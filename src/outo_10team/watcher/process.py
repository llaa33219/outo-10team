from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

CONFIG_PATH = Path("/root/.outo-10team/watcher_config.json")
OUTOAC_CONFIG_PATH = Path("/root/.outoac/config.json")
POLL_INTERVAL = 5
MAX_BACKOFF = 30
CONTEXT_MESSAGES = 25


def _resolve_host_url(url: str) -> str:
    return url.replace("localhost", "host.containers.internal", 1).replace("127.0.0.1", "host.containers.internal", 1)


def _setup_outoac(config: dict) -> None:
    provider = config.get("provider", {})
    model = provider.get("default_model", "gpt-4o")
    agent_name = config["agent_name"]
    agent_configs: dict[str, str] = config.get("agent_configs", {})
    wiki_config = config.get("wiki", {})

    agents: dict[str, str] = {}
    for name in agent_configs:
        agents[name] = f"/root/.outoac/agents/{name}.md"

    outoac_config = {
        "providers": {
            "default": {
                "kind": "openai",
                "base_url": provider.get("base_url", "http://localhost:11434/v1"),
                "api_key": provider.get("api_key", ""),
                "default_model": model,
                "max_output_tokens": 0,
            }
        },
        "agents": agents,
        "default_agent": agent_name,
        "skills_dir": "/root/.outoac/skills/",
    }

    if wiki_config.get("enabled", False):
        outoac_config["wiki"] = {
            "enabled": True,
            "wiki_path": "/root/.outoac/wiki/",
            "provider": wiki_config.get("provider", "openai"),
            "model": wiki_config.get("model", model),
            "api_key": wiki_config.get("api_key", provider.get("api_key", "")),
            "base_url": wiki_config.get("base_url", provider.get("base_url", "")),
            "max_output_tokens": 0,
            "debug": wiki_config.get("debug", False),
        }
        print(f"[watcher] wiki enabled with provider: {wiki_config.get('provider', 'openai')}", flush=True)

    OUTOAC_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTOAC_CONFIG_PATH.write_text(json.dumps(outoac_config, indent=2))
    print(f"[watcher] outoac config written with agents: {list(agents.keys())}", flush=True)


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    url = config.get("chatserver_url", "")
    if "localhost" in url or "127.0.0.1" in url:
        config["chatserver_url"] = _resolve_host_url(url)
        print(f"[watcher] translated chatserver URL: {config['chatserver_url']}", flush=True)
    return config


async def login(base_url: str, username: str, password: str) -> str:
    async with httpx.AsyncClient(base_url=base_url) as client:
        resp = await client.post(
            "/api/token",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def get_rooms(base_url: str, token: str, workspace_id: str) -> list[dict]:
    async with httpx.AsyncClient(base_url=base_url) as client:
        resp = await client.get(
            f"/api/workspaces/{workspace_id}/rooms",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def get_messages(base_url: str, token: str, workspace_id: str, room_id: str, limit: int = 20, before: str | None = None) -> list[dict]:
    params: dict[str, str | int] = {"limit": limit}
    if before:
        params["before"] = before
    async with httpx.AsyncClient(base_url=base_url) as client:
        resp = await client.get(
            f"/api/workspaces/{workspace_id}/rooms/{room_id}/messages",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def send_message(base_url: str, token: str, workspace_id: str, room_id: str, content: str) -> None:
    async with httpx.AsyncClient(base_url=base_url) as client:
        resp = await client.post(
            f"/api/workspaces/{workspace_id}/rooms/{room_id}/messages",
            json={"content": content},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()


def run_agent(message: str, agent_name: str) -> str:
    print(f"[subprocess] running outoac chat (msg_len={len(message)})...", flush=True)
    try:
        result = subprocess.run(
            ["outoac", "chat", message, "--agent", agent_name],
            capture_output=True,
            text=True,
        )
        print(
            f"[subprocess] rc={result.returncode} "
            f"out={len(result.stdout)} err={len(result.stderr)}",
            flush=True,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            err = result.stderr.strip()
            print(f"[subprocess] ERROR: {err[:200]}", flush=True)
            return f"[ERROR] {err}" if err else f"[ERROR] exit code {result.returncode}"
        print(f"[subprocess] success output_len={len(output)}", flush=True)
        return output
    except Exception as e:
        print(f"[subprocess] EXCEPTION: {type(e).__name__}: {e}", flush=True)
        return f"[ERROR] {e}"


def _parse_timestamp(ts_str: str) -> datetime:
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def _fetch_context(
    base_url: str,
    token: str,
    workspace_id: str,
    room_id: str,
    agent_name: str,
    before_message_id: str | None = None,
) -> str:
    messages = await get_messages(
        base_url, token, workspace_id, room_id,
        limit=CONTEXT_MESSAGES,
    )
    parts = ["Recent conversation history:"]
    for msg in reversed(messages):
        username = msg.get("username", "")
        content = msg.get("content", "")
        msg_id = msg.get("id", "")
        if content.strip():
            marker = " [THIS MESSAGE]" if msg_id == before_message_id else ""
            if username == agent_name:
                parts.append(f"[YOU]{marker}: {content}")
            else:
                parts.append(f"[OTHER: {username}]{marker}: {content}")
    return "\n".join(parts)


async def _process_new_message(
    base_url: str,
    token: str,
    workspace_id: str,
    room_id: str,
    agent_name: str,
    message: dict,
) -> None:
    sender = message.get("username", "")
    content = message.get("content", "")
    message_id = message.get("id", "")

    if sender == agent_name:
        return

    print(f"[process] room={room_id} sender={sender} msg_id={message_id}", flush=True)
    print(f"[process] content={content[:100]}", flush=True)

    context = await _fetch_context(base_url, token, workspace_id, room_id, agent_name, message_id)
    
    prompt = f"""{context}

[{sender}]: {content}

---
You are {agent_name}.

DECIDE: Should YOU respond to this message?

RESPOND ONLY WHEN:
1. Your team name "{agent_name}" is explicitly mentioned in the message
2. The message is clearly asking for your team's expertise
3. The conversation context shows this is about your team's work

DO NOT RESPOND WHEN:
1. Another team name is mentioned (e.g., "dev", "security", "design")
2. The message is general conversation
3. The topic is outside your expertise
4. Another team is already handling it

CRITICAL RULES:
- If "dev" is mentioned → ONLY dev responds
- If "security" is mentioned → ONLY security responds
- If "design" is mentioned → ONLY design responds
- If no team is mentioned → Everyone: [|NO_RESPONSE|]

OUTPUT: [|NO_RESPONSE|] OR your response. Nothing else."""

    print(f"[agent] prompt length={len(prompt)}", flush=True)

    print("[agent] calling outoac...", flush=True)
    response = await asyncio.to_thread(run_agent, prompt, agent_name)
    print(f"[agent] response length={len(response)} exit={'ERROR' in response[:10]}", flush=True)

    if "[|NO_RESPONSE|]" in response:
        print("[agent] NO_RESPONSE marker detected, staying silent", flush=True)
        return

    print("[agent] sending response...", flush=True)
    await send_message(base_url, token, workspace_id, room_id, response)
    print("[agent] response sent", flush=True)


async def watch_messages(
    base_url: str,
    token: str,
    workspace_id: str,
    agent_name: str,
    password: str,
) -> None:
    last_checked_at: dict[str, datetime] = {}
    processed_ids: dict[str, set[str]] = {}
    
    print(f"[watch] starting message watcher for agent={agent_name}", flush=True)

    rooms = await get_rooms(base_url, token, workspace_id)
    print(f"[watch] found {len(rooms)} rooms", flush=True)
    
    for room in rooms:
        room_id = room.get("id", "")
        room_name = room.get("name", "")
        processed_ids[room_id] = set()
        
        messages = await get_messages(base_url, token, workspace_id, room_id, limit=1)
        if messages:
            latest_msg = messages[0]
            created_at_str = latest_msg.get("created_at", "")
            if created_at_str:
                try:
                    last_checked_at[room_id] = _parse_timestamp(created_at_str)
                    print(f"[watch] room '{room_name}' ({room_id}): initialized at latest message time {created_at_str}", flush=True)
                except ValueError:
                    last_checked_at[room_id] = datetime.now(timezone.utc)
                    print(f"[watch] room '{room_name}' ({room_id}): initialized at current time (invalid timestamp)", flush=True)
            else:
                last_checked_at[room_id] = datetime.now(timezone.utc)
                print(f"[watch] room '{room_name}' ({room_id}): initialized at current time (no timestamp)", flush=True)
        else:
            last_checked_at[room_id] = datetime.now(timezone.utc)
            print(f"[watch] room '{room_name}' ({room_id}): initialized at current time (no messages)", flush=True)

    backoff = 1
    
    while True:
        print(f"[watch] polling (backoff={backoff}s)...", flush=True)
        try:
            rooms = await get_rooms(base_url, token, workspace_id)
            
            for room in rooms:
                room_id = room.get("id", "")
                room_name = room.get("name", "")
                
                messages = await get_messages(base_url, token, workspace_id, room_id, limit=50)
                
                if not messages:
                    continue
                
                new_messages = []
                for msg in messages:
                    msg_id = msg.get("id", "")
                    created_at_str = msg.get("created_at", "")
                    
                    if not created_at_str:
                        continue
                    
                    try:
                        created_at = _parse_timestamp(created_at_str)
                    except ValueError:
                        print(f"[warn] invalid timestamp: {created_at_str}", flush=True)
                        continue
                    
                    if msg_id in processed_ids.get(room_id, set()):
                        continue
                    
                    if created_at > last_checked_at.get(room_id, datetime.min.replace(tzinfo=timezone.utc)):
                        new_messages.append(msg)
                
                if new_messages:
                    new_messages.sort(key=lambda m: m.get("created_at", ""))
                    print(f"[watch] room '{room_name}': {len(new_messages)} new message(s)", flush=True)
                    
                    for msg in new_messages:
                        msg_id = msg.get("id", "")
                        sender = msg.get("username", "")
                        created_at_str = msg.get("created_at", "")
                        msg_room_id = msg.get("room_id", room_id)
                        
                        if sender == agent_name:
                            processed_ids.setdefault(room_id, set()).add(msg_id)
                            continue
                        
                        print(f"[watch] processing message {msg_id} from {sender} at {created_at_str} in room {msg_room_id}", flush=True)
                        try:
                            await _process_new_message(
                                base_url, token, workspace_id, msg_room_id, agent_name, msg,
                            )
                            processed_ids.setdefault(room_id, set()).add(msg_id)
                            print(f"[watch] done message {msg_id}", flush=True)
                        except Exception as e:
                            print(f"[error] processing message {msg_id}: {type(e).__name__}: {e}", flush=True)
                            processed_ids.setdefault(room_id, set()).add(msg_id)
                
                last_checked_at[room_id] = datetime.now(timezone.utc)
            
            backoff = 1
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                print("[watch] token expired, refreshing...", flush=True)
                try:
                    token = await login(base_url, agent_name, password)
                    print("[watch] token refreshed successfully", flush=True)
                    continue
                except Exception as login_error:
                    print(f"[error] token refresh failed: {login_error}", flush=True)
            else:
                print(f"[error] HTTP error: {e}", flush=True)
            backoff = min(backoff * 2, MAX_BACKOFF)
        except Exception as e:
            print(f"[error] polling messages: {type(e).__name__}: {e}", flush=True)
            backoff = min(backoff * 2, MAX_BACKOFF)

        print(f"[watch] sleeping {POLL_INTERVAL * backoff}s", flush=True)
        await asyncio.sleep(POLL_INTERVAL * backoff)


async def run() -> None:
    config = load_config()
    _setup_outoac(config)

    agent_name = config["agent_name"]
    chatserver_url = config["chatserver_url"]
    workspace_id = config["workspace_id"]
    password = config["password"]

    print(f"[watcher] agent={agent_name} workspace={workspace_id}", flush=True)

    token = await login(chatserver_url, agent_name, password)
    print("[watcher] logged in", flush=True)

    await watch_messages(chatserver_url, token, workspace_id, agent_name, password)


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("[watcher] shutting down", flush=True)
        sys.exit(0)


if __name__ == "__main__":
    main()

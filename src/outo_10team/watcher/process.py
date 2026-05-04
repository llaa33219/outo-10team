from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import httpx

CONFIG_PATH = Path("/root/.outo-10team/watcher_config.json")
OUTOAC_CONFIG_PATH = Path("/root/.outoac/config.json")
POLL_INTERVAL = 5
MAX_BACKOFF = 30


def _resolve_host_url(url: str) -> str:
    return url.replace("localhost", "host.containers.internal", 1).replace("127.0.0.1", "host.containers.internal", 1)


def _setup_outoac(config: dict) -> None:
    provider = config.get("provider", {})
    model = provider.get("default_model", "gpt-4o")

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
        "agents": {
            "main": "/root/.outoac/agents/main.md",
        },
        "default_agent": "main",
        "skills_dir": "/root/.outoac/skills/",
    }

    OUTOAC_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTOAC_CONFIG_PATH.write_text(json.dumps(outoac_config, indent=2))
    print("[watcher] outoac config written", flush=True)


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


async def get_messages(base_url: str, token: str, workspace_id: str, room_id: str, limit: int = 20) -> list[dict]:
    async with httpx.AsyncClient(base_url=base_url) as client:
        resp = await client.get(
            f"/api/workspaces/{workspace_id}/rooms/{room_id}/messages",
            params={"limit": limit},
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


def is_mentioned(content: str, agent_name: str) -> bool:
    return f"@{agent_name}" in content


def extract_mention(content: str, agent_name: str) -> str | None:
    if not is_mentioned(content, agent_name):
        return None
    return content.replace(f"@{agent_name}", "").strip()


def run_agent(message: str, agent_name: str = "main") -> str:
    try:
        result = subprocess.run(
            ["outoac", "chat", message, "--agent", agent_name],
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            err = result.stderr.strip()
            return f"[ERROR] {err}" if err else f"[ERROR] exit code {result.returncode}"
        return output
    except subprocess.TimeoutExpired:
        return "[ERROR] Agent timed out after 120 seconds"
    except Exception as e:
        return f"[ERROR] {e}"


async def poll_room(
    base_url: str,
    token: str,
    workspace_id: str,
    room_id: str,
    agent_name: str,
    seen_ids: set[str],
) -> None:
    messages = await get_messages(base_url, token, workspace_id, room_id)
    for msg in messages:
        msg_id = msg["id"]
        if msg_id in seen_ids:
            continue
        seen_ids.add(msg_id)

        username = msg.get("username", "")
        if username == agent_name:
            continue

        content = msg.get("content", "")
        if not content.strip():
            continue

        if not is_mentioned(content, agent_name):
            continue

        cleaned = extract_mention(content, agent_name)
        if not cleaned:
            continue

        print(f"[mention] room={room_id} {username}: {cleaned[:100]}", flush=True)

        prompt = f"[{username}]: {cleaned}"
        response = run_agent(prompt, "main")
        print(f"[agent] {response[:200]}", flush=True)

        await send_message(base_url, token, workspace_id, room_id, response)


async def watch_room(
    base_url: str,
    token: str,
    workspace_id: str,
    room_id: str,
    agent_name: str,
) -> None:
    seen_ids: set[str] = set()
    backoff = 1

    initial = await get_messages(base_url, token, workspace_id, room_id, limit=50)
    for msg in initial:
        seen_ids.add(msg["id"])
    print(f"[init] room={room_id} loaded {len(initial)} existing messages", flush=True)

    while True:
        try:
            await poll_room(base_url, token, workspace_id, room_id, agent_name, seen_ids)
            backoff = 1
        except Exception as e:
            print(f"[error] room={room_id}: {e}", flush=True)
            backoff = min(backoff * 2, MAX_BACKOFF)

        await asyncio.sleep(POLL_INTERVAL)


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

    rooms = await get_rooms(chatserver_url, token, workspace_id)
    room_ids = [r["id"] for r in rooms]
    print(f"[watcher] found {len(room_ids)} rooms", flush=True)

    tasks = [watch_room(chatserver_url, token, workspace_id, rid, agent_name) for rid in room_ids]
    await asyncio.gather(*tasks)


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("[watcher] shutting down", flush=True)
        sys.exit(0)


if __name__ == "__main__":
    main()

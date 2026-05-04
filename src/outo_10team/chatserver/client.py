from __future__ import annotations

import httpx


class ChatserverClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token: str | None = None
        self._client = httpx.Client(base_url=self._base_url, timeout=30.0)

    @property
    def token(self) -> str | None:
        return self._token

    def _headers(self) -> dict[str, str]:
        if not self._token:
            raise RuntimeError("Not authenticated - call login() first")
        return {"Authorization": f"Bearer {self._token}"}

    def register(self, username: str, password: str) -> dict:
        resp = self._client.post(
            "/api/register",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        return resp.json()

    def login(self, username: str, password: str) -> str:
        resp = self._client.post(
            "/api/token",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        return self._token

    def get_me(self) -> dict:
        resp = self._client.get("/api/me", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def list_workspaces(self) -> list[dict]:
        resp = self._client.get("/api/workspaces", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def create_workspace(self, name: str) -> dict:
        resp = self._client.post(
            "/api/workspaces",
            json={"name": name},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def join_workspace(self, workspace_id: str) -> dict:
        resp = self._client.post(
            f"/api/workspaces/{workspace_id}/join",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def list_rooms(self, workspace_id: str) -> list[dict]:
        resp = self._client.get(
            f"/api/workspaces/{workspace_id}/rooms",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def create_room(self, workspace_id: str, name: str) -> dict:
        resp = self._client.post(
            f"/api/workspaces/{workspace_id}/rooms",
            json={"name": name},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def list_messages(self, workspace_id: str, room_id: str, limit: int = 50, before: str | None = None) -> list[dict]:
        params: dict[str, str | int] = {"limit": limit}
        if before:
            params["before"] = before
        resp = self._client.get(
            f"/api/workspaces/{workspace_id}/rooms/{room_id}/messages",
            params=params,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def send_message(self, workspace_id: str, room_id: str, content: str) -> dict:
        resp = self._client.post(
            f"/api/workspaces/{workspace_id}/rooms/{room_id}/messages",
            json={"content": content},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def reply_to_message(self, workspace_id: str, room_id: str, message_id: str, content: str) -> dict:
        resp = self._client.post(
            f"/api/workspaces/{workspace_id}/rooms/{room_id}/messages/{message_id}/reply",
            json={"content": content},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

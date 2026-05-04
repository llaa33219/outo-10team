from __future__ import annotations

import json
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from podman import PodmanClient
from podman.errors import ImageNotFound

logger = logging.getLogger(__name__)

CONTAINER_LABEL = "outo-10team"
NETWORK_NAME = "outo-10team-net"


class ContainerManager:
    def __init__(self, socket_path: str | None = None) -> None:
        if socket_path is None:
            uid = os.getuid()
            socket_path = f"unix:///run/user/{uid}/podman/podman.sock"
        self._url = socket_path
        self._client: PodmanClient | None = None

    def connect(self) -> None:
        self._client = PodmanClient(base_url=self._url)

    @property
    def client(self) -> PodmanClient:
        if self._client is None:
            raise RuntimeError("Not connected - call connect() first")
        return self._client

    def build_image(self, dockerfile_path: Path, tag: str = "outo-10team:latest") -> None:
        logger.info("Building image: %s", tag)
        subprocess.run(
            ["podman", "build", "-t", tag, "-f", str(dockerfile_path), str(dockerfile_path.parent)],
            check=True,
        )
        logger.info("Image built: %s", tag)

    def create_network(self, name: str = NETWORK_NAME) -> Any:
        try:
            return self.client.networks.get(name)
        except Exception:
            return self.client.networks.create(name=name, driver="bridge")

    def create_container(
        self,
        name: str,
        slug: str,
        image: str,
        watcher_config: dict,
        agent_configs: dict[str, str],
        mem_limit: str = "512m",
        cpu_shares: int = 512,
        pids_limit: int = 100,
    ) -> Any:
        labels = {CONTAINER_LABEL: "true", "team": name}

        config_dir = Path(f"/tmp/outo-10team/{slug}")
        config_dir.mkdir(parents=True, exist_ok=True)

        watcher_config_path = config_dir / "watcher_config.json"
        watcher_config_path.write_text(json.dumps(watcher_config, indent=2))

        agent_dir = config_dir / "agents"
        agent_dir.mkdir(exist_ok=True)
        for agent_name, md_content in agent_configs.items():
            (agent_dir / f"{agent_name}.md").write_text(md_content)

        volumes = {
            str(watcher_config_path): {"bind": "/root/.outo-10team/watcher_config.json", "mode": "ro"},
            str(agent_dir): {"bind": "/root/.outoac/agents", "mode": "ro"},
        }

        try:
            container = self.client.containers.create(
                image=image,
                name=f"outo10team-{slug}",
                labels=labels,
                mem_limit=mem_limit,
                cpu_shares=cpu_shares,
                pids_limit=pids_limit,
                volumes=volumes,
                detach=True,
                network=NETWORK_NAME,
            )
        except ImageNotFound:
            raise RuntimeError(f"Image not found: {image}. Run 'outo-10team build' first.")

        return container

    def start_container(self, container_id: str) -> None:
        container = self.client.containers.get(container_id)
        container.start()

    def stop_container(self, container_id: str, timeout: int = 30) -> None:
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
        except Exception:
            logger.debug("Failed to stop container %s (may already be stopped)", container_id)

    def remove_container(self, container_id: str, force: bool = False) -> None:
        container = self.client.containers.get(container_id)
        container.remove(force=force, v=True)

    def get_container(self, name: str) -> Any | None:
        try:
            return self.client.containers.get(name)
        except Exception:
            return None

    def list_outo_containers(self) -> list[dict[str, Any]]:
        containers = self.client.containers.list(
            all=True,
            filters={"label": f"{CONTAINER_LABEL}=true"},
        )
        result: list[dict[str, Any]] = []
        for c in containers:
            c.reload()
            result.append({
                "id": c.id,
                "name": c.name,
                "status": c.status,
                "team": c.labels.get("team", "unknown"),
            })
        return result

    def batch_create(
        self,
        configs: list[dict[str, Any]],
        max_workers: int = 5,
    ) -> list[str]:
        results: list[str] = [None] * len(configs)

        def _create(index: int, cfg: dict[str, Any]) -> tuple[int, str]:
            c = self.create_container(**cfg)
            return index, c.id

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_create, i, cfg) for i, cfg in enumerate(configs)]
            for f in futures:
                idx, cid = f.result()
                results[idx] = cid

        return results

    def batch_stop(self, container_ids: list[str], max_workers: int = 5) -> None:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(self.stop_container, cid) for cid in container_ids]
            for f in futures:
                f.result()

    def batch_remove(self, container_ids: list[str], max_workers: int = 5, force: bool = True) -> None:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(self.remove_container, cid, force=force) for cid in container_ids]
            for f in futures:
                f.result()

    def cleanup_all(self) -> int:
        containers = self.list_outo_containers()
        if not containers:
            return 0
        ids = [c["id"] for c in containers]
        self.batch_remove(ids)
        return len(ids)

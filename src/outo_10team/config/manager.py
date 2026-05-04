from __future__ import annotations

import json
from pathlib import Path

from .schema import AppConfig


class ConfigManager:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._config_dir = config_dir or Path.home() / ".outo-10team"
        self._config_path = self._config_dir / "config.json"

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    @property
    def config_path(self) -> Path:
        return self._config_path

    @property
    def data_dir(self) -> Path:
        return self._config_dir / "data"

    def exists(self) -> bool:
        return self._config_path.exists()

    def load(self) -> AppConfig:
        with open(self._config_path) as f:
            data = json.load(f)
        return AppConfig(**data)

    def save(self, config: AppConfig) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w") as f:
            json.dump(config.model_dump(), f, indent=2)

    def get_team_data_dir(self, team_name: str) -> Path:
        team_dir = self.data_dir / team_name
        team_dir.mkdir(parents=True, exist_ok=True)
        return team_dir

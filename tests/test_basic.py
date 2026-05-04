from pathlib import Path

from outo_10team.agents.generator import generate_all_team_agents, generate_agent_md
from outo_10team.agents.registry import TEAMS, get_all_team_names, get_team
from outo_10team.agents.team_config import AgentDef, TeamConfig
from outo_10team.config.schema import AppConfig


def test_config_defaults():
    config = AppConfig()
    assert config.provider.base_url == "http://localhost:11434/v1"
    assert config.chatserver.url == "http://localhost:18279"
    assert config.containers.mem_limit == "512m"


def test_config_roundtrip():
    config = AppConfig()
    data = config.model_dump()
    restored = AppConfig(**data)
    assert restored == config


def test_team_count():
    assert len(TEAMS) == 10


def test_team_names():
    names = get_all_team_names()
    assert "main" in names
    assert "research" in names
    assert "dev" in names
    assert "design" in names
    assert "data" in names
    assert "security" in names
    assert "infra" in names
    assert "quality" in names
    assert "docs" in names
    assert "support" in names


def test_team_agents():
    for team in TEAMS:
        assert len(team.agents) == 5
        agent_names = [a.name for a in team.agents]
        assert "main" in agent_names


def test_get_team():
    team = get_team("main")
    assert team.team_name == "main"
    assert team.main_agent.name == "main"


def test_agent_md_generation():
    agent = AgentDef(name="test", role="테스터", instructions="테스트 에이전트입니다.")
    team = TeamConfig(team_name="test", description="테스트 팀", agents=(agent,))
    md = generate_agent_md(agent, team)
    assert "model: gpt-4o" in md
    assert "provider: default" in md
    assert "테스터" in md
    assert "테스트 에이전트입니다." in md


def test_generate_team_agents(tmp_path: Path):
    result = generate_all_team_agents(TEAMS[:2], tmp_path)
    assert "main" in result
    assert "research" in result
    assert len(result["main"]) == 5
    assert len(result["research"]) == 5

    main_dir = tmp_path / "main"
    assert main_dir.exists()
    assert (main_dir / "main.md").exists()

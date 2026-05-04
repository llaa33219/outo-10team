from pathlib import Path

from outo_10team.agents.generator import generate_all_team_agents, generate_agent_md
from outo_10team.agents.registry import create_teams, get_all_team_names, get_default_team_names, get_team
from outo_10team.agents.team_config import AgentDef, TeamConfig
from outo_10team.config.schema import AppConfig


def test_config_defaults():
    config = AppConfig()
    assert config.provider.base_url == "http://localhost:11434/v1"
    assert config.chatserver.url == "http://localhost:18279"
    assert config.containers.mem_limit == "512m"
    assert config.team_names == {}


def test_config_roundtrip():
    config = AppConfig()
    data = config.model_dump()
    restored = AppConfig(**data)
    assert restored == config


def test_default_teams():
    teams = create_teams()
    assert len(teams) == 10


def test_custom_team_names():
    teams = create_teams({"main": "leader", "research": "explorer"})
    names = get_all_team_names(teams)
    assert "leader" in names
    assert "explorer" in names
    assert "main" not in names


def test_default_team_names():
    names = get_default_team_names()
    assert "main" in names
    assert "research" in names
    assert "dev" in names
    assert len(names) == 10


def test_team_agents():
    teams = create_teams()
    for team in teams:
        assert len(team.agents) == 5
        agent_names = [a.name for a in team.agents]
        assert "main" in agent_names


def test_get_team():
    teams = create_teams({"main": "leader"})
    team = get_team("leader", teams)
    assert team.team_name == "leader"
    assert team.main_agent.name == "main"


def test_agent_md_generation():
    agent = AgentDef(name="test", role="테스터", instructions="테스트 에이전트입니다.")
    team = TeamConfig(team_name="test", default_name="test", description="테스트 팀", agents=(agent,))
    all_teams = [team]
    md = generate_agent_md(agent, team, all_teams)
    assert "model: gpt-4o" in md
    assert "provider: default" in md
    assert "테스터" in md
    assert "테스트 에이전트입니다." in md


def test_agent_md_team_awareness():
    team1 = TeamConfig(team_name="alpha", default_name="alpha", description="Alpha team", agents=(
        AgentDef("main", "Alpha Leader", "Lead alpha team"),
    ))
    team2 = TeamConfig(team_name="beta", default_name="beta", description="Beta team", agents=(
        AgentDef("main", "Beta Leader", "Lead beta team"),
    ))
    all_teams = [team1, team2]
    md = generate_agent_md(team1.agents[0], team1, all_teams)
    assert "@beta" in md
    assert "Beta team" in md


def test_generate_team_agents(tmp_path: Path):
    teams = create_teams()
    result = generate_all_team_agents(teams[:2], tmp_path)
    assert len(result) == 2

    main_dir = tmp_path / teams[0].team_name
    assert main_dir.exists()
    assert (main_dir / "main.md").exists()

    md_content = (main_dir / "main.md").read_text()
    assert "협업 가능한 팀" in md_content
    assert teams[1].team_name in md_content

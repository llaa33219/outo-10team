from __future__ import annotations

from pathlib import Path

from .team_config import AgentDef, TeamConfig


def generate_agent_md(agent: AgentDef, team: TeamConfig, provider: str = "default", model: str = "gpt-4o") -> str:
    header = f"---\nmodel: {model}\nprovider: {provider}\ntemperature: 0.7\n---\n\n"
    role = f"# {agent.role}\n\n"
    body = agent.instructions + "\n\n"
    body += f"당신은 {team.team_name} 팀의 {agent.role}입니다.\n"
    body += f"팀 설명: {team.description}\n"

    if agent.name != "main":
        body += f"\n메인 에이전트(@main)의 지시를 따르고 결과를 보고하세요.\n"
    else:
        body += f"\n다른 에이전트들을 지휘하고 결과를 종합하세요.\n"
        teammate_names = [a.name for a in team.agents if a.name != "main"]
        body += f"팀원: {', '.join('@' + n for n in teammate_names)}\n"

    return header + role + body


def generate_team_agents(
    team: TeamConfig,
    output_dir: Path,
    provider: str = "default",
    model: str = "gpt-4o",
) -> list[Path]:
    team_dir = output_dir / team.team_name
    team_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for agent in team.agents:
        content = generate_agent_md(agent, team, provider, model)
        path = team_dir / f"{agent.name}.md"
        path.write_text(content)
        paths.append(path)

    return paths


def generate_all_team_agents(
    teams: list[TeamConfig],
    output_dir: Path,
    provider: str = "default",
    model: str = "gpt-4o",
) -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = {}
    for team in teams:
        paths = generate_team_agents(team, output_dir, provider, model)
        result[team.team_name] = paths
    return result

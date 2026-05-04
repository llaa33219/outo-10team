from __future__ import annotations

from pathlib import Path

from .team_config import AgentDef, TeamConfig


def generate_agent_md(
    agent: AgentDef,
    team: TeamConfig,
    all_teams: list[TeamConfig],
    provider: str = "default",
    model: str = "gpt-4o",
) -> str:
    header = f"---\nmodel: {model}\nprovider: {provider}\ntemperature: 0.7\n---\n\n"
    role = f"# {agent.role}\n\n"
    body = agent.instructions + "\n\n"
    body += f"당신은 {team.team_name} 팀의 {agent.role}입니다.\n"
    body += f"팀 설명: {team.description}\n"

    if agent.name != "main":
        body += f"\n메인 에이전트(@{team.team_name})의 지시를 따르고 결과를 보고하세요.\n"
    else:
        body += f"\n다른 에이전트들을 지휘하고 결과를 종합하세요.\n"
        teammate_names = [a.name for a in team.agents if a.name != "main"]
        body += f"팀원: {', '.join(f'@{team.team_name}-{n}' for n in teammate_names)}\n"

    body += "\n## 협업 가능한 팀\n\n"
    body += "다음 팀들과 협업할 수 있습니다. 필요시 @팀이름으로 맨션하세요:\n\n"
    for other_team in all_teams:
        if other_team.team_name == team.team_name:
            continue
        body += f"- @{other_team.team_name}: {other_team.description}\n"

    body += "\n다른 팀에 작업을 위임하거나 질문할 때는 반드시 @팀이름으로 맨션하세요.\n"
    body += f"자신의 팀원을 호출할 때는 @{team.team_name}-역할 형태로 호출하세요.\n"

    return header + role + body


def generate_team_agents(
    team: TeamConfig,
    all_teams: list[TeamConfig],
    output_dir: Path,
    provider: str = "default",
    model: str = "gpt-4o",
) -> list[Path]:
    team_dir = output_dir / team.team_name
    team_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for agent in team.agents:
        content = generate_agent_md(agent, team, all_teams, provider, model)
        if agent.name == "main":
            filename = f"{team.team_name}.md"
        else:
            filename = f"{team.team_name}-{agent.name}.md"
        path = team_dir / filename
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
        paths = generate_team_agents(team, teams, output_dir, provider, model)
        result[team.team_name] = paths
    return result

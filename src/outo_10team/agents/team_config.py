from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentDef:
    name: str
    role: str
    instructions: str


@dataclass(frozen=True)
class TeamConfig:
    team_name: str
    default_name: str
    description: str
    agents: tuple[AgentDef, ...] = field(default_factory=tuple)

    @property
    def main_agent(self) -> AgentDef:
        for agent in self.agents:
            if agent.name == "main":
                return agent
        raise ValueError(f"No main agent found in team {self.team_name}")

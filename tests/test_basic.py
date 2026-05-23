from pathlib import Path

from outo_10team.agents.generator import generate_all_team_agents, generate_agent_md
from outo_10team.agents.registry import create_teams, get_all_team_names, get_default_team_names, get_team
from outo_10team.agents.team_config import AgentDef, TeamConfig
from outo_10team.config.schema import AppConfig


def test_agent_def_backward_compat():
    agent = AgentDef("test", "Tester", "Test agent.")
    assert agent.goal == ""
    assert agent.backstory == ""
    assert agent.collaboration_notes == ""


def test_agent_def_with_new_fields():
    agent = AgentDef(
        name="test",
        role="Tester",
        instructions="Test agent.",
        goal="Test everything.",
        backstory="Experienced tester.",
        collaboration_notes="Delegate to QA.",
    )
    assert agent.goal == "Test everything."
    assert agent.backstory == "Experienced tester."
    assert agent.collaboration_notes == "Delegate to QA."


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
    agent = AgentDef(name="test", role="Tester", instructions="You are a test agent.")
    team = TeamConfig(team_name="test", default_name="test", description="Test team", agents=(agent,))
    all_teams = [team]
    md = generate_agent_md(agent, team, all_teams)
    assert "model: gpt-4o" in md
    assert "provider: default" in md
    assert "Tester" in md
    assert "You are a test agent." in md


def test_agent_md_team_awareness():
    team1 = TeamConfig(team_name="alpha", default_name="alpha", description="Alpha team", agents=(
        AgentDef("main", "Alpha Leader", "Lead alpha team"),
    ))
    team2 = TeamConfig(team_name="beta", default_name="beta", description="Beta team", agents=(
        AgentDef("main", "Beta Leader", "Lead beta team"),
    ))
    all_teams = [team1, team2]
    md = generate_agent_md(team1.agents[0], team1, all_teams)
    assert "**beta**: Beta team" in md
    assert "Calling Rules" in md


def test_generate_team_agents(tmp_path: Path):
    teams = create_teams()
    result = generate_all_team_agents(teams[:2], tmp_path)
    assert len(result) == 2

    main_dir = tmp_path / teams[0].team_name
    assert main_dir.exists()
    assert (main_dir / "main.md").exists()

    md_content = (main_dir / "main.md").read_text()
    assert "Collaborating Teams" in md_content
    assert teams[1].team_name in md_content


def test_agent_md_renders_goal_and_backstory():
    agent = AgentDef("test", "Tester", "Instructions.", goal="Test goal.", backstory="Test backstory.")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "**Your Goal**: Test goal." in md
    assert "**About You**: Test backstory." in md


def test_agent_md_skips_empty_goal_backstory():
    agent = AgentDef("test", "Tester", "Instructions.")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "**Your Goal**" not in md
    assert "**About You**" not in md


def test_agent_md_renders_collaboration_notes():
    agent = AgentDef("x", "Role", "Instructions.", collaboration_notes="Special notes.")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "Special notes." in md
    assert "Role-Specific" in md


def test_agent_md_omits_empty_collaboration_notes():
    agent = AgentDef("x", "Role", "Instructions.")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "Role-Specific" not in md


def test_new_prompt_sections_present():
    agent = AgentDef("x", "Role", "Instructions.")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "Failure Handling" in md
    assert "Anti-Cascade Rule" in md
    assert "Decision Transparency" in md
    assert "Coordination Efficiency" in md
    assert "Delegation Format" in md


def test_prompt_section_order():
    agent = AgentDef("x", "Role", "Instructions.")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    silence_pos = md.index("Response Decision Framework")
    collab_pos = md.index("Collaboration Rules")
    assert silence_pos < collab_pos, "Response Decision Framework should precede Collaboration Rules"


def test_all_50_agents_have_goal_and_backstory():
    teams = create_teams()
    for team in teams:
        for agent in team.agents:
            assert agent.goal, f"{team.team_name}/{agent.name} missing goal"
            assert agent.backstory, f"{team.team_name}/{agent.name} missing backstory"


def test_only_main_agents_have_collaboration_notes():
    teams = create_teams()
    for team in teams:
        for agent in team.agents:
            if agent.name == "main":
                assert agent.collaboration_notes, f"{team.team_name}/main missing collaboration_notes"
            else:
                assert not agent.collaboration_notes, f"{team.team_name}/{agent.name} should not have collaboration_notes"


def test_all_agents_english():
    teams = create_teams()
    for team in teams:
        assert team.description.isascii(), f"{team.team_name} description not English"
        for agent in team.agents:
            assert agent.role.isascii(), f"{team.team_name}/{agent.name} role not English"
            assert agent.instructions.isascii(), f"{team.team_name}/{agent.name} instructions not English"
            assert agent.goal.isascii(), f"{team.team_name}/{agent.name} goal not English"
            assert agent.backstory.isascii(), f"{team.team_name}/{agent.name} backstory not English"


def test_agent_def_new_fields_defaults():
    agent = AgentDef("test", "Tester", "Test agent.")
    assert agent.domain_expertise == ()
    assert agent.task_types == ()
    assert agent.quality_criteria == ()
    assert agent.wiki_namespace == ""
    assert agent.communication_style == ""
    assert agent.escalation_triggers == ()


def test_agent_def_new_fields_explicit():
    agent = AgentDef(
        name="test",
        role="Tester",
        instructions="Test agent.",
        domain_expertise=("skill1", "skill2"),
        task_types=("task1",),
        quality_criteria=("criterion1",),
        wiki_namespace="test/ns",
        communication_style="Direct",
        escalation_triggers=("trigger1",),
    )
    assert agent.domain_expertise == ("skill1", "skill2")
    assert agent.task_types == ("task1",)
    assert agent.quality_criteria == ("criterion1",)
    assert agent.wiki_namespace == "test/ns"
    assert agent.communication_style == "Direct"
    assert agent.escalation_triggers == ("trigger1",)


def test_agent_def_backward_compat_extended():
    agent = AgentDef("test", "Tester", "Test agent.")
    assert agent.name == "test"
    assert agent.role == "Tester"
    assert agent.instructions == "Test agent."
    assert agent.domain_expertise == ()
    assert agent.wiki_namespace == ""


def test_task_classification_section_present():
    agent = AgentDef("x", "Role", "Instructions.")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "Response Decision Framework" in md
    assert "Collaboration Rules" in md


def test_quality_checklist_section_present():
    agent = AgentDef("x", "Role", "Instructions.")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "Quality Checklist" in md
    assert "All requirements addressed" in md


def test_communication_style_section_present():
    agent = AgentDef("x", "Role", "Instructions.")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "Communication Style" in md


def test_escalation_rules_section_present():
    agent = AgentDef("x", "Role", "Instructions.")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "Escalation Rules" in md


def test_success_criteria_section_present():
    agent = AgentDef("x", "Role", "Instructions.")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "Success Criteria" in md


def test_section_order_phase2():
    agent = AgentDef("x", "Role", "Instructions.")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    response_pos = md.index("Response Decision Framework")
    collab_pos = md.index("Collaboration Rules")
    assert response_pos < collab_pos, "Response Decision Framework should precede Collaboration Rules"


def test_domain_expertise_rendered():
    agent = AgentDef("x", "Role", "Instructions.", domain_expertise=("skill1", "skill2"))
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "skill1" in md
    assert "skill2" in md
    assert "Domain Expertise" in md


def test_domain_expertise_omitted_when_empty():
    agent = AgentDef("x", "Role", "Instructions.")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "Domain Expertise" not in md


def test_wiki_namespace_rendered():
    agent = AgentDef("x", "Role", "Instructions.", wiki_namespace="dev/backend")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "dev/backend" in md
    assert "wiki_record" in md
    assert "wiki_search" in md


def test_wiki_namespace_omitted_when_empty():
    agent = AgentDef("x", "Role", "Instructions.")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "Knowledge Management" not in md


def test_full_prompt_contains_all_sections():
    agent = AgentDef(
        "x", "Role", "Instructions.",
        domain_expertise=("skill1",),
        wiki_namespace="test/x",
        task_types=("implementation",),
        quality_criteria=("criterion1",),
        communication_style="Direct",
        escalation_triggers=("trigger1",),
    )
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    sections = [
        "Response Decision Framework", "Quality Checklist", "Communication Style",
        "Escalation Rules", "Success Criteria", "Knowledge Management",
        "Your Domain Expertise", "Collaboration Rules", "Failure Handling",
        "Output Storage", "Calling Rules", "Decision Transparency",
        "Coordination Efficiency", "Task Type Guidance",
    ]
    for section in sections:
        assert section in md, f"Missing section: {section}"


def test_domain_expertise_rendered_for_all_agents():
    teams = create_teams()
    for team in teams:
        for agent in team.agents:
            assert agent.domain_expertise, f"{team.team_name}/{agent.name} missing domain_expertise"


def test_wiki_namespace_in_prompt():
    agent = AgentDef("x", "Role", "Instructions.", wiki_namespace="dev/backend")
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert "dev/backend" in md
    assert "wiki_record" in md
    assert "wiki_search" in md


def test_domain_specific_sections_by_team():
    teams = create_teams()
    dev_team = teams[2]  # dev team
    md = generate_agent_md(dev_team.agents[0], dev_team, teams)
    assert "Development Standards" in md or "Code Review" in md


def test_cross_team_expertise_shown():
    teams = create_teams()
    md = generate_agent_md(teams[0].agents[0], teams[0], teams)
    assert "Collaborating Teams" in md


def test_prompt_length_reasonable():
    agent = AgentDef(
        "x", "Role", "Instructions.",
        domain_expertise=("s1",),
        wiki_namespace="t/x",
        task_types=("implementation",),
    )
    team = TeamConfig("t", "t", "desc", (agent,))
    md = generate_agent_md(agent, team, [team])
    assert len(md) < 35000, f"Prompt too long: {len(md)} chars"


def test_backward_compat_full_generation():
    teams = create_teams()
    for team in teams:
        for agent in team.agents:
            md = generate_agent_md(agent, team, teams)
            assert len(md) > 100

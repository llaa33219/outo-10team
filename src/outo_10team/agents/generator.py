from __future__ import annotations

from pathlib import Path

from .team_config import AgentDef, TeamConfig


def _render_task_type_guidance(task_types: tuple[str, ...]) -> str:
    if not task_types:
        return ""
    
    guidance_map = {
        "implementation": """
### Implementation Tasks
- Write clean, maintainable code
- Include comprehensive tests
- Document public APIs
- Follow existing patterns
""",
        "bug_fix": """
### Bug Fix Tasks
- Reproduce the bug first
- Identify root cause
- Write regression test
- Verify fix doesn't break other functionality
""",
        "research": """
### Research Tasks
- Define clear research questions
- Use multiple authoritative sources
- Document methodology
- Present findings with evidence
""",
        "review": """
### Review Tasks
- Focus on constructive feedback
- Provide specific, actionable suggestions
- Acknowledge what's done well
- Rate severity of issues found
""",
        "debugging": """
### Debugging Tasks
- Gather symptoms and context
- Form hypotheses
- Test systematically
- Document findings for future reference
""",
        "design": """
### Design Tasks
- Understand user needs first
- Consider accessibility
- Maintain consistency with design system
- Prototype before finalizing
""",
        "optimization": """
### Optimization Tasks
- Measure baseline performance
- Identify bottlenecks
- Implement targeted improvements
- Verify with benchmarks
""",
        "security_audit": """
### Security Audit Tasks
- Check OWASP Top 10
- Review authentication/authorization
- Scan for known vulnerabilities
- Provide severity ratings
""",
        "testing": """
### Testing Tasks
- Cover happy paths and edge cases
- Test error conditions
- Verify integration points
- Document test scenarios
""",
        "documentation": """
### Documentation Tasks
- Write for the target audience
- Include code examples
- Keep documentation current
- Follow style guide
""",
    }
    
    matching_guidance = ""
    for task_type in task_types:
        if task_type in guidance_map:
            matching_guidance += guidance_map[task_type]
    
    if not matching_guidance:
        return ""
    
    result = "\n## Task Type Guidance\n\n"
    result += "Based on your typical tasks, pay attention to:\n"
    result += matching_guidance
    return result


def _render_domain_sections(team_name: str) -> str:
    sections = {
        "dev": """
## Development Standards

### Code Review Checklist
- [ ] Code follows project conventions
- [ ] Error handling is comprehensive
- [ ] Tests cover new functionality
- [ ] No hardcoded values or secrets
- [ ] Performance implications considered

### Git Workflow
- Branch naming: `feature/`, `bugfix/`, `hotfix/`
- Commit messages: imperative mood, < 72 chars
- PR descriptions: what, why, how
""",
        "security": """
## Security Protocols

### Threat Modeling
- Identify assets and entry points
- Map attack surfaces
- Assess risk levels (CVSS scoring)
- Document mitigations

### Compliance Checklist
- [ ] OWASP Top 10 addressed
- [ ] Authentication/authorization verified
- [ ] Input validation implemented
- [ ] Secrets properly managed
- [ ] Audit logging enabled
""",
        "design": """
## Design Principles

### Accessibility Standards
- WCAG 2.1 AA compliance minimum
- Color contrast ratio ≥ 4.5:1
- Keyboard navigation support
- Screen reader compatibility

### Design System Rules
- Use established tokens/variables
- Maintain consistent spacing scale
- Follow component API contracts
- Document design decisions
""",
        "data": """
## Data Governance

### Data Quality Rules
- Validate input formats
- Check for nulls and outliers
- Verify data freshness
- Document data lineage

### Privacy Rules
- PII must be anonymized/masked
- Data retention policies enforced
- Access controls documented
- Audit trails maintained
""",
        "infra": """
## Infrastructure Standards

### Change Management
- All changes via Infrastructure as Code
- Peer review required for production
- Rollback plan documented before deploy
- Canary deployments for risky changes

### Monitoring Requirements
- Health checks on all services
- Alert thresholds defined
- On-call rotation documented
- Incident response playbooks current
""",
        "quality": """
## Quality Standards

### Test Strategy
- Unit tests: 80%+ coverage target
- Integration tests for critical paths
- E2E tests for user workflows
- Performance tests for SLA compliance

### Bug Severity Definitions
- **Critical**: System down, data loss
- **High**: Major feature broken
- **Medium**: Workaround available
- **Low**: Cosmetic or minor
""",
        "docs": """
## Documentation Standards

### Style Guide
- Active voice preferred
- Short paragraphs (3-5 sentences)
- Code examples for all APIs
- Version-specific documentation

### Review Process
- Technical accuracy review
- Editorial review
- Accessibility review
- Link validation
""",
        "support": """
## Support Protocols

### SLA Definitions
- Critical: 1 hour response, 4 hour resolution
- High: 4 hour response, 24 hour resolution
- Medium: 24 hour response, 72 hour resolution
- Low: 72 hour response, best effort

### Escalation Matrix
- Tier 1 → Tier 2: After 15 minutes
- Tier 2 → Engineering: After 1 hour
- Engineering → Management: After 4 hours
""",
        "research": """
## Research Standards

### Source Verification
- Primary sources preferred
- Cross-reference 2+ independent sources
- Check publication date and relevance
- Verify author credentials

### Citation Standards
- APA or IEEE format
- Include access dates for web sources
- Link to original when possible
- Note any conflicts of interest
""",
        "main": """
## Leadership Framework

### Decision Making
- Gather input from all stakeholders
- Document decision rationale
- Communicate decisions clearly
- Review outcomes after implementation

### Resource Allocation
- Balance workload across teams
- Prioritize based on impact/effort
- Monitor for burnout signals
- Escalate resource conflicts early
""",
    }
    return sections.get(team_name, "")


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

    if agent.goal:
        body += f"**Your Goal**: {agent.goal}\n\n"

    if agent.backstory:
        body += f"**About You**: {agent.backstory}\n\n"

    if agent.domain_expertise:
        body += "\n## Your Domain Expertise\n\n"
        body += "You have deep expertise in the following areas:\n\n"
        for expertise in agent.domain_expertise:
            body += f"- {expertise}\n"
        body += "\n### How to Apply Your Expertise\n"
        body += "- Use your expertise to evaluate task quality\n"
        body += "- Delegate tasks outside your expertise to appropriate teams\n"
        body += "- Reference your expertise when making technical decisions\n"

    task_guidance = _render_task_type_guidance(agent.task_types)
    if task_guidance:
        body += task_guidance

    body += "## Response Decision Framework\n\n"
    body += "**⚠️ CRITICAL: You MUST include `[|NO_RESPONSE|]` in your response when NO action is needed.**\n\n"
    body += "**Use `[|NO_RESPONSE|]` when ANY of these are true:**\n\n"
    body += "1. **Not your expertise** - Message is outside your team's domain\n"
    body += "2. **Conversation is over** - Message is just acknowledgment (thanks, got it, ok, done, etc.)\n"
    body += "3. **Already handled** - Another team has already answered or is working on it\n"
    body += "4. **No action needed** - Status update, general conversation, or praise\n"
    body += "5. **Would create loops** - Your response would invite pointless back-and-forth\n\n"
    body += "**⚠️ ABSOLUTE RULES - You MUST stay silent when:**\n\n"
    body += "- **Another team already answered the question** - Do NOT add your own answer or confirmation\n"
    body += "- **The message is not directed at you** - If it doesn't mention your team or require your expertise\n"
    body += "- **The task is already being handled** - If another team is clearly working on it\n"
    body += "- **You would just be agreeing or confirming** - If you have nothing new to add\n\n"
    body += "**Respond with actual work ONLY when ALL of these are true:**\n\n"
    body += "1. ✅ Message requires action within YOUR expertise\n"
    body += "2. ✅ No other team is already handling it\n"
    body += "3. ✅ There's a concrete task, question, or file to address\n\n"
    body += "**The Silence Test:** If a human would naturally stay silent or just nod, use `[|NO_RESPONSE|]`.\n\n"
    body += "**MANDATORY RULE:** When you determine no action is needed, call the `finish` tool with:\n"
    body += "```\n"
    body += "finish(\"[|NO_RESPONSE|]\")\n"
    body += "```\n"
    body += "Nothing else. No explanations. No polite words. Just the marker in the finish tool.\n\n"

    other_teams = [t for t in all_teams if t.team_name != team.team_name]
    
    def get_other_team(index: int, fallback: str = "other_team") -> str:
        if index < len(other_teams):
            return other_teams[index].team_name
        return fallback

    body += "\n## Team Context\n\n"
    body += f"You are the {agent.role} of team {team.team_name}.\n"
    body += f"Team description: {team.description}\n"

    if agent.name != "main":
        body += f"\nFollow the main agent({team.team_name})'s instructions and report results.\n"
    else:
        body += f"\nDirect other agents and synthesize results.\n"
        teammate_names = [a.name for a in team.agents if a.name != "main"]
        body += f"Teammates: {', '.join(teammate_names)}\n"

    body += "\n### Collaborating Teams\n\n"
    for other_team in all_teams:
        if other_team.team_name == team.team_name:
            continue
        body += f"- **{other_team.team_name}**: {other_team.description}\n"

    body += "\n## Collaboration Rules\n\n"
    body += "**You are a single-turn agent.** Each message = one turn. Do your work, respond, done.\n\n"
    body += "**Delegation Decision:**\n"
    body += "```\n"
    body += "Is it within your expertise?\n"
    body += "  ├─ YES → Can you do it alone?\n"
    body += "  │        ├─ YES → Do it, provide result\n"
    body += "  │        └─ NO  → Ask teammate for help\n"
    body += "  └─ NO  → State what needs to be done and by whom\n"
    body += "```\n\n"
    body += "**When delegating to another team:**\n"
    body += "- State what needs to be done\n"
    body += "- Specify which team should do it\n"
    body += "- Provide all necessary context\n\n"
    body += "**Completion Rules:**\n"
    body += "- NEVER stop without completing the full task\n"
    body += "- If blocked, clearly state what you need and from whom\n"
    body += "- If other teams need to act, specify what needs to happen next\n"

    if agent.collaboration_notes:
        body += "\n### Your Role-Specific Collaboration Notes\n\n"
        body += agent.collaboration_notes + "\n"

    body += "\n## Delegation Format\n\n"
    body += "When delegating to another team, use this format:\n\n"
    body += "```\n"
    body += "From: {your_team_name}\n"
    body += "Task: {clear description of what needs to be done}\n"
    body += "Context: {relevant background and constraints}\n"
    body += "Expected Output: {what deliverable or answer you need}\n"
    body += "Priority: {urgent / high / normal / low}\n"
    body += "```\n\n"
    body += "**Example:**\n"
    body += "```\n"
    body += "From: dev\n"
    body += "Task: Review authentication module for security vulnerabilities\n"
    body += "Context: OAuth2 login flow at /shared/auth/oauth2.py. Concerned about token refresh and CSRF.\n"
    body += "Expected Output: Security review report with severity ratings and fix recommendations.\n"
    body += "Priority: high\n"
    body += "```\n"

    body += "\n## Communication Style\n\n"
    if agent.communication_style:
        body += f"Your communication style: {agent.communication_style}\n\n"
    body += "- Professional but approachable\n"
    body += "- Direct and concise\n"
    body += "- Solution-oriented\n"
    body += "- Use headers for structure, bullet points for lists, code blocks for code\n"

    body += "\n## Escalation Rules\n\n"
    if agent.escalation_triggers:
        body += "**Your specific escalation triggers:**\n"
        for trigger in agent.escalation_triggers:
            body += f"- {trigger}\n"
        body += "\n"
    body += "**General triggers:** Blocked > 2 turns, security vulnerability, data loss risk, production affected.\n\n"
    body += "**How to escalate:** Describe issue, explain impact, list what you tried, specify what you need.\n"

    body += "\n## Failure Handling\n\n"
    body += "**When a team doesn't respond:** Wait for next turn. If still no response after 2 tries, do it yourself (if within expertise) or report blockage.\n\n"
    body += "**When you receive an error:** Fix it if within expertise. Otherwise, delegate with full error message and what you tried.\n\n"
    body += "**When you cannot complete:** NEVER fake an answer. Report EXACTLY what failed, what you tried, and what you need.\n\n"
    body += "**Anti-Cascade Rule:** If a task was delegated to you, do NOT re-delegate to a third team. Report back to the delegating team.\n"

    body += "\n## Quality Checklist\n\n"
    body += "Before finishing, verify:\n"
    body += "- [ ] All requirements addressed\n"
    body += "- [ ] No placeholder content\n"
    body += "- [ ] Facts verified, code tested\n"
    body += "- [ ] Output is well-structured\n"
    body += "- [ ] Correct teams informed (if needed)\n"
    body += "- [ ] Files saved to `/shared/` (if cross-team)\n"

    body += "\n## Output Storage\n\n"
    body += "**`/data/`** - PRIVATE (your team only). Other teams cannot access.\n"
    body += "**`/shared/`** - SHARED (all teams). Use for cross-team collaboration.\n\n"
    body += "**Rule:** If another team needs to see it → `/shared/`. Otherwise → `/data/`.\n"

    body += "\n## Calling Rules\n\n"
    body += "**When you need another team to do something:**\n"
    body += "- Clearly state what needs to be done\n"
    body += "- Specify which team should do it\n"
    body += "- Provide all necessary context\n\n"
    body += "**Examples:**\n"
    body += "- 'The security team should review the authentication implementation at /shared/auth/login.py.'\n"
    body += "- 'The dev team needs to fix the login bug at /shared/auth/login.py.'\n"
    body += "- 'The design team should create a mobile-friendly login page mockup.'\n\n"

    body += "\n## Decision Transparency\n\n"
    body += "When finishing a task or delegating, explain:\n"
    body += "- **What you decided** (and what you decided NOT to do)\n"
    body += "- **Why** (especially if you delegated or chose not to)\n"
    body += "- **What the next step should be** (if any)\n\n"

    body += "## Coordination Efficiency\n\n"
    body += "- **Verify a task genuinely requires another team's expertise** before asking. If you can do it yourself in reasonable time, do it.\n"
    body += "- **Token budget awareness:** Every message to another team consumes tokens. Prefer doing simple tasks yourself.\n"
    body += "- **Batch related requests** into a single message instead of multiple separate messages.\n"

    body += "\n## Success Criteria\n\n"
    body += "- All acceptance criteria met\n"
    body += "- Quality standards upheld\n"
    body += "- No regressions introduced\n"
    body += "- Stakeholders informed\n"
    body += "- Lessons documented\n\n"

    if agent.quality_criteria:
        body += "**Your Quality Criteria:**\n"
        for criterion in agent.quality_criteria:
            body += f"- {criterion}\n"
        body += "\n"

    domain_section = _render_domain_sections(team.team_name)
    if domain_section:
        body += domain_section

    if agent.wiki_namespace:
        body += "\n## Knowledge Management (Wiki)\n\n"
        body += "You have access to a persistent wiki system for cross-session memory.\n\n"
        body += "**When to use:**\n"
        body += "- `wiki_record`: Save important findings, decisions, or learnings\n"
        body += "- `wiki_search`: Retrieve previously saved knowledge\n\n"
        body += "**Format:**\n"
        body += '```\n'
        body += 'wiki_record("""## Finding: [title]\\n\\n**Details**: ...""")\n'
        body += 'wiki_search("query")\n'
        body += '```\n\n'
        body += f"**Your Wiki Namespace:** `{agent.wiki_namespace}`\n\n"
        body += "**Memory Patterns:**\n"
        body += "- Session Start: Search for context, decisions, blockers\n"
        body += "- During Work: Record findings, decisions, search related work\n"
        body += "- Session End: Record results, open questions, recommendations\n"

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

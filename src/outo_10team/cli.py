from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import click
import httpx
from rich.console import Console
from rich.table import Table

from . import __version__


def _get_containerfile_path() -> Path:
    from importlib.resources import files
    return Path(str(files("outo_10team") / "Containerfile"))


console = Console()


def _resolve_team_name(team_name: str, config) -> tuple[str, str]:
    teams = config.team_names
    for default, custom in teams.items():
        if team_name == custom or team_name == default:
            return custom, default
    return team_name, team_name


@click.group()
@click.version_option(version=__version__, prog_name="outo-10team")
@click.option("--config-dir", type=click.Path(), default=None, help="Custom config directory")
@click.pass_context
def cli(ctx: click.Context, config_dir: str | None) -> None:
    ctx.ensure_object(dict)
    ctx.obj["config_dir"] = Path(config_dir) if config_dir else None


@cli.command()
@click.option("--provider-url", help="OpenAI-compatible API base URL")
@click.option("--api-key", help="API key for provider")
@click.option("--model", help="Default model name")
@click.option("--chatserver-url", help="Chatserver URL")
@click.option("--workspace-id", help="Workspace ID (required)")
@click.option("--bot-password", help="Bot password for all teams")
@click.option("--mem-limit", default="512m", help="Memory limit per container")
@click.option("--cpu-shares", default=512, type=int, help="CPU shares per container")
@click.option("--pids-limit", default=100, type=int, help="PID limit per container")
@click.option("--skip-team-names", is_flag=True, help="Use default team names without prompting")
@click.pass_context
def setup(ctx: click.Context, **kwargs) -> None:
    from .agents.generator import generate_all_team_agents
    from .agents.registry import DEFAULT_TEAM_CONFIGS, create_teams
    from .chatserver.client import ChatserverClient
    from .config.manager import ConfigManager
    from .config.schema import AppConfig, ChatserverConfig, ContainerConfig, ProviderConfig

    config_mgr = ConfigManager(ctx.obj.get("config_dir"))

    existing = None
    if config_mgr.exists():
        existing = config_mgr.load()
        console.print("[dim]Existing config found. Updating...[/dim]")

    flags = {k: v for k, v in kwargs.items() if v is not None and v is not False}

    def _get_value(
        flag_name: str,
        prompt_text: str,
        default_val: str | int | None = None,
        required: bool = False,
    ) -> str | int:
        if flag_name in flags:
            return flags[flag_name]
        if existing:
            attr_map = {
                "provider_url": "base_url",
                "model": "default_model",
                "chatserver_url": "url",
            }
            attr_name = attr_map.get(flag_name, flag_name.replace("-", "_"))
            existing_val = getattr(
                existing.provider if flag_name in ("provider_url", "api_key", "model")
                else existing.chatserver if flag_name in ("chatserver_url", "workspace_id", "bot_password")
                else existing.containers,
                attr_name,
                None,
            )
            if existing_val is not None and existing_val != "":
                default_val = existing_val
        if required and not default_val:
            val = click.prompt(prompt_text)
            if not val:
                console.print(f"[red]Error: {prompt_text} is required.[/red]")
                sys.exit(1)
            return val
        return click.prompt(prompt_text, default=default_val)

    base_url = _get_value("provider_url", "OpenAI-compatible API base URL", "http://localhost:11434/v1")
    api_key = _get_value("api_key", "API key", "")
    model = _get_value("model", "Default model", "gpt-4o")
    chatserver_url = _get_value("chatserver_url", "Chatserver URL", "http://localhost:18279")
    bot_password = _get_value("bot_password", "Bot password for all teams", "outo-10team-bot-2026")
    workspace_id = _get_value("workspace_id", "Workspace ID", "", required=True)
    mem_limit = _get_value("mem_limit", "Memory limit per container", "512m")
    cpu_shares = int(_get_value("cpu_shares", "CPU shares", 512))
    pids_limit = int(_get_value("pids_limit", "PID limit", 100))

    team_names: dict[str, str] = {}
    if existing and existing.team_names:
        team_names = dict(existing.team_names)

    if not kwargs.get("skip_team_names"):
        console.print("\n[bold]Team Names[/bold]")
        console.print("[dim]Press Enter to keep the default name, or type a custom name.[/dim]\n")

        for default_name, description, _ in DEFAULT_TEAM_CONFIGS:
            current = team_names.get(default_name, default_name)
            custom = click.prompt(f"  {description}", default=current)
            if custom and custom != default_name:
                team_names[default_name] = custom

    for default_name, custom_name in team_names.items():
        if len(custom_name) < 3:
            console.print(
                f"[red]Error: Team name '{custom_name}' (for {default_name}) "
                "is too short. Must be at least 3 characters.[/red]"
            )
            sys.exit(1)

    teams = create_teams(team_names)

    app_config = AppConfig(
        provider=ProviderConfig(base_url=base_url, api_key=api_key, default_model=model),
        chatserver=ChatserverConfig(url=chatserver_url, bot_password=bot_password, workspace_id=workspace_id),
        containers=ContainerConfig(mem_limit=mem_limit, cpu_shares=cpu_shares, pids_limit=pids_limit),
        team_names=team_names,
    )

    config_mgr.save(app_config)
    console.print(f"\n[green]Config saved to {config_mgr.config_path}[/green]")

    console.print("\n[bold]Registering bot accounts on chatserver...[/bold]\n")
    client = ChatserverClient(chatserver_url)

    registered = 0
    for team in teams:
        try:
            client.register(team.team_name, bot_password)
            console.print(f"  [green]+[/green] Registered: {team.team_name}")
            registered += 1
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json().get("detail", "")
                if isinstance(detail, list):
                    detail = "; ".join(str(d) for d in detail)
            except Exception:
                detail = ""
            if "already exists" in detail.lower():
                console.print(f"  [dim]~[/dim] Already exists: {team.team_name}")
            else:
                console.print(f"  [red]![/red] Failed to register {team.team_name}: {detail or e}")
        except Exception as e:
            console.print(f"  [red]![/red] Failed to register {team.team_name}: {e}")

    console.print(f"\n[green]Registered {registered} bot accounts[/green]")

    console.print(f"\n[bold]Joining workspace {workspace_id}...[/bold]\n")
    joined = 0
    for team in teams:
        try:
            client.login(team.team_name, bot_password)
            client.join_workspace(workspace_id)
            console.print(f"  [green]+[/green] Joined: {team.team_name}")
            joined += 1
        except Exception as e:
            console.print(f"  [dim]~[/dim] {team.team_name}: {e}")
    console.print(f"\n[green]{joined} teams joined workspace[/green]")

    console.print("\n[bold]Generating agent definitions...[/bold]\n")
    agents_dir = config_mgr.config_dir / "agents"
    generate_all_team_agents(teams, agents_dir, provider="default", model=model)
    console.print(f"[green]Agent definitions generated in {agents_dir}[/green]")

    console.print("\n[bold cyan]Setup complete![/bold cyan]")
    console.print("\nNext steps:")
    console.print("  1. Start outo-chatserver (if not running)")
    console.print("  2. Run: [bold]outo-10team run[/bold]")


@cli.command()
@click.pass_context
def run(ctx: click.Context) -> None:
    from .agents.registry import create_teams
    from .chatserver.client import ChatserverClient
    from .config.manager import ConfigManager
    from .containers.manager import ContainerManager

    config_mgr = ConfigManager(ctx.obj.get("config_dir"))
    if not config_mgr.exists():
        console.print("[red]No config found. Run: outo-10team setup[/red]")
        sys.exit(1)

    config = config_mgr.load()

    if not config.chatserver.workspace_id:
        console.print("[red]No workspace ID configured. Run: outo-10team setup[/red]")
        sys.exit(1)

    teams = create_teams(config.team_names)

    console.print("[bold]Connecting to Podman...[/bold]")
    cm = ContainerManager()
    cm.connect()

    console.print("[bold]Cleaning up existing containers...[/bold]\n")
    existing = cm.list_outo_containers()
    if existing:
        for c in existing:
            console.print(f"  [yellow]-[/yellow] Removing: {c['name']}")
            try:
                cm.remove_container(c["id"], force=True)
            except Exception as e:
                console.print(f"  [dim]~[/dim] Failed to remove {c['name']}: {e}")
        console.print()

    console.print("[bold]Creating network...[/bold]")
    cm.create_network()

    console.print("[bold]Logging in to chatserver...[/bold]\n")
    client = ChatserverClient(config.chatserver.url)

    logged_in_teams: list[str] = []
    for team in teams:
        try:
            client.login(team.team_name, config.chatserver.bot_password)
            logged_in_teams.append(team.team_name)
            console.print(f"  [green]+[/green] Logged in: {team.team_name}")
        except Exception as e:
            console.print(f"  [red]![/red] Failed to login {team.team_name}: {e}")

    if not logged_in_teams:
        console.print("[red]No teams could log in. Check chatserver.[/red]")
        sys.exit(1)

    workspace_id = config.chatserver.workspace_id

    for team_name in logged_in_teams:
        try:
            client.login(team_name, config.chatserver.bot_password)
            client.join_workspace(workspace_id)
            console.print(f"  [green]+[/green] {team_name} joined workspace")
        except Exception as e:
            console.print(f"  [dim]~[/dim] {team_name}: {e}")

    console.print("\n[bold]Preparing container configurations...[/bold]\n")

    agents_dir = config_mgr.config_dir / "agents"
    skills_dir = Path.home() / ".agents" / "skills"
    data_base_dir = config_mgr.config_dir / "data"
    shared_dir = config_mgr.config_dir / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    if skills_dir.exists():
        console.print(f"  [dim]Skills directory found: {skills_dir}[/dim]")
    else:
        console.print(f"  [dim]No skills directory found at {skills_dir}[/dim]")
    console.print(f"  [dim]Shared directory: {shared_dir}[/dim]")

    container_configs: list[dict] = []

    for team in teams:
        if team.team_name not in logged_in_teams:
            continue

        agent_configs: dict[str, str] = {}
        team_agents_dir = agents_dir / team.team_name
        if team_agents_dir.exists():
            for md_file in team_agents_dir.glob("*.md"):
                agent_configs[md_file.stem] = md_file.read_text()

        watcher_config = {
            "agent_name": team.team_name,
            "chatserver_url": config.chatserver.url,
            "workspace_id": workspace_id,
            "password": config.chatserver.bot_password,
            "provider": {
                "base_url": config.provider.base_url,
                "api_key": config.provider.api_key,
                "default_model": config.provider.default_model,
            },
            "agent_configs": agent_configs,
            "wiki": {
                "enabled": config.wiki.enabled,
                "provider": config.wiki.provider or config.provider.default_model,
                "model": config.wiki.model or config.provider.default_model,
                "api_key": config.wiki.api_key or config.provider.api_key,
                "base_url": config.wiki.base_url or config.provider.base_url,
                "debug": config.wiki.debug,
            },
        }

        team_data_dir = data_base_dir / team.default_name
        team_data_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"  [dim]Data directory: {team_data_dir}[/dim]")

        cfg: dict[str, Any] = {
            "name": team.team_name,
            "slug": team.default_name,
            "image": "outo-10team:latest",
            "watcher_config": watcher_config,
            "agent_configs": agent_configs,
            "mem_limit": config.containers.mem_limit,
            "cpu_shares": config.containers.cpu_shares,
            "pids_limit": config.containers.pids_limit,
            "data_dir": team_data_dir,
            "shared_dir": shared_dir,
        }
        if skills_dir.exists():
            cfg["skills_dir"] = skills_dir

        if config.wiki.enabled:
            wiki_dir = shared_dir / "wiki"
            wiki_dir.mkdir(parents=True, exist_ok=True)
            cfg["wiki_dir"] = wiki_dir
            console.print(f"  [dim]Wiki directory: {wiki_dir}[/dim]")

        container_configs.append(cfg)

    console.print("[bold]Starting containers...[/bold]\n")

    for cfg in container_configs:
        try:
            container = cm.create_container(**cfg)
            cm.start_container(container.id)
            console.print(f"  [green]+[/green] Started: {cfg['name']} ({container.id[:12]})")
        except Exception as e:
            console.print(f"  [red]![/red] Failed {cfg['name']}: {e}")

    console.print(f"\n[bold green]All {len(container_configs)} teams are running![/bold green]")
    console.print("\nCommands:")
    console.print("  outo-10team status    - Check container status")
    console.print("  outo-10team logs TEAM - View team logs (custom or default name)")
    console.print("  outo-10team stop      - Stop all containers")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    from .containers.manager import ContainerManager

    cm = ContainerManager()
    cm.connect()

    containers = cm.list_outo_containers()

    table = Table(title="Team Containers")
    table.add_column("Name", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Team")

    for c in containers:
        status_style = "green" if c["status"] == "running" else "red"
        table.add_row(c["name"], f"[{status_style}]{c['status']}[/{status_style}]", c.get("team", "N/A"))

    console.print(table)


@cli.command()
@click.argument("team_name")
@click.option("--lines", "-n", default=50, type=int, help="Number of log lines")
@click.pass_context
def logs(ctx: click.Context, team_name: str, lines: int) -> None:
    from .config.manager import ConfigManager
    from .containers.manager import ContainerManager

    config_mgr = ConfigManager(ctx.obj.get("config_dir"))
    if not config_mgr.exists():
        console.print("[red]No config found.[/red]")
        sys.exit(1)

    config = config_mgr.load()
    custom, default = _resolve_team_name(team_name, config)
    slug = default

    cm = ContainerManager()
    cm.connect()

    container = cm.get_container(f"outo10team-{slug}")
    if not container:
        console.print(f"[red]Container not found: outo10team-{slug}[/red]")
        sys.exit(1)

    for line in container.logs(tail=lines, stream=True):
        click.echo(line.decode().rstrip())


@cli.command()
@click.pass_context
def stop(ctx: click.Context) -> None:
    from .containers.manager import ContainerManager

    cm = ContainerManager()
    cm.connect()

    count = cm.cleanup_all()
    console.print(f"[green]Stopped and removed {count} containers[/green]")


@cli.command()
@click.pass_context
def build(ctx: click.Context) -> None:
    from .containers.manager import ContainerManager

    containerfile_path = _get_containerfile_path()
    if not containerfile_path.exists():
        console.print(f"[red]Containerfile not found at {containerfile_path}[/red]")
        sys.exit(1)

    console.print(f"[dim]Using Containerfile: {containerfile_path}[/dim]")
    console.print("[bold]Building Podman image...[/bold]")
    cm = ContainerManager()
    cm.build_image(containerfile_path)
    console.print("[green]Build complete: outo-10team:latest[/green]")


@cli.group()
def skill() -> None:
    """Manage skills in team containers."""
    pass


@skill.command("sync")
@click.argument("team_name", required=False)
@click.pass_context
def skill_sync(ctx: click.Context, team_name: str | None) -> None:
    from .config.manager import ConfigManager
    from .containers.manager import ContainerManager

    config_mgr = ConfigManager(ctx.obj.get("config_dir"))
    if not config_mgr.exists():
        console.print("[red]No config found.[/red]")
        sys.exit(1)

    config = config_mgr.load()

    skills_dir = Path.home() / ".agents" / "skills"
    if not skills_dir.exists():
        console.print(f"[red]Skills directory not found: {skills_dir}[/red]")
        sys.exit(1)

    cm = ContainerManager()
    cm.connect()

    if team_name:
        custom, default = _resolve_team_name(team_name, config)
        slug = default
        container = cm.get_container(f"outo10team-{slug}")
        if not container:
            console.print(f"[red]Container not found: outo10team-{slug}[/red]")
            sys.exit(1)
        try:
            cm.sync_skills(container.id, skills_dir)
            console.print(f"[green]Synced skills to {custom or default}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to sync skills to {custom or default}: {e}[/red]")
            sys.exit(1)
    else:
        containers = cm.list_outo_containers()
        if not containers:
            console.print("[yellow]No running team containers found.[/yellow]")
            sys.exit(0)

        for c in containers:
            try:
                cm.sync_skills(c["id"], skills_dir)
                console.print(f"  [green]+[/green] Synced skills to {c.get('team', c['name'])}")
            except Exception as e:
                console.print(f"  [red]![/red] Failed to sync skills to {c.get('team', c['name'])}: {e}")

        console.print("[green]Skill sync complete![/green]")

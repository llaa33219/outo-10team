<p align="center">
  <img src="logo.svg" alt="outo-10team" width="200">
</p>

<h1 align="center">outo-10team</h1>

<p align="center">
  Orchestrate 10 AI agent teams in isolated Podman containers, communicating via <a href="https://github.com/llaa33219/outo-chatserver">outo-chatserver</a>
</p>

<p align="center">
  <a href="https://pypi.org/project/outo-10team/"><img src="https://img.shields.io/pypi/v/outo-10team" alt="PyPI"></a>
  <a href="https://github.com/llaa33219/outo-10team/blob/main/LICENSE"><img src="https://img.shields.io/github/license/llaa33219/outo-10team" alt="License"></a>
  <a href="https://github.com/llaa33219/outo-10team"><img src="https://img.shields.io/github/stars/llaa33219/outo-10team?style=social" alt="GitHub Stars"></a>
</p>

---

## Features

- **10 Specialized AI Teams** — Each team has a dedicated role (leader, research, dev, design, etc.)
- **Powered by [outo-agentcore](https://pypi.org/project/outo-agentcore/)** — Each container runs `outo-agentcore` as the agent runtime, handling LLM interactions, tool execution, and agent orchestration
- **Isolated Containers** — Each team runs in its own Podman container with resource limits
- **Chatserver Integration** — Teams communicate through [outo-chatserver](https://github.com/llaa33219/outo-chatserver)
- **OpenAI-Compatible** — Works with any OpenAI-compatible API (OpenAI, Ollama, vLLM, etc.)
- **Custom Team Names** — Rename teams to match your workflow
- **Skill Sync** — Sync agent skills from host to containers

## Prerequisites

- Python 3.11+
- [Podman](https://podman.io/) installed and running
- [outo-chatserver](https://github.com/llaa33219/outo-chatserver) running
- An OpenAI-compatible API endpoint

## Installation

```bash
pip install outo-10team
```

## Quick Start

### 1. Setup

Run the interactive setup wizard:

```bash
outo-10team setup
```

You'll be prompted for:

| Prompt | Description | Default |
|--------|-------------|---------|
| API base URL | OpenAI-compatible endpoint | `http://localhost:11434/v1` |
| API key | Authentication key (leave empty for local) | *(empty)* |
| Default model | Model name to use | `gpt-4o` |
| Chatserver URL | outo-chatserver address | `http://localhost:18279` |
| Bot password | Shared password for all team bots | `outo-10team-bot-2026` |
| Workspace ID | **(required)** Chatserver workspace to join | — |

You can also provide values via flags:

```bash
outo-10team setup \
  --provider-url http://localhost:11434/v1 \
  --api-key sk-xxx \
  --model gpt-4o \
  --chatserver-url http://localhost:18279 \
  --workspace-id my-workspace \
  --bot-password my-secret \
  --skip-team-names
```

### 2. Build Container Image

```bash
outo-10team build
```

Builds the Podman image (`outo-10team:latest`) used by all team containers.

### 3. Run All Teams

```bash
outo-10team run
```

Starts all 10 team containers and joins them to the configured workspace.

## Commands

### `outo-10team setup`

Configure LLM provider, chatserver connection, and team names.

```bash
outo-10team setup [OPTIONS]

Options:
  --provider-url TEXT    OpenAI-compatible API base URL
  --api-key TEXT         API key for provider
  --model TEXT           Default model name
  --chatserver-url TEXT  Chatserver URL
  --workspace-id TEXT    Workspace ID (required)
  --bot-password TEXT    Bot password for all teams
  --mem-limit TEXT       Memory limit per container [default: 512m]
  --cpu-shares INT       CPU shares per container [default: 512]
  --pids-limit INT       PID limit per container [default: 100]
  --skip-team-names      Use default team names without prompting
  --help                 Show this message and exit.
```

### `outo-10team build`

Build the Podman container image from the bundled Containerfile.

```bash
outo-10team build
```

### `outo-10team run`

Start all team containers. Cleans up existing containers first, then creates fresh ones.

```bash
outo-10team run
```

### `outo-10team status`

Display a table showing the status of all team containers.

```bash
outo-10team status
```

Example output:

```
┌──────────────┬─────────┬──────────┐
│ Name         │ Status  │ Team     │
├──────────────┼─────────┼──────────┤
│ outo10team-main    │ running │ main     │
│ outo10team-research│ running │ research │
│ ...          │         │          │
└──────────────┴─────────┴──────────┘
```

### `outo-10team logs TEAM`

Stream logs from a specific team container. Accepts either the default or custom team name.

```bash
outo-10team logs TEAM [OPTIONS]

Arguments:
  TEAM          Team name (e.g., "main", "research", or your custom name)

Options:
  -n, --lines INT  Number of log lines to show [default: 50]
  --help           Show this message and exit.
```

Examples:

```bash
# View last 50 lines from the dev team
outo-10team logs dev

# View last 200 lines from the research team
outo-10team logs research -n 200
```

### `outo-10team stop`

Stop and remove all outo-10team containers.

```bash
outo-10team stop
```

### `outo-10team skill sync`

Sync agent skills from the host (`~/.agents/skills/`) to running containers.

```bash
outo-10team skill sync [TEAM]

Arguments:
  TEAM  Optional. Sync to a specific team only. Omit to sync all.
```

Examples:

```bash
# Sync skills to all running containers
outo-10team skill sync

# Sync skills to a specific team
outo-10team skill sync dev
```

### Global Options

```bash
outo-10team [OPTIONS] COMMAND [ARGS]...

Options:
  --version          Show version
  --config-dir PATH  Custom config directory (default: ~/.outo-10team/)
  --help             Show this message and exit.
```

## Architecture

```
Host Machine
├── ~/.outo-10team/
│   ├── config.json              # Main configuration
│   ├── agents/{teamname}/*.md   # Agent definitions
│   ├── data/{teamname}/         # Per-team persistent data
│   └── shared/                  # Shared data (wiki, etc.)
│
└── Podman (10 containers)
    ├── Arch Linux base image
    ├── outo-agentcore (agent runtime)
    │   ├── outoac CLI — runs agent inference via LLM
    │   ├── tool execution
    │   └── agent orchestration
    └── watcher.py (polls chatserver REST API → triggers outoac)
```

### How It Works

1. **watcher.py** runs inside each container, polling [outo-chatserver](https://github.com/llaa33219/outo-chatserver) for new messages
2. When a message arrives, the watcher invokes `outoac chat` (from [outo-agentcore](https://pypi.org/project/outo-agentcore/)) with the message and agent name
3. **outo-agentcore** processes the message using the configured LLM provider, executes any tools, and returns a response
4. The watcher sends the response back to chatserver

## Related Projects

| Project | Description |
|---------|-------------|
| [outo-agentcore](https://pypi.org/project/outo-agentcore/) | Agent runtime powering each container — handles LLM calls, tool use, and orchestration |
| [outo-chatserver](https://github.com/llaa33219/outo-chatserver) | Chat server that teams communicate through |

## Teams

| Default Name | Role | Description |
|--------------|------|-------------|
| `main` | Leader | Coordinator — orchestrates and delegates tasks |
| `research` | Research | Investigates topics, gathers information |
| `dev` | Development | Writes code, implements features |
| `design` | Design | UI/UX design, visual assets |
| `data` | Data | Data analysis, metrics, insights |
| `security` | Security | Security audits, vulnerability checks |
| `infra` | Infra/DevOps | Infrastructure, deployment, CI/CD |
| `qa` | QA | Quality assurance, testing |
| `docs` | Docs | Documentation, guides, API references |
| `support` | Support | Customer support, issue triage |

## Configuration

Configuration is stored at `~/.outo-10team/config.json`:

```json
{
  "provider": {
    "base_url": "http://localhost:11434/v1",
    "api_key": "",
    "default_model": "gpt-4o"
  },
  "chatserver": {
    "url": "http://localhost:18279",
    "bot_password": "outo-10team-bot-2026",
    "workspace_id": "my-workspace"
  },
  "containers": {
    "mem_limit": "512m",
    "cpu_shares": 512,
    "pids_limit": 100
  },
  "team_names": {}
}
```

## License

[Apache-2.0](LICENSE)

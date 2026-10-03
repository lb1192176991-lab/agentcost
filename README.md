# agentcost

[![CI](https://github.com/yunaremaia/agentcost/actions/workflows/ci.yml/badge.svg)](https://github.com/yunaremaia/agentcost/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/yunaremaia/agentcost/blob/main/LICENSE) [![Release](https://img.shields.io/github/v/release/yunaremaia/agentcost)](https://github.com/yunaremaia/agentcost/releases/latest) [![Stars](https://img.shields.io/github/stars/yunaremaia/agentcost)](https://github.com/yunaremaia/agentcost)

**Token usage tracker for multi-agent AI sessions.**

`agentcost` analyzes logs from AI coding agents (Claude Code, Codex CLI, OpenCode, Hermes) and calculates the real cost in tokens and USD. See how much each agent, session, and project costs — with monthly projections.

## Install

```bash
pip install git+https://github.com/yunaremaia/agentcost.git
```

> **Not on PyPI yet.** The distribution is named `agentcost-py` to avoid the
> short PyPI name `agentcost`, which belongs to a different project by a
> different author. The trusted-publisher upload is still pending, so install
> from Git for now — `pip install agentcost-py` does not resolve yet.

## Quick Start

```bash
agentcost init                  # guided setup (global config)
agentcost init --project        # guided setup (project-local .agentcost.toml)
```

On first run, `init` prompts for budget thresholds and creates the config file:

```
agentcost — Initialization

Daily budget (USD) [10.00]: 5.00
Weekly budget (USD) [50.00]: 25.00
Monthly budget (USD) [200.00]: 100.00

Config saved to /home/user/.agentcost/config.toml
  Daily: $5.00
  Weekly: $25.00
  Monthly: $100.00
```

## Usage

### Discover logs automatically

```bash
agentcost discover
```

### Everyday usage

```bash
agentcost today                              # today's usage summary
agentcost today --date 2026-09-14            # a specific day
agentcost week                               # last 7 days
agentcost week --days 30                     # last 30 days
agentcost cron                               # analyze Hermes cron costs
agentcost cron --job <job-id>                # a specific Hermes job
agentcost cron --json-output                 # machine-readable cron summary
```

`today` and `week` summarize calls, tokens, and estimated cost from discovered logs. `cron` groups Hermes cron output by job and estimates the cost of its recent runs.

### Analyze a log file

```bash
agentcost analyze ~/.claude/projects/my-session.jsonl --agent claude --period daily
```

## Budget & Compare

### Spending budgets

```bash
agentcost budget set --daily 10 --weekly 50 --monthly 200
agentcost budget show
agentcost budget check
agentcost budget check --quiet
agentcost budget check --sarif
```

`budget check` exits with `0` when configured thresholds are satisfied and `1` when a threshold is exceeded, no budget is configured, or another check failure occurs. `--quiet` is useful for scripts, while `--sarif` emits SARIF 2.1.0 for CI integrations.

### Compare agents

```bash
agentcost compare --period daily                  # terminal table
agentcost compare --period weekly --format json   # structured output
agentcost compare --period monthly --format markdown > report.md
```

Comparison periods are `daily`, `weekly`, and `monthly`. Output formats are `cli` (default), `json`, and `markdown`; `--quiet` selects JSON output for scripting.

### Set budgets

```bash
agentcost budget set --daily 10.0 --weekly 50.0 --monthly 200.0
agentcost budget check
agentcost budget show
```

Check if spending exceeds threshold today:

```bash
agentcost alert --threshold 5.0
```

### Example output

```
╭──────────────────────────────────────────────────────────────╮
│ agentcost v0.3.0 — 42 calls                                  │
│ Total tokens: 156,230                                        │
│ Input: 98,400 | Output: 57,830                              │
│ Cache Read: 12,000 | Cache Write: 3,000                      │
│ Total cost: $0.8234                                          │
╰──────────────────────────────────────────────────────────────╯
```

## Features

- **Multi-agent**: Claude Code, Codex CLI, OpenCode, Hermes, Cursor
- **Zero config**: Discovers logs automatically
- **Rich output**: CLI tables, JSON, Markdown
- **SARIF 2.1.0**: GitHub Code Scanning integration for budget alerts
- **Cost-aware**: Cache read pricing (Anthropic: 90% discount)
- **Projections**: Monthly cost estimates based on recent usage

## GitHub Action

Use agentcost in CI with the repository's ready-made GitHub Action. See [GitHub Action usage](GITHUB_ACTION_USAGE.md) for workflow examples, alert thresholds, inputs, and exit codes.

## SARIF Output (GitHub Code Scanning)

Generate SARIF 2.1.0 output for GitHub Code Scanning integration:

```bash
agentcost budget check --daily 10 --weekly 50 --monthly 200 --sarif
agentcost alert --threshold 5.0 --sarif
```

GitHub Actions workflow:

```yaml
- name: Check budget
  run: agentcost budget check --daily 10 --sarif > agentcost.sarif

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: agentcost.sarif
```

SARIF output includes one rule per budget period (daily/weekly/monthly). When thresholds are exceeded, results are emitted at `error` level.

## Supported log formats

| Agent       | Log format          | Status |
|-------------|---------------------|--------|
| Claude Code | JSONL               | ✅     |
| Codex CLI   | JSONL               | ✅     |
| OpenCode    | JSONL               | ✅     |
| Hermes      | JSON/JSONL          | ✅     |
| Cursor      | JSONL               | ✅     |

## Hermes tool overhead estimates

Hermes tool-call prompt overhead estimates are defined in `TOOL_CALL_OVERHEAD_TOKENS` in `src/agentcost/hermes_output.py`. This dictionary is the canonical source for these estimates.

When Hermes adds a new tool, add its name and estimated token overhead to that dictionary. Unknown tools fall back to 100 tokens and emit a warning so missing entries are visible instead of silently using the default.

## Model pricing

Built-in pricing for Claude 3.x, GPT-4o, Gemini 1.5. Auto-fallback for unknown models.

## Security

Please report security vulnerabilities privately. See [SECURITY.md](SECURITY.md) for supported versions and reporting instructions.

If this tool is useful to you, a star helps other people find it.

## Related tools

- **[driftcheck](https://github.com/yunaremaia/driftcheck)** — detect version drift between docs and toolchain files
- **[taintrace](https://github.com/yunaremaia/taintrace)** — trace and inspect AI agent execution
- **[depscan](https://github.com/yunaremaia/depscan)** — scan dependencies across multiple ecosystems
- **[agent-guard](https://github.com/yunaremaia/agent-guard)** — enforce guardrails on AI agent tool calls

Part of a family of focused, single-purpose developer tools — each one does one thing
and does it well.

## License

MIT

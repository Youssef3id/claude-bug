# prowl — Claude-powered bug-hunting workspace

You drive. Claude is the brain. Files are the memory.

Claude reads your target brief, picks a hypothesis, fires requests through Burp, and writes findings — all inside a structured file tree that compounds knowledge across sessions.

---

## Requirements

| Tool | Purpose |
|------|---------|
| [Claude Code CLI](https://claude.ai/code) | The Claude agent that runs inside this workspace |
| Burp Suite (Community or Pro) | Proxy + MCP Server extension for active testing |
| Python 3.8+ | `prowl` CLI and corpus search |
| git, curl, gzip, zgrep | Standard shell tooling |

---

## Setup — Linux (native / WSL2)

### 1. Clone the repo

```bash
git clone git@github.com:Youssef3id/claude-bug.git ~/bughunt
cd ~/bughunt
```

### 2. Run the bootstrap script

```bash
./setup.sh
```

This will:
- Make `prowl` executable and symlink it to `~/.local/bin/prowl`
- Auto-detect or prompt for the redscan corpus (optional — needed for `prowl lookup`)
- Run smoke tests

Then reload your shell:

```bash
source ~/.bashrc   # or ~/.zshrc
prowl list
```

### 3. Install Claude Code

Follow the official docs at <https://docs.anthropic.com/claude-code>

```bash
npm install -g @anthropic-ai/claude-code
claude                     # opens the agent in the current directory
```

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Add that line to `~/.bashrc` or `~/.zshrc` so it persists.

---

## Setup — Windows (WSL2)

1. Install WSL2 with Ubuntu:
   ```powershell
   wsl --install -d Ubuntu
   ```
2. Open an Ubuntu terminal and follow the **Linux** steps above.
3. Run Burp Suite natively on Windows (it listens on `127.0.0.1:9876`). From WSL2, reach it via the Windows host IP:
   ```bash
   # Find the Windows host IP from inside WSL2
   cat /etc/resolv.conf | grep nameserver | awk '{print $2}'
   ```
   Then update `.mcp.json` (see below) — replace `127.0.0.1` with that IP.

---

## MCP Integration — Claude Code + Burp Suite

MCP (Model Context Protocol) lets Claude fire real HTTP requests through Burp, poll Collaborator, and push requests into Repeater — all without copy-pasting.

### Step 1: Install the Burp MCP Server extension

1. Open Burp Suite → **BApp Store** → search **MCP Server** → Install.
2. The extension listens on `http://127.0.0.1:9876` by default. Confirm in **Extensions → MCP Server → Config**.

### Step 2: Download the MCP proxy JAR

The JAR bridges Claude Code (stdio) to Burp's SSE endpoint:

```bash
mkdir -p ~/.BurpSuite/mcp-proxy
# Place the JAR here:
# ~/.BurpSuite/mcp-proxy/mcp-proxy-all.jar
```

The JAR is bundled with the BApp or available from the extension's GitHub releases page. After installing the BApp, check the **Output** tab in Burp for the exact download link.

### Step 3: Edit `.mcp.json`

The repo ships with `.mcp.json` pre-configured for a standard Linux Burp install. Edit it to match your paths:

```json
{
  "mcpServers": {
    "burp": {
      "command": "/home/YOU/BurpSuiteCommunity/jre/bin/java",
      "args": [
        "-jar",
        "/home/YOU/.BurpSuite/mcp-proxy/mcp-proxy-all.jar",
        "--sse-url",
        "http://127.0.0.1:9876"
      ]
    }
  }
}
```

Find your Burp JRE:

```bash
find ~/BurpSuite* -name java -type f 2>/dev/null | head -3
```

**WSL2 users:** replace `127.0.0.1` in `--sse-url` with the Windows host IP from Step 3 above.

### Step 4: Verify the connection

Start Burp (with MCP Server extension active), then open Claude Code in this directory:

```bash
cd ~/bughunt
claude
```

Claude Code auto-loads `.mcp.json`. Ask it:
> *"list the available MCP tools"*

You should see `get_proxy_http_history`, `send_http1_request`, `create_repeater_tab`, etc.

### Available Burp MCP tools

| Tool | What it does |
|------|-------------|
| `get_proxy_http_history` | Pull raw requests/responses from the proxy |
| `send_http1_request` / `send_http2_request` | Fire a request through Burp |
| `create_repeater_tab` | Push a request into Repeater for manual replay |
| `get_burp_collaborator_payload` | Get an OOB interaction URL |
| `poll_burp_collaborator` | Check if the payload was hit |
| `encode_decode` | Encoding utilities |

---

## Daily workflow

### New target

```bash
prowl init example.com
```

Then tell Claude:
> *"new target: example.com — recon-intake"*

Claude follows `prompts/recon-intake.md`, asks minimal questions, and writes `targets/example.com/brief.md`.

Or auto-brief from Burp history (fastest path):
> *"burp brief example.com"*

Claude pulls your proxy history for that host, extracts endpoints + auth model + parameters, and writes the brief + intel digest in one shot.

### Hunt

```bash
prowl hunt example.com   # prints the context bundle
```

Or just tell Claude:
> *"hunt example.com"*

Claude picks one goal → one hypothesis → fires requests through Burp → writes a finding only when reproducible.

### Inspect

```bash
prowl list               # all targets, finding count, last activity
prowl show example.com   # everything about one target
prowl lookup "ssrf aws"  # search CVEs + public writeups
```

---

## Workspace layout

```
~/bughunt/
  bin/prowl                  the CLI (on PATH after setup)
  templates/                 brief.md / memory.md / finding.md skeletons
  prompts/                   recon-intake.md, hunt-loop.md (Claude protocols)
  knowledge/
    portswigger-topics.md    index of 32 vuln-class playbooks
    techniques/<slug>.md     per-class playbooks (read before testing)
    by-stack/<stack>.md      stack-specific gotchas
    corpus/                  symlink → redscan corpus (CVEs, writeups, CWEs)
  targets/                   LOCAL ONLY — gitignored, never pushed
    <host>/brief.md          scope, accounts, goals, ground rules
    <host>/memory.md         append-only hunt log
    <host>/findings/         one file per real finding
    <host>/session.txt       cookies/headers
    <host>/intel/            operator-fed captures (Burp exports, notes)
  .mcp.json                  Burp MCP wiring — edit paths for your machine
  setup.sh                   one-shot bootstrap
  CHEAT.md                   operator command reference
  CLAUDE.md                  Claude's operating instructions (read this)
```

> **`targets/` is gitignored.** Your hunt data, findings, and session tokens stay on your machine only. The repo tracks playbooks, tooling, and protocols — not target intelligence.

---

## Realistic expectations

This is a force-multiplier, not an autonomous scanner. Per target: 1–3 hours of operator time → 0–5 quality findings. The `knowledge/` tree compounds across targets — that's where the leverage builds.

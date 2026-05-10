# prowl — bug-hunting workspace

You are the operator/brain for this workspace. Files in this tree are your
memory; everything you learn lives in `knowledge/` and accumulates across
sessions.

## Workspace layout
- `bin/prowl` — the CLI. On PATH.
- `templates/` — `brief.md`, `memory.md`, `finding.md` skeletons.
- `prompts/recon-intake.md` — protocol for new-target intake (start here on `new target:`).
- `prompts/hunt-loop.md` — iron rules for active hunting (scope/rate/evidence-only).
- `knowledge/portswigger-topics.md` — index of 32 vuln-class playbooks.
- `knowledge/techniques/<slug>.md` — per-class playbooks (read these before testing).
- `knowledge/by-stack/<stack>.md` — stack-specific gotchas (write new ones as you learn).
- `knowledge/corpus/` — symlink to `~/redscan/data/`: 24k CVEs, 23k bug-bounty/CTF writeups, 61k methodology entries, 1.4k CWEs (gzipped JSONL). Search via `prowl lookup`.
- `targets/<host>/` — one dir per target: `brief.md`, `memory.md`, `findings/NNN-slug.md`, `session.txt`, `log.jsonl`.
- `CHEAT.md` — operator's command cheat sheet.

## Intel-driven hunts (operator pre-recorded captures)
The operator can pre-feed you HTTP captures, Burp dumps as markdown, manual
notes, decompiled mobile-app constants — anything that documents what the
target already does.

**Two intake paths:**
- File-based: `prowl ingest <host> <file.md> [...]` copies into `targets/<host>/intel/`. The next `prowl hunt <host>` includes them in the bundle automatically.
- Inline-paste: operator pastes capture content in chat. Save it yourself: `targets/<host>/intel/captured-<iso-date>.md`, then proceed.

**When intel files are present, do this BEFORE picking any hunting goal:**
1. Read every file in `targets/<host>/intel/` end-to-end. They're truth — what
   the app actually does, not what you guessed.
2. Extract: endpoints + methods, auth model (cookie / JWT / OAuth flow), every
   parameter you see, hidden fields, response shapes (especially fields the UI
   doesn't show but the API returns), state-bearing tokens, anomalies (200 with
   error JSON, debug headers, internal IDs that look guessable).
3. Append a short "intel digest" block to `targets/<host>/memory.md`:
   ```
   ## <iso-date> — intel digest
   - endpoints observed: ...
   - auth: ...
   - interesting params/fields: ...
   - hypotheses worth testing: ... (3–5 max, ranked)
   ```
4. Cross-reference the brief's hunting goals with the digest. Pick the goal
   where intel + scope + payout overlap most.
5. THEN start the normal hunt-loop (one goal, one hypothesis, prove or kill).

## How to start a session

### `fill brief for <host> from this overview:` (brief-creation mode)
Triggered when the operator launched `prowl brief <host>` and pastes the
program overview/scope/OOS as their first message.

Steps:
1. Read the pasted text — extract: program platform (HackerOne/Bugcrowd/private),
   bounty range, in-scope assets, out-of-scope hosts, OOS vuln classes,
   ground rules ("no DDoS", "only your own accounts", etc.), known restrictions
   (recently removed assets, informative-only assets, etc.).
2. Overwrite `targets/<host>/brief.md` using the schema from `templates/brief.md`.
   Fill EVERY section. Where the overview doesn't say, write `unknown — to confirm with operator`.
3. Propose 2–4 prioritised hunting goals based on what's in scope + what
   typically pays well for this kind of program.
4. **Do not** run any active probing. Do not start hunting.
5. End with: `Brief written. Run \`bug\` and say \`hunt <host>\` when ready.`

### Default behaviour: user drops just a URL.
Auto-route based on the URL host:

1. **`*.web-security-academy.net`** (PortSwigger lab):
   - Fetch the page (`curl -sk <url> | head -200` or visit `<url>` to read the
     `<title>` / lab banner — that's the lab title).
   - Match the lab title to one of the 32 vuln classes; `cat knowledge/techniques/<class>.md`.
   - Drive the exploit yourself with `curl` (and Python where needed). One pass: confirm vuln → exploit → log in / submit / mark solved.
   - Report back: vuln class, technique used, payload, evidence the lab is `is-solved`.
   - DO NOT start a long recon process for a lab — labs are scoped to one bug; jump straight to the playbook.

2. **Any other URL** (real bounty target):
   - Treat as `new target: <host> — recon-intake`.
   - Follow `prompts/recon-intake.md`: ask the user 5 short questions (program URL, scope/OOS, accounts, prior intel) BEFORE doing anything active.
   - Then light passive recon (≤10 zero-impact requests), write `targets/<host>/brief.md`, propose 2–3 goals.
   - Stop and wait for the operator to say "hunt" before active testing.

### Explicit overrides (still work)
- `solve this lab: <title>\n<url>` — same as 1, but title is given.
- `new target: <host> — recon-intake` — force intake mode.
- `hunt <host>` — continue an existing target. Run `prowl hunt <host>` for the bundle, then follow `prompts/hunt-loop.md`. Report back in the fixed shape: Goal / Tested / Findings / Open questions / Next step.

## Corpus lookup — use BEFORE forming a hypothesis
The workspace ships with the redscan corpus (CVEs, public writeups, methodology, CWEs).
Whenever you have a target's stack/product/version or a candidate parameter name, run:

```
prowl lookup "<product or param> <bug-class>"     # search all sources
prowl lookup "<query>" -t writeup -n 10           # limit to writeups
prowl lookup "<query>" -t cve                     # CVE catalog
```

Read the top hits, extract concrete techniques (CVE numbers, payloads, paths)
that apply to your target, and only THEN form a hypothesis. This grounds
hunches in real, disclosed bugs instead of generic playbook theory.

## Iron rules (always)
- **Scope first.** Verify host/path is in `brief.md` scope before any request.
- **Never destructive against others.** No DELETE on real users' data, no
  password reset of real accounts, no payment, no exfil of real PII. All
  exploitation must hit accounts/data the operator controls.
- **Demonstrate impact, don't describe it.** On confirm, exploit it for real
  using operator-controlled accounts and capture exact request + response
  proving the effect. A finding without a working PoC + captured output is not
  a finding. Never write "an attacker could …" — write "I executed X and got Y".
  When the bug is cross-account, use a SECOND operator account as the victim.
- **Rate limit.** ≤ 5 req/sec/host, back off on 429.
- **Evidence over volume.** One reproducible bug > ten anomalies.
- **Token discipline.** Read only what's needed; summarize; never paste raw bodies.
- **Append to memory.** Each session block in `targets/<host>/memory.md`.
- **Knowledge compounds.** New technique discovered → write to `knowledge/techniques/<slug>.md`.

## Tooling
- `prowl init <host>` create target dirs.
- `prowl hunt <host>` print context bundle for the next session.
- `prowl note <host> "..."` append to memory.
- `prowl finding <host> <slug>` scaffold a finding file.
- `prowl learn --list` show playbook coverage.
- `prowl learn <slug>` open/scaffold a playbook.

## Burp MCP integration
The workspace has a Burp Suite MCP server wired in (`.mcp.json`). Burp must be
running with the **MCP Server** extension active (BApp Store → "MCP Server",
listens on `127.0.0.1:9876`).

### Available Burp MCP tools
- `get_proxy_http_history` — pull raw HTTP requests/responses from the proxy
- `send_http1_request` / `send_http2_request` — fire a raw request through Burp
- `create_repeater_tab` — push a request into Repeater for manual replay
- `get_burp_collaborator_payload` / `poll_burp_collaborator` — OOB interactions
- `encode_decode` — encoding utilities

### Auto-brief from Burp history (`burp brief <host>`)
When the operator says **`burp brief <host>`**:
1. Call `get_proxy_http_history` filtered to `<host>`.
2. Extract from the history:
   - All unique endpoints + HTTP methods observed
   - Auth mechanism (Cookie names, Authorization header shape, tokens)
   - Every query/body parameter seen
   - Interesting response fields (IDs, tokens, hidden fields, debug headers)
   - Anomalies (200 with error JSON, redirects to internal hosts, etc.)
3. Overwrite `targets/<host>/brief.md` using `templates/brief.md` — fill EVERY
   section from observed traffic. Mark anything not seen as `unknown — not observed in capture`.
4. Append an **intel digest** block to `targets/<host>/memory.md`:
   ```
   ## <iso-date> — burp history digest
   - requests captured: <count>
   - endpoints: ...
   - auth: ...
   - interesting params: ...
   - hypotheses: ... (3–5, ranked)
   ```
5. Report back: endpoints found, auth model inferred, top 3 hypotheses.

### During active hunts
- Prefer `send_http1_request` over curl when you need responses routed through
  Burp (so they appear in history and can be replayed).
- Use `create_repeater_tab` when handing a suspicious request to the operator
  for manual follow-up.
- Use `get_burp_collaborator_payload` for any SSRF / XXE / blind injection
  hypothesis; poll with `poll_burp_collaborator` after a short wait.

## When in doubt
- Re-read `CHEAT.md` and the relevant `knowledge/techniques/<slug>.md`.
- Ask the user before scope-adjacent or destructive actions.

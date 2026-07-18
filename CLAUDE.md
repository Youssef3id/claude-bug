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

2. **A WordPress plugin** (a local `*.zip`, a plugin directory, a
   `https://wordpress.org/plugins/<slug>/` page, or a `downloads.wordpress.org/...zip`
   link) — route to **WP plugin audit mode** below, NOT recon-intake.

3. **Any other URL** (real bounty target):
   - Treat as `new target: <host> — recon-intake`.
   - Follow `prompts/recon-intake.md`: ask the user 5 short questions (program URL, scope/OOS, accounts, prior intel) BEFORE doing anything active.
   - Then light passive recon (≤10 zero-impact requests), write `targets/<host>/brief.md`, propose 2–3 goals.
   - Stop and wait for the operator to say "hunt" before active testing.

### WP plugin source-code audit (`wphunt`)
The operator launches `wphunt` (= `prowl wphunt`, opens claude on **sonnet**) and
pastes a plugin as the next message. Trigger this route whenever the message is —
with or without an `audit:`/`wphunt`/`wpbug` prefix — a local plugin zip path, a
plugin directory, a `wordpress.org/plugins/<slug>` URL, or a direct `.zip` URL.

**This whole route must run on Sonnet.** Keep every step concrete and mechanical;
do not rely on Opus-only leaps. The instructions here + `prompts/code-audit.md`
are the full spec — follow them literally.

Steps (start IMMEDIATELY — no recon-intake, no 5 questions):

**STEP 0 — Gate 5 check BEFORE touching any code (do this first, takes 30 seconds):**
Run these two checks and STOP if either fails:
```
# Is the plugin still live and maintained?
curl -s "https://api.wordpress.org/plugins/info/1.2/?action=plugin_information&request[slug]=<slug>&request[fields][active_installs]=1&request[fields][last_updated]=1" | python3 -c "import sys,json; d=json.load(sys.stdin); print('installs:', d.get('active_installs',0), '| last_updated:', d.get('last_updated','?'), '| status:', d.get('error','live'))"
```
- If the API returns `{"error":"closed"}` or similar → **plugin is closed/removed → ABORT, tell the operator, pick a new target.**
- If `last_updated` is more than 3 years ago → **ABORT, out of scope per Gate 5.**
- Note the `active_installs` count — if < 100, CVSS floor becomes 8.5 (Gate 2).
- For non-wordpress.org sources (CodeCanyon, GitHub, vendor site) verify the plugin is still actively sold/maintained before proceeding.

**Only proceed to step 1 after Gate 5 passes.**

1. Run `prowl audit <input>` (it resolves zip/dir/URL, copies the source to
   `targets/<slug>/src/`, scans the attack surface, seeds `brief.md`, and writes
   `targets/<slug>/audit/{manifest.json,surface-map.md}`).
2. Read `targets/<slug>/audit/surface-map.md`. Skim `knowledge/wp-audit-rules.md`
   and **`knowledge/patchstack-rules.md`** (the scope/acceptance filter — apply it).
3. **Fan out the deep audit**: spawn one subagent per cluster (parallel, in one
   message), **each with `model: sonnet`**, following `prompts/code-audit.md` —
   read its files end-to-end, trace source→sink, emit JSONL leads. Agents return
   leads + summary only (no file dumps).
4. Aggregate returns into `targets/<slug>/audit/leads.jsonl`; dedupe; rank by
   confidence × severity. **Apply the Patchstack gates before promoting any lead**
   (`knowledge/patchstack-rules.md`): exploitable by unauth/Subscriber/Customer
   (Contributor only if CVSS ≥7.5; Admin+ = out); class on the accepted list;
   CVSS ≥6.5 (≥8.5 for low-install); reject AC:H; check novelty via `prowl lookup`
   + the Patchstack DB. Anything failing a gate is reported as out-of-scope context, not a lead.
5. Report back: ranked lead table (primitive, file:line, **min-role**, class,
   confidence, cvss_est, in-scope/oos). Separate the out-of-scope ones.
6. Frame every lead by the exploitable **primitive**, not the OWASP class.

**Verdict discipline — read this twice.** Everything this route produces is a
**candidate**, never a confirmed bug.
- Static analysis = a candidate. A successful **local** reproduction with a
  working PoC = still a candidate, NOT a confirmed bug. A local repro only proves
  the code path executes in *your* lab build — it does not prove the bug is
  exploitable on the real/production target, in scope, unpatched, or novel.
- So: run the PoC, capture the exact request/response as **evidence**, and report
  it factually ("I ran X locally and observed Y"). Do **not** write "this is a
  vulnerability / confirmed bug / exploitable". Label it `candidate` and state
  what still has to be checked (live target, config, version, prior disclosure).
- Only the operator promotes a candidate to a bug. Finding files created via
  `prowl finding <slug> <lead-slug>` stay `status: candidate` until the operator
  says otherwise — never auto-set `confirmed`.

If the launcher's priming message arrives first (`wphunt: …`), acknowledge audit
mode in one line and wait for the operator to paste the plugin.

### `wphunt --auto` — autonomous target selection (no operator input needed)
Triggered by `wphunt --auto` or `wpbug --auto`. Do NOT wait for the operator to
paste a plugin. Pick one yourself and start immediately.

**Selection algorithm (run every time — pick the best target that passes all gates):**

1. **Build a candidate list.** Use the WP.org API to find plugins with:
   - `active_installs` ≥ 10,000 (sweet spot: 10k–500k; high enough to matter, low enough to be under-audited)
   - `last_updated` within the last 12 months
   - Tag overlap with historically buggy categories: `booking`, `form`, `payment`, `upload`, `import`, `export`, `membership`, `crm`, `woocommerce`, `ajax`, `api`, `rest`
   - NOT in the already-audited dead-ends list (`knowledge/wp-audit-rules.md` or `targets/` dir)

   Useful WP.org API endpoints:
   ```bash
   # Browse by tag (e.g. "booking")
   curl -s "https://api.wordpress.org/plugins/info/1.2/?action=query_plugins&request[tag]=booking&request[per_page]=20&request[orderby]=active_installs&request[fields][active_installs]=1&request[fields][last_updated]=1"

   # Or browse by search term
   curl -s "https://api.wordpress.org/plugins/info/1.2/?action=query_plugins&request[search]=ajax+upload&request[per_page]=20&request[fields][active_installs]=1&request[fields][last_updated]=1"
   ```

2. **Gate 5 check each candidate** (same 30-second check as above). Skip any that are
   closed, abandoned (> 12 months no update), or already in `targets/`.

3. **Novelty pre-screen.** For the top 3 candidates, run:
   ```bash
   prowl lookup "<slug> sql injection" -t cve -n 3
   prowl lookup "<slug> sqli" -n 3
   ```
   Prefer plugins with **zero recent CVEs** (under-audited) over ones with a history
   of patches (likely already hardened or thoroughly picked over).

4. **Pick the winner.** Highest score on: `active_installs` weight × tag-risk weight ×
   novelty score (no recent CVEs = +1). Announce your choice in one line:
   `→ auto-selected: <slug> v<version> (<installs> installs, last updated <date>)`
   then proceed immediately to Step 0 → Step 1 without waiting.

5. **If all candidates fail** (all closed / all stale / all over-audited): try a
   different tag from the list above and repeat once. If still no good target, tell
   the operator: "No suitable target found for tags X,Y,Z — paste a specific plugin."

### `review <host> <slug>` — pre-submission report hardening
Triggered when the operator says `review <host> <slug>` (or pastes a finding path).

**This mode runs WITHOUT operator input.** Read the finding, attack it like a
triager, fix every weakness, rewrite the submission draft, and output `READY` or
`KILLED`. Do not ask questions mid-run.

Steps: follow `prompts/report-review.md` exactly.
- Read finding + brief.
- Run the full triager attack list for the detected bug class.
- For every "Live" attack: run the missing test, capture the output, fix the section.
- Re-score CVSS independently.
- Rewrite any "an attacker could" language to "I executed / I observed".
- Add "Triager FAQ" block covering the top 3 likely pushbacks.
- Update the finding file with new evidence + review-pass block.
- Output the final H1 draft + `READY` or `KILLED`.

Do not output `READY` until every attack in the checklist is explicitly dismissed.

### Explicit overrides (still work)
- `solve this lab: <title>\n<url>` — same as 1, but title is given.
- `new target: <host> — recon-intake` — force intake mode.
- `hunt <host>` — continue an existing target. Run `prowl hunt <host>` for the bundle, then follow `prompts/hunt-loop.md`. Report back in the fixed shape: Goal / Tested / Findings / Open questions / Next step.
- `audit <zip|dir|url>` / `wphunt <input>` / `wpbug <input>` — force WP plugin audit mode above.
- `wphunt --auto` / `wpbug --auto` — autonomous target selection, no input needed.

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

## BurpStrike active scanner
`prowl hunt <host>` auto-launches **BurpStrike** (an active DAST scanner at
`http://127.0.0.1:7332`) and inlines a live findings section into the bundle.
It covers reflected/DOM **XSS** (confirmed in a real headless browser), **open
redirect**, **path traversal**, and **CORS** misconfig — fed by everything you
browse through Burp (the burplens extension forwards proxy traffic to it).

- It scopes itself to `<host>` (fail-closed: it only fires at in-scope hosts).
- During a hunt, trigger and read it via the curls in the bundle's BurpStrike
  section (`POST /scan`, `GET /findings`, `POST /recon`, `POST /control/stop`).
- Its output is **CANDIDATES only** — confirm each with a real PoC + captured
  output before writing a finding, exactly like every other lead (iron rule 3).
- Disable for a run with `PROWL_BURPSTRIKE=0 prowl hunt <host>`.
- Complements the Burp MCP tools above: Burp MCP = manual/raw requests +
  collaborator; BurpStrike = automated param fuzzing + browser-confirmed XSS.

## When in doubt
- Re-read `CHEAT.md` and the relevant `knowledge/techniques/<slug>.md`.
- Ask the user before scope-adjacent or destructive actions.

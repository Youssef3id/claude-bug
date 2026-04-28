# Operator playbook — how to hunt a new bounty program

Repeat this for every program you take on. ~10–15 min of prep, then you let
Claude work.

## Step 1 — Initialise the target with the policy
1. Pick the program's primary host (e.g. `att.com`, `yahoo.com`, `redacted-co`).
2. Run:
   ```
   brief <host>
   ```
   Claude opens.
3. Paste the program policy as ONE message, exactly prefixed with:
   ```
   fill brief for <host> from this overview:
   <paste the entire policy: scope, OOS, ground rules, payouts>
   ```
4. Claude writes `~/bughunt/targets/<host>/brief.md` with your scope and OOS pre-filled, proposes 2–4 hunting goals, and stops. No probing.
5. Exit Claude (`/exit` or Ctrl-D).

## Step 2 — Browse the app yourself, capture interesting traffic
- Use Burp / Caido / browser DevTools. Walk every authenticated flow you'll be testing.
- Dump req/res that look suspicious (hidden fields, internal IDs, auth tokens, weird endpoints) into one or more markdown files. Format doesn't matter — Claude will read raw HTTP.
- Save to anywhere on disk; e.g. `~/captures/<program>/account-flow.md`.

## Step 3 — Ingest captures into the target
```
prowl ingest <host> <file1.md> <file2.md> [...]
```
Files land in `targets/<host>/intel/`. They become part of the hunt bundle automatically.

## Step 4 — Hunt
```
bug
> hunt <host>
```
Claude:
- Loads brief + memory + findings + intel + the 4 most-relevant playbooks
- Reads intel files end-to-end, writes an "intel digest" to `memory.md`
- Picks one goal from your brief, forms one hypothesis, tests it
- If confirmed → exploits it for real against your own accounts → captures proof → writes a finding file
- If not → notes the dead-end and moves on
- Reports back in fixed shape: Goal / Tested / Findings / Open questions / Next step

## Step 5 — Iterate
Each new session continues from `memory.md`. Drop more intel anytime with `prowl ingest`. New techniques you discover get written to `knowledge/techniques/` and apply to future programs automatically.

## Step 6 — Submit
Findings live at `~/bughunt/targets/<host>/findings/NNN-slug.md`. Each one is structured for direct submission (summary, repro, PoC with captured output, demonstrated impact, fix).

---

## Reference — every prowl subcommand
```
prowl init <host>             create target dirs (no chat)
prowl brief <host>            launch claude → paste policy → brief.md written
prowl ingest <host> <file>... copy capture files into intel/
prowl hunt <host>             print full context bundle (used by bug session)
prowl chat                    launch claude in workspace (alias: bug)
prowl note <host> "..."       quick append to memory.md
prowl finding <host> <slug>   scaffold a finding file
prowl list                    all targets, finding count, last activity
prowl show <host>             everything in one screen
prowl learn --list            show 32-playbook coverage
prowl learn <slug>            open/scaffold a playbook
```

## Aliases
- `bug` → `prowl chat` (open Claude in workspace, skip-permissions)
- `brief <host>` → `prowl brief <host>` (open Claude in brief-creation mode)

## Iron rules Claude follows in every hunt
1. Scope first. Verify host/path is in brief before any request.
2. Never destructive against real users — exploitation only on operator-controlled accounts.
3. Demonstrate impact, don't describe it. Real exploit + captured output for every finding.
4. Rate ≤5 req/sec/host, back off on 429.
5. Knowledge compounds — new techniques get written to knowledge/techniques/.

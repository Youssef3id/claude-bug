# prowl — cheat sheet

Workspace lives at `~/bughunt/`. Command is `prowl` (already on $PATH).

## start a target
```bash
prowl init example.com         # creates targets/example.com/{brief,memory,findings,session,log}
$EDITOR ~/bughunt/targets/example.com/brief.md   # fill the [TODO] blocks
```
Or, for guided intake — open Claude and say:
```
new target: example.com — recon-intake
```
Claude runs `prompts/recon-intake.md` and writes the brief for you.

## hunt
```bash
prowl hunt example.com         # prints the context bundle Claude needs
```
Or in chat: `hunt example.com` — Claude runs the bundle itself.

## quick ops
```bash
prowl note example.com "tested /api/v2/orders, no IDOR — uses uuid v7"
prowl finding example.com sqli-product-stock   # scaffolds findings/NNN-...md
prowl list                     # all targets, count, last activity
prowl show example.com         # everything in one screen
```

## file map
```
~/bughunt/
  bin/prowl                 the CLI
  templates/                brief.md / memory.md / finding.md skeletons
  prompts/recon-intake.md   how Claude does the intake interview
  prompts/hunt-loop.md      the iron rules (scope, rate, evidence-only)
  knowledge/techniques/     reusable playbooks per bug class
  knowledge/by-stack/       stack-specific gotchas
  targets/<host>/
    brief.md                scope, accounts, goals — single source of truth
    memory.md               append-only hunt log (one block per session)
    findings/NNN-slug.md    one file per real bug
    session.txt             cookies/headers (DO NOT COMMIT)
    log.jsonl               raw req/resp audit
```

## iron rules (Claude follows these — you should too)
- scope first; when unsure, ask
- never destructive (no delete, no password reset, no payment)
- ≤ 5 req/sec; back off on 429
- evidence over volume — one repro > ten hunches
- write a finding only when reproducible
- token-discipline: read only what's needed, summarize, never paste raw bodies

## name notes
- your `hunt` alias (in `.bashrc`) launches Claude with skip-permissions —
  that's untouched. `prowl hunt` is a SUBCOMMAND, no collision.
- if you ever want to type just `hunt example.com` for prowl, alias it explicitly:
  `alias prowl-hunt='prowl hunt'`

## one-line workflow
```bash
prowl init example.com && $EDITOR ~/bughunt/targets/example.com/brief.md && prowl hunt example.com
```

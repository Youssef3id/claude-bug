# prowl — file-based bug-hunting workspace

You drive. Claude is the brain. Files are the memory.

## Day-zero workflow

1. **New target:**
   ```
   prowl init example.com
   ```
   Open `~/bughunt/targets/example.com/brief.md` and fill the [TODO] blocks
   (scope, out-of-scope, accounts, goals). Or — open a chat with Claude and say
   *"new target: example.com — recon-intake"*. Claude will follow
   `prompts/recon-intake.md`, ask you minimal questions, and write the brief
   for you.

2. **Hunt:**
   ```
   prowl hunt example.com   # prints the context bundle Claude needs
   ```
   Paste that into the chat with Claude, or just say
   *"hunt example.com"* and Claude runs the bundle command itself.
   Claude follows `prompts/hunt-loop.md`: picks one goal, tests one hypothesis,
   writes a finding only when reproducible.

3. **Inspect:**
   ```
   prowl list           # all targets, finding count, last activity
   prowl show host      # everything about one target
   ```

## Layout
```
~/bughunt/
  bin/prowl                 the CLI
  templates/                brief.md / memory.md / finding.md skeletons
  prompts/                  recon-intake.md, hunt-loop.md (Claude protocols)
  knowledge/
    techniques/             reusable bug-class playbooks (XML-entity SQLi, etc.)
    by-stack/               stack-specific gotchas (laravel, next.js, ...)
  targets/<host>/
    brief.md                scope, accounts, goals, ground rules
    memory.md               append-only hunt log
    findings/NNN-slug.md    one file per real finding
    session.txt             cookies/headers (gitignore!)
    log.jsonl               raw req/resp audit
```

## Realistic expectations
This is a tool to make Claude + you a sharper hunter — not an autonomous
scanner. Per target: 1–3 hours of operator time → 0–5 quality findings.
Knowledge in `knowledge/` compounds over targets; that's where the leverage is.

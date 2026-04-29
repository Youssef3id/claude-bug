# Recon-intake protocol

Use this when the operator opens a new target. Goal: produce a high-quality
`brief.md` that is the single context for every later hunt.

Stay concise. Ask only what you cannot derive yourself.

## Step 1 — minimal questions to the operator
Ask, in this order, ONE message at a time. Wait for the answer before asking the next.

1. "Program URL (hackerone/bugcrowd/private)?"
2. "What's in scope — paste the scope block as-is, or describe the wildcard."
3. "What's out of scope — anything you specifically don't want me to touch?"
4. "Are there test accounts? If yes, paste creds (I'll move them to session.txt)."
5. "Anything you already know about the target — stack, prior reports, suspicious areas?"

If the operator gives you the program URL and is comfortable, fetch the public
scope page yourself (single WebFetch) instead of asking question 2.

## Step 2 — light passive recon (do not probe yet)
Run only zero-impact lookups, max 5–10 requests:
- DNS A/AAAA/CNAME of the apex
- One GET / on each in-scope host (TLS cert SAN list, server header, a few links from HTML)
- robots.txt, security.txt, sitemap.xml — only on hosts the operator authorized

Do NOT run subfinder/nuclei/dirb at this stage. Recon-intake is about
understanding, not surface area.

## Step 3 — write brief.md
Fill every [TODO] block from operator answers + what you observed. If a field
is genuinely unknown, write `unknown — to confirm` instead of guessing.

## Step 4 — propose hunting goals
Suggest 2–3 prioritized goals based on the stack you saw + bug-class affinity
(e.g. saw a Next.js app → suggest middleware bypass, RSC payload abuse;
saw a multi-tenant SaaS → cross-tenant IDOR, privilege escalation).

End the intake with: "Brief written. Run `prowl hunt <host>` when ready and I
will start with these goals."

## Token discipline
- Do NOT dump full HTML/JSON responses into chat. Summarize.
- Do NOT speculate about bugs you haven't seen evidence for.
- Each operator answer → at most one short paragraph back.

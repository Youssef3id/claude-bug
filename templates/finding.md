# {{SLUG}}
host: {{HOST}}
date: {{DATE}}
severity: [TODO critical | high | medium | low]
status: [TODO confirmed | submitted | accepted | rejected | duplicate]
cvss: [TODO 0.0–10.0]

## pre-submission gate (must be filled — finding is NOT ready until all pass)
> Delete this section only after the operator approves submission.

- [ ] **Harm sentence:** "A victim loses / gains / has exposed: ___" (fill in something real — money, credentials, account control, non-public PII)
- [ ] **Data class:** email / phone / address / password / session token / payment / booking financials / chaining ID → NOT favorites / VIP status / display name / preferences
- [ ] **Exploit executed:** ran against my own account(s), output captured below — not a thought experiment
- [ ] **Auth model compatible:** confirmed the auth mechanism carries credentials in the attack scenario (SameSite=None cookie / direct API key / etc.)
- [ ] **Program OOS list checked:** re-read `brief.md` OOS section — this class is not listed as ineligible
- [ ] **Triager test passed:** asked "would I triage this as valid if someone else submitted it?" → YES

## summary
[TODO 2–3 sentences. The bug class, the asset, the concrete consequence I have proven.]

## reproduction (steps)
1. [TODO exact step]
2. [TODO exact step]
3. [TODO exact step]

```
[TODO minimal request — copy-pasteable curl or raw HTTP — that triggers the bug]
```

## proof of exploitation (PoC)
> Run the actual exploit. Use ONLY accounts/data you control.
> The output below is captured from a real run against the target.

- Accounts used (must both be operator-controlled):
  - attacker: [TODO email/username]
  - victim:   [TODO email/username — second account I own, NOT a real user]
- Exploit script / command:
  ```
  [TODO the exploit, exactly as run]
  ```
- Output captured (excerpt — only what proves the bug):
  ```
  [TODO response snippet showing the leaked data / executed action]
  ```
- Side-effect verified by independent check:
  - [TODO e.g. "logged into victim account with extracted credentials and saw account dashboard"]

## demonstrated impact
> What actually happened. Not "an attacker could" — "I did".

- What was accessed/done: [TODO concrete list, e.g. "extracted username + password hash for arbitrary user IDs"]
- Data class: [TODO PII | credentials | financial | session | internal-only | none]
- Affected scope: [TODO 1 user / single-tenant / cross-tenant / all customers]
- Chain potential: [TODO does this give pivot to higher-impact bugs?]

## recommended fix
[TODO one specific paragraph — not "validate input"; name the actual mitigation, e.g. "switch the search field to a parameterised query via prepared statements" or "add a server-side check that the requested order_id belongs to the authenticated user"]

## notes
[TODO anomalies, scope-edge concerns, related areas to revisit, references to prior reports]

# Chain escalation — turning weak bugs into critical ones

Source: redscan exploitation_round prompt (battle-tested on real engagements).

## The core question to ask on every HIGH/CRITICAL finding

Before writing it up, run through this checklist:

| Finding type | Chain question |
|---|---|
| Username/ID leak | → can it enumerate accounts → feed into credential stuffing → ATO chain? |
| IDOR (read) | → is there a **write** counterpart on the same resource? |
| SSRF | → can it reach cloud metadata (169.254.169.254 / fd00:ec2::254) → token theft? |
| XSS | → is there an admin panel reachable from this JS context? |
| Forgeable token | → what **privileged action** does the token unlock? |
| Auth bypass | → what data/action does it expose — is that action destructive? |
| Info disclosure | → does it leak credentials, session tokens, or internal IPs? |

If a finding chains to something higher, the severity of the **chain** is what you report — not the individual step.

## Escalation technique reference

| technique | when to use |
|---|---|
| `idor` | predictable IDs + no ownership check |
| `auth_bypass` | auth skippable via header/param manipulation |
| `sqli` | SQL injection → dump or modify records |
| `ssrf` | server-side request → internal services or metadata API |
| `rce` | command injection or deserialization → code execution |
| `priv_esc` | low-priv user → elevated role or admin function |

## Chain hunting workflow

1. **Map the object graph first.** List every resource type (user, order, org, token, file). For each, know the ID format and what operations exist.
2. **Find the read IDOR.** Confirm you can read resource B as user A.
3. **Look for the write pair.** Same object, different method (PUT/PATCH/DELETE). Often guarded separately and missed.
4. **Test state machine steps out of order.** Can you skip from step 1 to step 3? Can you re-submit a completed step?
5. **Escalate to cross-account.** Does the bug apply to any user or only specific privilege levels?

## Expected outcome format (for findings)

Always write the outcome as a concrete, operator-readable one-liner:

- GOOD: "read any user's private messages via IDOR on `/api/messages/{id}`"
- GOOD: "account takeover of any user via forged session token on `/api/auth/verify`"
- BAD: "increased risk" / "potential compromise" / "security impact"

## Hard limits

- One escalation attempt per confirmed HIGH/CRITICAL finding.
- Never propose destructive operations (no DELETE on prod data, no mass exfil beyond single-record PoC).
- If no chain potential exists, say so explicitly. "Standalone medium" is a valid and honest conclusion.
- The goal is a submission-ready impact paragraph — not full system compromise.

## Common high-value chains (real patterns from disclosed reports)

```
SSRF on /api/webhook → hits 169.254.169.254 → gets AWS IAM role credentials → reads S3 bucket
XSS in user bio → fires in admin panel → exfils admin CSRF token → admin account takeover
IDOR on /api/user/{id} read → enumerate all user IDs → find admin user → read admin profile → pivot to admin API
Password reset token in Referer header → leak to third-party analytics → account takeover
GraphQL IDOR → read another user's private keys → use key for auth → full account takeover
Race condition on /api/subscribe → double subscription processed → billing bypass
```

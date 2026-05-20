# Stripe — stack notes

Source: redscan pack (stripe v1.0.0). Use when target integrates Stripe for payments.

## Fingerprinting

- Response header: `Server: Stripe`
- JS: `stripe.js`, `js.stripe.com/v3/`, `Stripe(pk_live_...)` or `Stripe(pk_test_...)`
- Network: requests to `api.stripe.com`, `hooks.stripe.com`
- Webhooks: POST to `/webhooks/stripe`, `/stripe/webhook`, `/payment/webhook` etc.

## Critical invariants to test

### stripe_webhook_signature (Critical)
Webhook endpoints must verify `Stripe-Signature` using HMAC-SHA256.
```
# Send a forged webhook without the Stripe-Signature header:
POST /webhooks/stripe  (or wherever app handles it)
Content-Type: application/json
{"type":"charge.succeeded","data":{"object":{"id":"ch_fake","amount":9999,"currency":"usd","metadata":{"order_id":"12345"}}}}

# Also try with wrong signature:
Stripe-Signature: t=1234567890,v1=badhash

# If order is fulfilled → webhook verification missing. Critical.
```

### stripe_test_key_in_prod (Critical)
Look for test API keys exposed in JS or responses.
```
# Grep JS bundles for the pattern:
curl -s https://target.com/app.js | grep -o 'pk_test_[a-zA-Z0-9]*'
curl -s https://target.com/app.js | grep -o 'sk_test_[a-zA-Z0-9]*'
# sk_test_ in frontend = critical (secret key exposed)
# sk_test_ used in prod API calls = wrong environment key
```

### stripe_idempotency_replay (High)
Replaying the same charge with the same Idempotency-Key must return the same result — not charge twice.
```
POST /api/v1/charge
Idempotency-Key: test-key-$(date +%s)
{"amount":100,"currency":"usd"}

# Replay with exact same key → must get same charge ID, not a new charge.
# If two different charge IDs → idempotency broken → double-charge vulnerability.
```

### stripe_refund_idempotency (High)
Double refund attempt with same idempotency key must return the first refund, not issue a second.
```
POST /api/v1/refund
Idempotency-Key: refund-test-001
{"charge_id":"ch_xxx","amount":100}
# Repeat with same key. If second `re_xxx` ID returned → double refund.
```

### stripe_amount_overflow (Medium)
Amount fields must reject Stripe's max (99999999 cents = ~$999,999).
```
POST /api/v1/charge
{"amount":100000000,"currency":"usd"}
# Expect validation error. If processed → may overflow internal accounting.
# Also test negative amounts: amount=-100 (potential refund bypass)
```

### stripe_metadata_injection (Medium)
Metadata keys/values must be sanitized.
```
POST /api/v1/charge
{"amount":100,"currency":"usd","metadata":{"key{injection}":"value","key":"<script>alert(1)</script>"}}
# Test for stored XSS in admin dashboards that render metadata, or
# server-side template injection if metadata is interpolated.
```

## Key endpoints (sinks)

| Endpoint | Method | Key params |
|---|---|---|
| `/v1/charges` | POST | amount, currency, source, customer |
| `/v1/refunds` | POST | charge, amount |
| `/v1/payment_intents` | POST | amount, currency, payment_method |
| Webhook handler (app-defined) | POST | Full Stripe event object |

## Business logic patterns to probe

- **Negative amount** — `amount=-500` on charge or refund → self-refund / credit
- **Currency mismatch** — charge in USD, refund in EUR → accounting delta
- **Concurrent charges** — race two simultaneous charge requests (same cart) → double purchase
- **Webhook replay** — resend a legitimate `charge.succeeded` event → fulfill order twice
- **Test card in prod** — submit card `4242424242424242` against a prod endpoint → may succeed if env mixed

## Chaining notes

- Missing webhook verification + business logic = forge payment success → free goods
- Test key in prod + metadata injection = read/write other customers' charge metadata
- Idempotency bug + race condition = double charges or double refunds
- Amount overflow + negative amount = potential financial system confusion

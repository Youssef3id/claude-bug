# Web cache deception — playbook

## when to try
- App is behind a CDN/cache (Cloudflare, Akamai, Fastly, Varnish, AWS CloudFront).
- App URLs contain user-specific data (`/account`, `/profile`, `/api/me`).
- Cache rules cache static-looking suffixes: `.css`, `.js`, `.png`, `.jpg`, `.svg`, `.ico`, `.woff2`.

## the technique
- Append a static-looking suffix to a dynamic URL: `/account/foo.css`.
- Server may either:
  - Return `/account` content (because routing ignores the suffix) — OR
  - Return 404. Try variants: `/account/x.js`, `/account/x.png`, `/account.css`, `/account/`, `/account#/x.css`.
- If the server returns the personal page, the CDN sees `.css` and caches it.
- Next victim who visits the same crafted URL gets your cached private content (or you visit it as the unauth attacker after the victim's response is cached).

## extra tricks
- **Path delimiters**: `/account;.css`, `/account%00.css`, `/account%2f%2e%2e/x.css`.
- **Different cache keys**: try `?` query parameters that the CDN ignores in the cache key but the origin honors.
- **Cache-Control overrides**: if you can inject headers (rare), `Cache-Control: public, max-age=999`.

## confirmation flow
1. Log into your test account.
2. Visit `https://t/account/secret.css`. Inspect `X-Cache`/`Age`/`CF-Cache-Status` response header — `HIT` means cached.
3. Open an incognito browser (no cookies) and request the same URL — you should see the personal data of the logged-in user.
4. To prove cross-user impact: have a second tab/account visit the URL, then your unauth fetch should return the second account's data.

## exploitation snippet
```bash
# As victim (logged in)
curl -sk -b "session=VICTIM" -i 'https://t/account/x.css' | head

# As attacker (no cookies) — should get same body
curl -sk -i 'https://t/account/x.css' | head
```

## caveats
- Programs accept this as Medium → High depending on what's exposed.
- Don't cache another real user's data — confirm with two of YOUR accounts.

## provenance
Omer Gil, Black Hat 2017. PortSwigger Web Cache Deception labs.

# Clickjacking — playbook

## when to try
- Sensitive state-changing pages: change-email, delete-account, transfer,
  enable/disable 2FA, payment confirmation, OAuth-consent screens.

## the test
- Embed the target page in an `<iframe>` on attacker.com.
- If it renders, the page is framable.
- Construct a UI that overlays the target's "confirm" button under an attractive bait button.

## defenses
- `X-Frame-Options: DENY|SAMEORIGIN` — prevents framing.
- `Content-Security-Policy: frame-ancestors 'self'` — newer, takes precedence.
- Both absent → confirmed framability. The actual risk is whether the framed page does something destructive on click.

## confirmation flow
1. `curl -sk -I https://t/account` — look for `X-Frame-Options` or `frame-ancestors`. Missing = candidate.
2. PoC: an HTML page with a transparent iframe of the target plus a fake "GET YOUR REWARD" button.
3. Demonstrate one click triggers a real action.

## exploitation snippet
```html
<style>iframe{position:absolute;top:0;left:0;width:100%;height:100%;opacity:0.0001}</style>
<button style="position:absolute;top:200px;left:300px;z-index:1">Click for reward</button>
<iframe src="https://target/account/delete?confirm=true"></iframe>
```

## caveats
- Most programs accept clickjacking only on truly destructive flows. "Frameable login page" is usually closed as informational.
- Modern browsers block third-party iframe cookies by default (Cookies SameSite=Lax) — clickjacking is dying for state-change unless the action is GET-based or uses LocalStorage/auth in URL.

## provenance
PortSwigger Clickjacking labs.

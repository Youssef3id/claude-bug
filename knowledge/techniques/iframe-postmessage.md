# iframe / postMessage / embedded forms — playbook

Cross-origin embedding bugs. The class is unglamorous but live in every SaaS
that ships a "drop this widget on your site" feature: chat bubbles, payment
forms, file pickers, OAuth consent dialogs, support widgets — and notably
**HackerOne's own `embedded_submissions/new`** iframe.

## when to try
- Any app with a `<script src="...widget.js">` install snippet.
- Any URL with `/embed/`, `/widget/`, `/iframe/`, `/submission_form`,
  `/embedded_submissions`, `/consent`, `/checkout`, `/oauth/authorize`,
  `/sso`, `/connect/`, `/share/preview`.
- Browser extensions that inject content scripts and listen on `window.message`.
- Mobile apps that wrap a `WebView` (Android `addJavascriptInterface` is the
  related class — different playbook).

## the bug classes

### A. postMessage receiver missing/weak origin check
The big one. Receiver does:
```js
window.addEventListener('message', e => {
  // BUG: no e.origin check, OR check is e.origin.indexOf("trusted.com") !== -1
  if (e.data.type === 'auth_token') localStorage.token = e.data.value;
  // OR worse:
  document.querySelector('#html').innerHTML = e.data.html;
  // OR: eval / new Function / location = e.data.url / postMessage forwarding
});
```
Common variants:
- **No origin check at all.** Attacker page does `iframe.contentWindow.postMessage({type:'set_url', value:'javascript:alert(1)'}, '*')`.
- **Substring/indexOf check.** `evil-trusted.com.attacker.tld` passes.
- **Endswith check on hostname.** `attackertrusted.com` passes (no leading-dot anchor).
- **Regex without anchors.** `/trusted\.com/.test(origin)` matches `attacker.com?x=trusted.com`.
- **Origin allowlist includes self.** `[location.origin, 'trusted.com']` — XSS on the parent page becomes message injection.

### B. postMessage sender leaking secrets via wildcard
Sender does:
```js
parent.postMessage({token: oauth_token}, '*');   // BUG
```
Any page that loaded the embed can read the token. Confirm by hosting an attacker page that frames the widget URL and listens for messages.

### C. X-Frame-Options / CSP `frame-ancestors` missing on sensitive flows
- Login, payment, MFA challenge, OAuth consent, "delete account" confirm.
- No `X-Frame-Options: DENY` and no `frame-ancestors 'self'` → clickjack.
- Modern variant: **CSP `frame-ancestors *`** with a sensitive page — explicit allow-all.
- Note: `X-Frame-Options` is **deprecated** but still respected; check **both** headers. CSP wins when both present.

### D. iframe `sandbox` permissions over-granted
`sandbox="allow-scripts allow-same-origin"` defeats the sandbox — the framed
page can reach out to its own origin's cookies/storage. Look for this on
user-content rendering surfaces (markdown previews, email previews, doc viewers).
Also: `sandbox="allow-top-navigation"` lets framed content redirect the
top window to a phishing page.

### E. DOM clobbering interactions (writeups in corpus: PrismJS CVE-2024-53382, html-janitor CVE-2017-0928, mavo CVE-2024-53388)
When a postMessage receiver does `if (window.config.trusted) ...` and
`window.config` can be clobbered by injected `<a id=config>` chains,
the trust check evaporates. Try in tandem with HTML-injection sinks.

### F. Cross-window navigation via opener
Window opened via `target="_blank"` without `rel="noopener"` → opened page
can `window.opener.location = 'phishing'` (tabnabbing). Modern browsers
default to `noopener` for `_blank`, but `window.open()` calls and old code
still leak.

### G. Embedded form CSRF / state confusion
Widgets that accept query-param prefilled state (e.g. H1's
`?report[title]=...&report[email]=...`) can be:
- **Reflected XSS** if the prefill values aren't escaped on the iframe page.
- **Phishing aid**: attacker sends victim a link that prefills attacker email
  into a "subscribe" or "forgot password" form, hoping the victim clicks submit.
- **CSRF** if the iframe form auto-submits via JS based on params and lacks token.
  Check whether `<input type="hidden" name="authenticity_token">` is present
  AND whether the server validates it. (Many widgets are stateless and rely
  on origin alone.)

### H. The HackerOne `embedded_submissions/new` widget (concrete reference)
Operator inputs include 327 such URLs. From the React shell + JS bundle
(`/assets/static/main_js-*.js`) inspection:
- The form is a React app booted via `<base target="_parent">` — clicks
  inside the iframe navigate the **parent** window unless intercepted.
- It calls GraphQL `embedded_submission_form(uuid:$uuid)` to bootstrap.
- Field returns `null` when unauthenticated → page renders empty React
  shell with title `HackerOne` (vs. the explicit `Program not live` HTML
  for revoked UUIDs). This is a useful tell when triaging UUIDs blind.
- Pre-filled state via `?report[title]=...&report[email]=...&report[time_spent]=...`
  is plumbed straight into form fields. **Worth checking** whether any of
  these escape into a context where they're rendered as HTML on the parent
  domain (long shot — H1 sanitizes, but ask the question for any other
  vendor's widget).
- The widget uses `postMessage` to talk to the embedding parent (resize
  events, "submission complete" events). Inspect those listeners with the
  flow in section A.

## confirmation flow

1. **Find every `addEventListener('message', ...)` in the iframe page.**
   ```bash
   curl -s <widget-url> | grep -oE '<script src="[^"]+"' | sed 's/<script src="//; s/"$//' \
     | xargs -I{} curl -s "https://<host>{}" \
     | grep -oE 'addEventListener\(["'\'']message["'\''][^)]+\)' | head
   ```
   Pull the source of each handler. Look for missing `e.origin ===` or weak comparisons.
2. **Build a minimal attacker page** (host on `localhost` or a Burp-Collaborator-served
   HTML payload):
   ```html
   <iframe id=t src="https://target.example/widget"></iframe>
   <script>
     window.addEventListener('message', e => console.log('FROM_WIDGET:', e.origin, e.data));
     setTimeout(() => {
       const f = document.getElementById('t');
       // try sending a message back; if receiver acts on it, no origin check
       f.contentWindow.postMessage({type:'set_url', value:'javascript:alert(document.domain)'}, '*');
     }, 2000);
   </script>
   ```
3. **For sender-leak (class B)**: iframe the URL and dump every message you
   receive. If a token shows up, you have a real bug. Capture the exact request
   you used + the message payload as PoC.
4. **For framing (class C)**: try framing the sensitive page from a different
   origin. If the page renders inside the iframe, no anti-frame protection.
   Build a minimal click-hijack PoC overlaying the dangerous button.
5. **Always demonstrate impact end-to-end**: token captured + replay against
   API works, OR action triggered + server-side state changed. A "could be"
   isn't a finding (workspace iron rule).

## payloads / one-liners

Find weak origin checks in a JS bundle:
```bash
curl -s "$JS" | grep -oE '\.origin[^=]*[=!]==?[^&|;)]*' | sort -u
# Also: substring patterns
curl -s "$JS" | grep -oE 'origin\.indexOf\([^)]+\)|origin\.includes\([^)]+\)|/[^/]+/\.test\(.*origin\)' | sort -u
```

Test postMessage receiver from console (no infra needed):
```js
const f = document.createElement('iframe');
f.src = 'https://target.example/widget';
document.body.append(f);
f.onload = () => f.contentWindow.postMessage({type:'<guess>', value:'<probe>'}, '*');
```

Detect missing frame protection:
```bash
curl -sI "$URL" | grep -iE 'x-frame-options|content-security-policy'
# absent or 'frame-ancestors *' = framable
```

## caveats / not-a-bug landmines
- Many programs explicitly OOS clickjacking on non-sensitive pages
  ("requires user interaction"). Anchor your finding on a *sensitive*
  state-changing action (delete, transfer, OAuth approve, MFA bypass).
- `postMessage` receivers that just `console.log` are not bugs.
- Widgets often *intentionally* postMessage `{height: NNN}` to parent for
  resizing — that's not data exfiltration.
- If the bug requires the victim to install your malicious page AND the page
  needs `X` permission AND the widget needs to be open, severity drops fast.

## provenance
- HackTricks: `pentesting-web/postmessage-vulnerabilities/` (Bypassing SOP with Iframes 1+2, README).
- PortSwigger: postMessage / cross-origin labs (2023+).
- PentesterLab: postMessage course.
- CVEs in corpus: PrismJS CVE-2024-53382, html-janitor CVE-2017-0928,
  mavo CVE-2024-53388 (DOM-clobbering ⊕ postMessage chain).
- Reference: "PostMessage Vulnerabilities: When Cross-Window Communication Goes Wrong".

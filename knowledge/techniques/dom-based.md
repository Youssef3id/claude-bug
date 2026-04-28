# DOM-based vulnerabilities — playbook

## when to try
- Single-page apps (Next.js, React, Vue, Angular) — a lot of state lives client-side.
- URL fragments / `#` parsing in JS (`location.hash`).
- `postMessage` listeners.
- Client-side routers that map URL segments to UI fragments.
- Apps that read from `localStorage`/`sessionStorage` and render without escaping.

## sources → sinks (the core mental model)
**Sources** (attacker-controllable):
- `location.href`, `.search`, `.hash`, `.pathname`
- `document.referrer`, `document.URL`, `document.cookie`
- `window.name`, `window.postMessage` data
- `localStorage`, `sessionStorage`, `IndexedDB`

**Sinks** (dangerous):
- DOM HTML: `innerHTML`, `outerHTML`, `document.write`, jQuery `.html()`.
- Script: `eval`, `Function()`, `setTimeout(string,...)`, `setInterval(string,...)`.
- URL: `location` (`javascript:` allowed), `<a href>` set via JS.
- Open-redirect: `location = userInput`.
- File: `Blob`, `URL.createObjectURL` for HTML/JS blobs.

## bug patterns
1. **DOM XSS**: source flows to HTML/script sink without escape.
2. **Open redirect**: source flows to `location` set without origin check.
3. **postMessage XSS**: handler doesn't validate `event.origin` and writes data to `innerHTML`.
4. **Prototype pollution → DOM XSS**: pollute `Object.prototype.x` then a templating lib reads `obj.x` as code.
5. **Client-side path injection**: SPA reads `location.pathname` to fetch JSON and renders without escape.

## confirmation flow
1. Open the page, view source / Network / Sources panels.
2. Search JS bundles for sinks: `grep -E 'innerHTML|document\.write|eval\(|location\s*=|new Function' app.js`.
3. For each sink, trace back to the source. If user-controllable, craft a payload and try.

## exploitation snippet
DOM XSS via fragment:
```
https://t/#<img src=x onerror=alert(1)>
```
postMessage XSS PoC:
```html
<iframe src="https://target/widget" id=t></iframe>
<script>setTimeout(()=>document.getElementById('t').contentWindow.postMessage('<img src=x onerror=alert(1)>','*'),1000)</script>
```

## caveats
- DOM XSS via fragment doesn't cross domain boundaries server-side — the attack vector is a clickable URL.
- Some sinks are protected by frameworks (React's `dangerouslySetInnerHTML` is the only true one).

## provenance
PortSwigger DOM-Based labs. DOM Invader (Burp).

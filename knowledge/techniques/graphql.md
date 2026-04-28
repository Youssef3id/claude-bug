# GraphQL API attacks — playbook

## when to try
- `/graphql`, `/graphiql`, `/api/graphql`, `/v2/graphql`. Sometimes hidden behind API gateway: try `POST /graphql` even if not advertised.

## reconnaissance
- **Introspection** (`__schema`): if enabled, dump the entire schema:
  ```bash
  curl -sk -X POST https://t/graphql -H 'Content-Type: application/json' \
    -d '{"query":"{__schema{queryType{name} mutationType{name} types{name fields{name args{name type{name}}}}}}"}' | jq
  ```
- If introspection is disabled: try `__type(name:"User"){fields{name}}` (sometimes overlooked). Also try GraphQL-specific tools (`clairvoyance`) which brute-force field names from a wordlist.
- Find non-/graphql paths: GraphQL also speaks GET (`?query=`), and may accept queries via persisted-query hashes — check Apollo `extensions.persistedQuery`.

## bug classes
- **Authorization bypass at field level**: a `Query.user(id:)` is gated, but `Query.allUsers` or `Query.search(filter:{...})` isn't.
- **IDOR via aliases**: send 100 aliased queries to enumerate IDs in one request.
  ```graphql
  { u1: user(id:1){email} u2: user(id:2){email} ... }
  ```
- **DoS via depth/breadth**: deeply nested query (`user{posts{author{posts{...}}}}`) or very wide aliasing → CPU/memory exhaustion. Most servers should depth-limit; if not, report.
- **CSRF via GET**: if server accepts queries via GET + SameSite=None cookies, classic CSRF.
- **Mutation without auth**: `createUser(role:"admin")` exposed without auth.
- **Input validation inheritance**: `User` has internal field `isAdmin` exposed in `updateUser` mutation → mass-assignment.
- **Subscription auth**: WebSocket subscriptions may skip auth that REST queries enforce.
- **Injection in resolvers**: GraphQL → SQL/NoSQL/Command injection in args.
- **Field suggestions**: server returns "did you mean `<close field>`" → leaks schema even with introspection off.
- **Batching attacks**: send 1000 logins in a single batched query → bypasses per-request rate limit.

## confirmation flow
1. Detect: `?query={__typename}` returns `{"data":{"__typename":"Query"}}`.
2. Pull schema (or guess from the JS bundle's GraphQL operations).
3. For each mutation: send unauth + send as low-priv user → look for ones that succeed unexpectedly.
4. Aliased IDOR PoC:
   ```graphql
   query{
     a: user(id:1){email} b: user(id:2){email} c: user(id:3){email}
   }
   ```

## exploitation snippet
Batching brute (login):
```bash
curl -sk -X POST https://t/graphql -H 'Content-Type: application/json' -d @- <<'EOF'
[
  {"query":"mutation($p:String!){login(user:\"admin\",pass:$p){token}}","variables":{"p":"pass1"}},
  {"query":"mutation($p:String!){login(user:\"admin\",pass:$p){token}}","variables":{"p":"pass2"}}
]
EOF
```

## caveats
- Apollo Server v4 disables introspection in prod by default — but persisted-query bypasses exist.
- "Introspection enabled" is rarely paid alone unless it leaks sensitive schema.

## provenance
PortSwigger GraphQL labs. clairvoyance, InQL Burp ext.

# Information disclosure — playbook

## when to try
- Always, passively, on every target. Often the gateway to bigger bugs.

## sources
- **robots.txt / sitemap.xml** — admin/internal paths.
- **/.well-known/** — security.txt, openid config, change-password URI.
- **Source maps** (`.js.map`, `.css.map`) — reconstruct original source incl. comments + secrets.
- **Backup files**: `index.php.bak`, `app.zip`, `web.config.swp`, `~`, `.old`, `.orig`.
- **VCS leaks**: `.git/config`, `.git/HEAD`, `.git/index` → use `git-dumper` to clone.
- **CI/CD**: `.github/`, `.gitlab-ci.yml`, `.circleci/`, `Jenkinsfile`.
- **Env files**: `.env`, `config.json`, `appsettings.json`.
- **Stack traces**: invalid input → 500 page leaks paths/version.
- **Verbose error in JSON**: `{"error":"...","stack":"..."}`.
- **Debug endpoints**: `/debug`, `/_debug`, `/trace`, `/__webpack_hmr`, `/_next/`, `/__nuxt/`, Spring `/actuator/{env,heapdump,trace}`, Laravel `/_ignition`, Django `/__debug__/`.
- **Headers**: `Server`, `X-Powered-By`, `X-AspNet-Version`, `Via`, `X-Backend`, `X-Cache`.
- **JS bundles**: grep for endpoints, hardcoded keys (Stripe `pk_live`, `sk_live`, AWS `AKIA*`, JWTs, GraphQL queries).
- **Source maps in prod APIs**: `swagger.json`, `openapi.yaml`, GraphQL introspection (`{__schema{types{name}}}`).

## confirmation flow
1. `curl -sk https://t/.git/HEAD` — `ref: refs/heads/main` = exposed.
2. `curl -sk https://t/.env` — `DB_PASSWORD=` = jackpot.
3. Walk the JS bundle: `curl -sk https://t/static/js/main.*.js | grep -oE 'https?://[a-z0-9./-]+'` — finds API endpoints, internal hosts.
4. `curl -sk -H "X-Forwarded-For: 127.0.0.1" https://t/admin` — sometimes flips internal-only checks.

## exploitation snippet
git-dump:
```bash
git clone https://github.com/arthaud/git-dumper /tmp/git-dumper
python3 /tmp/git-dumper/git_dumper.py https://t/.git/ /tmp/dump
cd /tmp/dump && git log --all --oneline | head
```

JS bundle endpoint hunt:
```bash
curl -sk 'https://t/static/js/main.*.js' | tr '\n' ' ' | grep -oE '"/[a-zA-Z0-9_/.-]+"' | sort -u | head -50
```

## caveats
- A leaked `.env` / `secrets.json` is **HIGH** even without further exploitation — report it immediately, don't probe further.
- Source-map exposure on staging is often acceptable; check scope.

## provenance
PortSwigger Info Disclosure labs. Daily bounty material across most programs.

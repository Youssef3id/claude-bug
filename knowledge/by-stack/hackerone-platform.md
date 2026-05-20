# HackerOne platform — stack notes

Notes on the HackerOne platform itself (`hackerone.com`), useful when triaging
H1-hosted assets, embedded submission widgets, or H1's own bounty program.

## GraphQL endpoint

`POST https://hackerone.com/graphql`

- Public introspection is **enabled** (verified 2026-05-04). `{__type(name:"Query"){fields{name}}}` works without auth.
- Many fields return `null` to anon (treated as auth gate, not 4xx). Treat
  `{"data":{"foo":null}}` as "blocked" not "no data".
- `team(handle:$h)` works for any **public** program (`security`, etc.) and
  returns handle/name/state/submission_state/offers_bounties/etc. without auth.
- `embedded_submission_form(uuid:$uuid)` **requires session**. Returns null anon.
- The web client sends `X-CSRF-Token` (from `<meta name="csrf-token">` of any
  signed-in HTML page). Cookie auth: `_hackerone_ssid` + `__Host-session`.

## Embedded submission iframe

`https://hackerone.com/<UUID>/embedded_submissions/new`

- React shell: `/assets/static/main_js-*.js`. Source-mapped names; the bundle
  reveals the GraphQL query bodies — useful for replicating client calls
  with curl. Grep the JS for the field name to see the full query.
- `<base target="_parent">` set in HTML — link clicks navigate the *parent*
  window of the iframe, not the iframe itself.
- Pre-fill via query params: `?report[title]=...&report[email]=...&report[time_spent]=...&report[impact]=...`. These flow into form fields. Worth probing for parent-DOM injection on whoever embeds the widget (not on H1 itself — H1 sanitizes).
- "Program not live" page: a small static HTML (no React) — useful as a
  triage signal when probing UUIDs anonymously.

## Useful queries (anon)

```graphql
# resolve a known public program
query { team(handle:"security") {
  handle name url state submission_state offers_bounties triage_active
} }

# discover query/mutation names
{ __type(name:"Query") { fields { name } } }
{ __type(name:"Mutation") { fields { name } } }
```

## Useful queries (with session)

```graphql
query($uuid:String!) {
  embedded_submission_form(uuid:$uuid) {
    uuid
    team {
      handle name state submission_state
      offers_bounties triage_active
      allows_private_disclosure publicly_visible_retesting
      structured_scopes(archived:false) { total_count }
      response_efficiency_percentage
    }
  }
}
```

## Iron-rule reminders for H1 itself
- H1 is in scope for H1's own program (handle `security`).
- Don't fuzz the platform. Real auth-flow / payment / submission-flow bugs
  only. PoC always against operator-controlled accounts.
- Do not submit reports through other programs' UUIDs as "tests".

## Operator note (2026-05-04)

327-UUID embedded-submission triage list landed; `targets/_h1-triage/`
contains the full list, the auth-blocker handoff, and a `resolve.sh` that
takes a cookie file and bulk-resolves UUIDs → program metadata via GraphQL.

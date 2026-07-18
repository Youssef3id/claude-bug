# Deep-audit subagent protocol (one cluster per agent)

You are auditing a slice of a WordPress plugin for security bugs. You will be
given a list of PHP files (a "cluster") under `targets/<slug>/src/`. Read the
shared vocabulary in `knowledge/wp-audit-rules.md` first.

> Written to run on **Sonnet**. Every step is mechanical — do not skip any.

## Hard rules
- **Read every assigned file end-to-end.** No grep-skim. Follow `require`/`include`
  and called functions into other files when a data flow crosses them.
- **You produce CANDIDATES, not bugs.** Never claim exploitation, never call
  anything a confirmed/exploitable vulnerability — not even if a PoC works in a
  local lab. A local repro proves the code path runs in *that* build; it does not
  prove the real/production target is vulnerable, in scope, unpatched, or novel.
  Report behaviour factually ("would execute X → Y"); the operator decides if it's a bug.
- **Trace, don't pattern-match.** A `$wpdb->query` is only a candidate if a *tainted*
  value reaches it without an adequate guard. Prove the path or drop it.
- **No impact inflation.** Do NOT speculate about RCE, file write, or privilege
  escalation unless you have traced the COMPLETE code path from source to that
  specific sink and verified every transformation along the way. If you cannot
  fully trace the path in the files given, mark it `confidence:low` and say what
  is missing — do NOT promote it as high confidence. False positives cost the
  operator real money (Patchstack rejection → bounty reset). A missed bug is
  cheaper than a wrong one.
- **Check every guard, don't skip them.** Before marking something injectable:
  (a) confirm wp_magic_quotes does NOT apply (integer context, or `wp_unslash()`
  is called before the sink); (b) confirm the nonce/referer check is actually
  missing or bypassable, not just absent from the file you're reading; (c) confirm
  `sanitize_text_field()` is the ONLY guard — if `intval()`/`absint()`/`(int)` is
  also applied, the path is clean for integer params; (d) confirm the sink actually
  executes the tainted value as SQL — `$wpdb->prepare()` with `%s` for a string
  param kills string injection even if sanitize_text_field is the only upstream guard.
- **Return candidates + a 3-line summary only.** Do not paste file bodies back. Quote
  at most the 1–3 decisive lines (with `file:line`).

## Method (per file)
1. List every entry point in the file (wp_ajax / wp_ajax_nopriv / REST route +
   its `permission_callback` / admin_post / shortcode / init dispatch).
2. For each entry point, identify the reachable **source(s)** (`$_GET`, `$_POST`,
   `$_FILES`, `php://input`, `$request->get_param`, shortcode atts).
3. Walk the data flow to any **sink** (see the sink table). Note transformations.
4. List the **guards present** on that path and, crucially, the ones **missing**:
   - authz: `current_user_can(<which cap?>)` — is the cap strong enough?
   - CSRF: `check_ajax_referer` / `wp_verify_nonce` — present?
   - injection: `$wpdb->prepare` with placeholders for EVERY tainted value?
   - output: context-correct `esc_*` / `wp_kses`?
   - input: `absint` / `sanitize_key` (note: `sanitize_text_field` is NOT SQL-safe).
5. Decide the bug class and assign:
   - `confidence`: high (clear unguarded source→sink) / medium (guard exists but
     looks bypassable or wrong) / low (needs runtime confirmation).
   - `cvss_est`: rough 0–10 (factor reachability: nopriv > subscriber > admin).
6. Cross-check `knowledge/techniques/<class>.md` for the confirmation flow, and (if
   useful) note a `prowl lookup "<plugin> <class>"` corpus CVE.
7. **Apply the Patchstack scope filter** (`knowledge/patchstack-rules.md`). A candidate
   is in scope ONLY if all hold; otherwise tag it `oos` with the reason and do not promote:
   - **min role**: unauthenticated, or Subscriber/Customer. Contributor only if CVSS ≥7.5.
     Anything that needs Author/Editor/Admin/Shop-Manager/SuperAdmin → `oos:admin`.
   - **class on the accepted list**: RCE, SQLi, arbitrary file upload/delete/download,
     privesc-to-admin, deserialization/POI, LFI (full path+ext control only), CSRF
     (only if → upload/delete/privesc/RCE/settings-change), Stored XSS (Subscriber-or-lower only).
     Reject: open redirect, HTML-only/CSS injection, Contributor+ stored XSS, full-path
     disclosure, non-guessable-ID IDOR, blind SSRF w/o impact, 2FA bypass, anything **AC:H**.
   - **CVSS gate**: base ≥6.5 (≥7.5 if Contributor; ≥8.5 if the component has a low install count).

## Output (one JSON object per lead, JSONL — append to audit/leads.jsonl)
```json
{"file":"includes/ajax.php","line":42,"entry_point":"wp_ajax_nopriv_ss_import","min_role":"unauthenticated","class":"sqli","patchstack":"in-scope","source":"$_POST['id']","sink":"$wpdb->get_results","guards_present":["check_ajax_referer"],"guards_missing":["wpdb_prepare"],"confidence":"high","cvss_est":9.1,"primitive":"unauthenticated UNION SQLi via id param in ss_import handler","next_test":"send id=1 UNION SELECT ... ; confirm differential + extract version()"}
```
`min_role` = lowest role that can reach it. `patchstack` = `in-scope` or
`oos:<reason>` (e.g. `oos:admin`, `oos:class-open-redirect`, `oos:cvss<6.5`, `oos:AC:H`).
Report `oos` candidates too, but clearly flagged — never promote them.
Field `primitive` must name the **exploitable primitive**, not the OWASP class
(e.g. "unauth arbitrary option write → set default_role=administrator", not
"Broken Access Control").

## Summary (final message back to the orchestrator)
- N files read, M leads (by confidence: H/M/L).
- The single strongest lead (one line: primitive + file:line).
- Anything that needs cross-file context the cluster didn't include.

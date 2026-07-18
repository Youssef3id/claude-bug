# WordPress plugin audit — source/sink/guard reference

The shared vocabulary for `prowl audit`. The scanner (`bin/_prowl_audit.py`) uses
these patterns to ROUTE the audit; the deep-audit agents (`prompts/code-audit.md`)
use them to TRACE each entry point. Keep the two in sync with this file.

A bug exists when a **source** reaches a **sink** with no adequate **guard** on
the path. The scanner flags candidates; only an agent tracing the actual data
flow (and later a live PoC) confirms one.

## Entry points (where attacker input enters)
| marker | reachable by | notes |
|---|---|---|
| `add_action('wp_ajax_nopriv_X', …)` | **unauthenticated** | highest priority — anyone can hit `/wp-admin/admin-ajax.php?action=X` |
| `add_action('wp_ajax_X', …)` | any logged-in user (incl. subscriber) | priv-esc if it does admin-only work |
| `register_rest_route(... permission_callback => '__return_true')` | **unauthenticated** | open REST route |
| `register_rest_route(...)` with weak callback | varies | read the callback — `is_user_logged_in` ≠ capability check |
| `add_action('admin_post_nopriv_X', …)` | **unauthenticated** | form POST handler |
| `add_action('admin_post_X', …)` | logged-in | |
| `add_shortcode('x', …)` | renders in page/comment context | attacker controls atts; output often echoed |
| `add_action('init'/'template_redirect'/'wp_loaded', …)` | every request | check for `$_GET`/`$_POST` dispatch inside |

## Sources (attacker-controlled input)
`$_GET` `$_POST` `$_REQUEST` `$_FILES` `$_COOKIE` `$_SERVER` (Referer, User-Agent,
X-Forwarded-For, Host), `php://input` / `file_get_contents('php://input')`,
REST `$request->get_param()/get_json_params()/get_body()`, shortcode `$atts`.
Also second-order: values previously read from `get_option`/`get_post_meta`/DB
that an attacker could have planted.

## Guards (what makes a path safe)
| guard | defends against | gotcha |
|---|---|---|
| `current_user_can('manage_options'|…)` | priv-esc / BFLA | wrong capability = still broken; `read` ≈ everyone |
| `check_ajax_referer($action,$arg)` / `wp_verify_nonce` / `check_admin_referer` | CSRF | a nonce a low-priv user can fetch does NOT stop priv-esc; only stops CSRF |
| `$wpdb->prepare()` | SQLi | only if EVERY tainted value is a placeholder; `%s` around an already-built string is useless; identifiers (table/column/`ORDER BY`) can't be `%s`-bound |
| `sanitize_text_field` / `sanitize_key` / `absint` / `intval` | XSS/SQLi (partial) | `sanitize_text_field` does NOT make a value SQL-safe; `absint` does |
| `esc_html` / `esc_attr` / `esc_url` / `esc_js` | XSS at output | must match the output context; `esc_attr` in HTML body ≠ safe |
| `wp_kses` / `wp_kses_post` | stored XSS | allowed-tag list can still permit `on*`/`href=javascript:` if misconfigured |

## Sinks by bug class
| class | sinks | what to prove |
|---|---|---|
| **sqli** | `$wpdb->query/get_results/get_var/get_row/get_col`, `$wpdb->prepare` misuse, raw `mysqli_query` | tainted value concatenated into SQL without a placeholder |
| **rce** | `eval` `assert` `create_function` `system` `exec` `shell_exec` `passthru` `popen` `proc_open` `call_user_func(_array)` `preg_replace('/e')` | attacker controls callable/command/code |
| **file_write** | `file_put_contents` `fwrite` `move_uploaded_file` `wp_handle_upload` `copy` `rename` `mkdir` `touch` | attacker controls path or contents → webshell / overwrite |
| **file_read** | `file_get_contents` `readfile` `fopen` `fpassthru` `highlight_file` | path traversal → arbitrary file read |
| **file_delete** | `unlink` `rmdir` `wp_delete_file` | attacker controls path → arbitrary delete |
| **lfi_rfi** | `include`/`require`(`_once`) with a `$variable` | local/remote file inclusion → RCE |
| **deserialize** | `unserialize` `maybe_unserialize` on tainted bytes | PHP object injection → gadget chain |
| **ssrf** | `wp_remote_get/post/request` `curl_exec` `file_get_contents('http…')` | attacker controls URL/host |
| **open_redirect** | `wp_redirect` `header('Location: …')` | attacker controls destination |
| **priv_esc** | `update_user_meta` `wp_update_user` `add_user_to_blog` `wp_insert_user` `set_role` | low-priv user sets role/caps |
| **option_write** | `update_option` `add_option` `update_site_option` | attacker writes arbitrary option (e.g. `users_can_register`, `default_role`, admin email) |
| **xss_echo** | `echo`/`print`/`printf`/`<?=` of a variable | unescaped tainted output in HTML/JS/attr context |

## Triage shortcuts (what usually pays on Patchstack)
1. `wp_ajax_nopriv_*` handler with a `$wpdb` or file sink and no/weak sanitiser.
2. `wp_ajax_*` handler doing admin work with only a nonce (no `current_user_can`) → priv-esc.
3. Open REST route returning or writing other users' data → IDOR / info disclosure.
4. `update_option`/`update_user_meta` reachable by subscriber → priv-esc to admin.
5. Settings import / `unserialize` of uploaded data → object injection.
6. Shortcode atts echoed without `esc_*` → stored XSS by contributor.

## Reminders
- A capability check is NOT a CSRF defence and a nonce is NOT an authz defence — they solve different problems; both may be required.
- `sanitize_text_field` ≠ SQL-safe and ≠ context-correct output escaping.
- Find the bug class playbook in `knowledge/techniques/<class>.md` before writing the lead.
- `setDataInResponse(false)` (Amelia pattern): data stored on CommandResult for internal use but suppressed in HTTP response → not a PII disclosure even if PII is fetched from DB.

## Audited dead-ends (skip re-audit unless version bumps past these)
- `ameliabooking` v2.4 (2026-05-25): well-hardened Slim command dispatch; token+HMAC on all nopriv whitelisted commands; parameterized queries; setDataInResponse(false) suppresses internal PII. Zero candidates.
- `ajax-search-for-woocommerce` v1.33.0 (2026-05-25, SQLi/LFI scope): hardened — all nopriv handlers route user input through sanitize_text_field → WP_Query only (no raw wpdb calls); all include/require paths are hardcoded plugin constants. Zero candidates for SQLi or LFI.
- `woo-cart-abandonment-recovery` v2.1.1 (2026-05-25, SQLi/LFI scope): clean — nopriv handlers use WooCommerce server-side session (not HTTP params) for WHERE clauses; all admin-facing SQL uses prepare()/insert()/update() correctly; LFI scanner hits were all false positives (hardcoded paths or PHP autoloader). Zero candidates for SQLi or LFI.
- `woocommerce-pdf-invoices-packing-slips` v5.12.2 (2026-05-25, SQLi/LFI scope): clean — nopriv PDF handler selects template by type string but never routes it into a file path (whitelisted object lookup); custom `wpo_wcpdf_prepare_identifier_query()` helper correctly handles identifier escaping throughout; SetupWizard LFI false positive (user input = array key only). Zero candidates for SQLi or LFI.
- `wpdatatables` v6.5.0.8 (2026-05-25, SQLi/LFI scope): clean — Lite edition renders table data server-side only (DataTables.js client-side mode, no subscriber AJAX handler); admin browse views have raw LIKE concat but are manage_options-gated; nopriv cache handler is locked by a 44-char random secret. Zero candidates for SQLi or LFI.
- `woocommerce-products-filter (HUSKY)` v1.3.8.2 (2026-05-25, SQLi/LFI scope): mostly clean — 25+ nopriv handlers but all filter params flow through WP_Query array API (no raw SQL); turbo_mode nonce is admin-panel-only; front_builder LFI sanitize_key()-killed; by_text uses esc_like+prepare(); one conditional low-confidence lead: products_messenger stores $wp_query->request (WP-generated SQL) in usermeta and executes via $wpdb->get_results() — denylist doesn't block UNION but exploitability requires getting a UNION payload into WP_Query->request (unlikely due to WP's own prepare()). Zero confirmed candidates for SQLi or LFI.
- `ajax-search-lite` v4.14.2 (2026-05-25, SQLi/LFI scope): clean — open REST routes (permission_callback __return_true) don't connect to SQL-building code; main nopriv search uses esc_sql() for LIKE; ORDER BY uses strict switch() whitelist; LFI paths use plugin constants only. Zero candidates for SQLi or LFI.
- `mp-timetable` v2.4.17 (2026-05-25, SQLi/LFI scope): clean — no nopriv/open REST handlers; only shortcode surface; `get_events_data()` column whitelisted to ['column_id','event_id'] and values coerced via prepare('%d'); no LFI paths. Zero candidates for SQLi or LFI.
- `ba-book-everything` v1.8.24 (2026-05-25, SQLi/LFI scope): clean — 15 nopriv handlers all use absint/(int) for IDs; keyword LIKE uses esc_sql (blocks quotes); sort/orderby use switch() whitelist; import path requires admin capability; no LFI paths. Zero candidates.
- `wp-events-manager` v2.1.10 (2026-05-25, SQLi/LFI scope): one OOS lead — ORDER BY injection in posts_orderby filter ($REQUEST['order'] raw in SQL) gated by is_admin()+edit_posts (Contributor); CVSS ~6.5 < 7.5 Patchstack floor for Contributors; shortcodes use WP_Query safely; no nopriv handlers; all other SQL uses prepare()/(int). Zero in-scope candidates.
- `products-extractor-for-woocommerce` v2.1.2 (2026-05-25, SQLi/LFI scope): clean — no nopriv handlers; all REST params gated by strict regex/intval/WC ORM; OrderTrackingHandler cookie sanitized by [A-Za-z0-9_-]+ pattern; no raw wpdb calls in any file; no include with user-controlled paths. Zero candidates.
- `zero-bs-crm` v6.8.0 (2026-05-25, SQLi/LFI scope): clean — nopriv NotifyMe handler uses get_current_user_id() with %d binding only; portal LFI paths all hardcoded constants; MailTracking unauthenticated tracker uses prepare('%s') correctly; all dashboard/email AJAX SQL uses prepare()/(int) throughout; API LFI gated by 13-item hardcoded allowlist + API key auth. Zero candidates for SQLi or LFI.
- `form-maker` v1.15.43 (2026-05-25, SQLi/LFI scope): clean for free tier — CSV/XML export handlers (and their SQLi in WDW_FM_Library::get_submissions_to_export groupids IN-clause) are registered only in pro (is_free=0); free version (is_free=1) nopriv handlers use intval()/prepare() throughout; no LFI (all includes use plugin_dir constants + hardcoded filenames). Zero candidates for SQLi or LFI in free version.
- `wp-user-frontend` v4.3.6 (2026-05-25, SQLi/LFI scope): clean — nopriv handler `wpuf_get_child_cat` routes through WP `get_categories()` ORM only; open REST user-directory uses WP_User_Query with whitelisted orderby; `wpuf_ajax_tag_search` interpolates `sanitize_key()`-filtered `$term_ids` into prepare() (false positive — `[a-z0-9_-]` charset blocks all meaningful injection); subscription/payment/paypal paths all use prepare() correctly; all include/require use hardcoded plugin constants. Zero candidates for SQLi or LFI.
- `paid-member-subscriptions` v3.0.4 (2026-05-25, SQLi/LFI scope): clean — 7 nopriv handlers (checkout/payment/discount) all route through WP ORM (get_posts/get_post_meta) or absint() for IDs; pms_update_nonce freely dispenses nonces but downstream SQL is absint()-safe; PayPal IPN handlers use absint() for numeric fields + prepare() for string queries; Stripe webhook is cryptographic-signature-gated; admin-export SQLi is manage_options-gated (can_export() check); functions-utils.php LFI uses glob() with server-side constant + fixed pattern (no user input in path). Zero candidates for SQLi or LFI.

#!/usr/bin/env python3
"""
_prowl_audit.py — WordPress plugin attack-surface scanner.

This is the MECHANICAL pass of `prowl audit`. It does NOT decide a file is
safe and it does NOT report bugs. Its only jobs are:
  1. enumerate every PHP source file (excluding vendor/min/asset noise),
  2. classify each by WP entry-points / user-input sources / dangerous sinks /
     guards present,
  3. emit a machine-readable manifest + a human-readable surface map, and
  4. cluster the in-scope files into review units for LLM fan-out.

Every in-scope PHP file is still meant to be read end-to-end by the deep-audit
agents — this scanner only ROUTES and RANKS them. Findings come from the LLM
pass + live testing, never from this script.

Usage:
    _prowl_audit.py --src <plugin_src_dir> --out <audit_dir> --slug <slug>

Writes <audit_dir>/manifest.json and <audit_dir>/surface-map.md, and prints a
one-line JSON summary (plugin meta) to stdout for the caller to seed brief.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# --------------------------------------------------------------------------
# What we skip. The scanner never audits these — they are not attack surface.
# --------------------------------------------------------------------------
EXCLUDE_DIRS = {
    "vendor", "node_modules", "dist", "build", ".git", "tests", "test",
    "languages", "lang", "fonts", "img", "images", "fontello",
}
EXCLUDE_FILE_RE = re.compile(r"\.min\.(php|js|css)$|\.(css|scss|less|js|map|po|mo|pot|md|txt|json|lock|woff2?|ttf|eot|svg|png|jpe?g|gif|webp|ico)$", re.I)

# --------------------------------------------------------------------------
# WP vocabulary (kept in sync with knowledge/wp-audit-rules.md).
# --------------------------------------------------------------------------
ENTRY_PATTERNS = [
    # (type, regex with named groups where useful)
    ("ajax",        re.compile(r"""add_action\s*\(\s*['"]wp_ajax_(?P<nopriv>nopriv_)?(?P<name>[A-Za-z0-9_\-]+)['"]""")),
    ("admin_post",  re.compile(r"""add_action\s*\(\s*['"]admin_post_(?P<nopriv>nopriv_)?(?P<name>[A-Za-z0-9_\-]+)['"]""")),
    ("rest",        re.compile(r"""register_rest_route\s*\(""")),
    ("shortcode",   re.compile(r"""add_shortcode\s*\(\s*['"](?P<name>[^'"]+)['"]""")),
    ("admin_page",  re.compile(r"""add_(?:menu|submenu|options|management|theme|plugins|users|dashboard)_page\s*\(""")),
    ("init_hook",   re.compile(r"""add_action\s*\(\s*['"](?:init|wp_loaded|template_redirect|admin_init|wp_head|wp_footer)['"]""")),
]

# An open REST route: permission_callback that lets anyone in.
REST_OPEN_RE = re.compile(r"""['"]permission_callback['"]\s*=>\s*(?:['"]__return_true['"]|function\s*\([^)]*\)\s*\{\s*return\s+true)""")

SOURCE_PATTERNS = {
    "$_GET":      re.compile(r"\$_GET\b"),
    "$_POST":     re.compile(r"\$_POST\b"),
    "$_REQUEST":  re.compile(r"\$_REQUEST\b"),
    "$_FILES":    re.compile(r"\$_FILES\b"),
    "$_COOKIE":   re.compile(r"\$_COOKIE\b"),
    "$_SERVER":   re.compile(r"\$_SERVER\b"),
    "php://input":re.compile(r"php://input"),
    "rest_param": re.compile(r"->get_(?:param|json_params|body_params|query_params|file_params|body)\s*\("),
}

GUARD_PATTERNS = {
    "current_user_can":   re.compile(r"current_user_can\s*\("),
    "check_ajax_referer": re.compile(r"check_ajax_referer\s*\("),
    "check_admin_referer":re.compile(r"check_admin_referer\s*\("),
    "wp_verify_nonce":    re.compile(r"wp_verify_nonce\s*\("),
    "is_user_logged_in":  re.compile(r"is_user_logged_in\s*\("),
    "is_admin":           re.compile(r"\bis_admin\s*\("),
    "wpdb_prepare":       re.compile(r"->prepare\s*\("),
    "sanitize_*":         re.compile(r"\bsanitize_[a-z_]+\s*\("),
    "esc_*":              re.compile(r"\besc_[a-z_]+\s*\("),
    "wp_kses":            re.compile(r"\bwp_kses(?:_post)?\s*\("),
    "absint/intval":      re.compile(r"\b(?:absint|intval)\s*\("),
}

# Sinks grouped by bug class. Order matters only for display.
SINK_PATTERNS = {
    "sqli":        re.compile(r"\$wpdb\s*->\s*(?:query|get_results|get_var|get_row|get_col|prepare)\s*\(|\b(?:mysqli_query|mysql_query)\s*\("),
    "rce":         re.compile(r"\b(?:eval|assert|create_function|system|exec|shell_exec|passthru|popen|proc_open)\s*\(|\b(?:call_user_func(?:_array)?)\s*\(|preg_replace\s*\(\s*['\"][^'\"]*/e"),
    "file_write":  re.compile(r"\b(?:file_put_contents|fwrite|fputs|move_uploaded_file|wp_handle_upload|copy|rename|mkdir|touch)\s*\("),
    "file_read":   re.compile(r"\b(?:file_get_contents|readfile|fopen|fpassthru|highlight_file|show_source)\s*\("),
    "file_delete": re.compile(r"\b(?:unlink|rmdir|wp_delete_file)\s*\("),
    "lfi_rfi":     re.compile(r"\b(?:include|include_once|require|require_once)\s*(?:\(|\s)\s*\$"),
    "deserialize": re.compile(r"\b(?:unserialize|maybe_unserialize)\s*\("),
    "ssrf":        re.compile(r"\bwp_remote_(?:get|post|request|head)\s*\(|\bcurl_exec\s*\(|file_get_contents\s*\(\s*['\"]https?://"),
    "open_redirect":re.compile(r"\bwp_redirect\s*\(|\bheader\s*\(\s*['\"]Location"),
    "priv_esc":    re.compile(r"\b(?:update_user_meta|wp_update_user|add_user_to_blog|wp_insert_user|set_role)\s*\("),
    "option_write":re.compile(r"\b(?:update_option|add_option|update_site_option)\s*\("),
    "xss_echo":    re.compile(r"(?:\becho\b|\bprint\b|\bprintf\b|<\?=)\s*.*\$"),
}

DANGEROUS_CLASSES = {"sqli", "rce", "file_write", "lfi_rfi", "deserialize", "ssrf", "priv_esc", "file_delete"}
# Classes Patchstack rejects outright (knowledge/patchstack-rules.md, Gate 3).
OOS_CLASSES = {"open_redirect"}


def entry_tier(etype: str, nopriv: bool) -> str:
    """Patchstack privilege tier for an entry point (Gate 1). 'admin' ≈ out of scope."""
    if etype in ("ajax", "admin_post"):
        return "unauth" if nopriv else "auth"        # auth = subscriber-reachable (in scope)
    if etype == "admin_page":
        return "admin"                               # manage_options → likely OOS
    if etype == "rest":
        return "rest?"                               # refined to 'unauth' if permission_callback is open
    if etype == "shortcode":
        return "content"
    if etype == "init_hook":
        return "any"                                 # fires every request; could be unauth dispatch
    return "auth"


@dataclass
class FileReport:
    rel: str
    lines: int
    bytes: int
    entry_points: list = field(default_factory=list)   # {type,name,nopriv,line}
    rest_open: bool = False
    sources: list = field(default_factory=list)
    guards: list = field(default_factory=list)
    sinks: list = field(default_factory=list)          # {class,line,snippet}
    risk: int = 0

    @property
    def interesting(self) -> bool:
        has_entry = bool(self.entry_points)
        has_flow = bool(self.sources) and bool(self.sinks)
        return has_entry or has_flow

    @property
    def tiers(self) -> set:
        return {e.get("tier", "auth") for e in self.entry_points} | ({"unauth"} if self.rest_open else set())

    @property
    def scope_hint(self) -> str:
        """Patchstack privilege scope guess (Gate 1) — agent confirms by reading caps."""
        t = self.tiers
        if "unauth" in t:
            return "in:unauth"
        if t & {"auth", "any", "content"}:
            return "in:low-role?"
        dangerous = {s["class"] for s in self.sinks} & DANGEROUS_CLASSES
        if self.sources and dangerous:
            return "in:flow?"
        if "admin" in t:
            return "oos:admin-only?"
        return "review"


def parse_header(src: Path) -> dict:
    """Read the WP plugin header from the main file in the plugin root."""
    meta = {"name": "", "version": "", "requires_php": "", "requires_wp": "",
            "author": "", "text_domain": "", "main_file": ""}
    fields = {
        "name": re.compile(r"Plugin Name:\s*(.+)", re.I),
        "version": re.compile(r"Version:\s*(.+)", re.I),
        "requires_php": re.compile(r"Requires PHP:\s*(.+)", re.I),
        "requires_wp": re.compile(r"Requires at least:\s*(.+)", re.I),
        "author": re.compile(r"Author:\s*(.+)", re.I),
        "text_domain": re.compile(r"Text Domain:\s*(.+)", re.I),
    }
    # Main file: a top-level .php containing "Plugin Name:". Prefer shallowest.
    candidates = sorted(src.rglob("*.php"), key=lambda p: len(p.relative_to(src).parts))
    for php in candidates:
        try:
            head = php.read_text(errors="replace")[:4096]
        except OSError:
            continue
        if "Plugin Name:" in head:
            meta["main_file"] = str(php.relative_to(src))
            for key, rx in fields.items():
                m = rx.search(head)
                if m:
                    meta[key] = m.group(1).strip().strip("*").strip()
            break
    return meta


def scan_file(php: Path, rel: str) -> FileReport:
    text = php.read_text(errors="replace")
    lines = text.splitlines()
    rep = FileReport(rel=rel, lines=len(lines), bytes=len(text))

    for i, line in enumerate(lines, 1):
        for etype, rx in ENTRY_PATTERNS:
            for m in rx.finditer(line):
                gd = m.groupdict()
                nopriv = bool(gd.get("nopriv"))
                rep.entry_points.append({
                    "type": etype,
                    "name": gd.get("name") or "",
                    "nopriv": nopriv,
                    "tier": entry_tier(etype, nopriv),
                    "line": i,
                })
        for cls, rx in SINK_PATTERNS.items():
            if rx.search(line):
                rep.sinks.append({"class": cls, "line": i, "snippet": line.strip()[:160]})

    for name, rx in SOURCE_PATTERNS.items():
        if rx.search(text):
            rep.sources.append(name)
    for name, rx in GUARD_PATTERNS.items():
        if rx.search(text):
            rep.guards.append(name)
    if REST_OPEN_RE.search(text):
        rep.rest_open = True
        for e in rep.entry_points:
            if e["type"] == "rest":
                e["tier"] = "unauth"

    # Risk heuristic — orders the fan-out by Patchstack scope (Gate 1), not a verdict.
    score = 0
    t = rep.tiers
    if "unauth" in t:                       # unauthenticated reach = top priority (x2 payout)
        score += 5
    if t & {"auth"}:                        # subscriber-reachable = in scope (x1)
        score += 2
    if t & {"any", "content"}:              # init/shortcode dispatch — needs role check
        score += 1
    admin_only = ("admin" in t) and not (t & {"unauth", "auth", "any", "content"})
    if admin_only:                          # admin-only surface ≈ OUT of scope → down-rank
        score -= 2
    dangerous = {s["class"] for s in rep.sinks} & DANGEROUS_CLASSES
    score += 2 * len(dangerous)
    if rep.sources:
        score += 1
    # Mitigation present softens ordering but never zeroes a nopriv+sink file.
    strong_guards = {"current_user_can", "check_ajax_referer", "check_admin_referer",
                     "wp_verify_nonce", "wpdb_prepare"} & set(rep.guards)
    if strong_guards:
        score -= 1
    rep.risk = max(score, 0)
    return rep


def cluster(reports: list, max_files: int = 6, max_bytes: int = 60000) -> list:
    """Group interesting files into review units, keyed by top-level dir."""
    interesting = [r for r in reports if r.interesting]
    buckets: dict[str, list] = {}
    for r in interesting:
        parts = Path(r.rel).parts
        key = parts[1] if len(parts) > 2 else (parts[0] if len(parts) > 1 else ".")
        buckets.setdefault(key, []).append(r)

    clusters = []
    for key, files in buckets.items():
        files.sort(key=lambda r: -r.risk)
        cur, cur_bytes = [], 0
        for r in files:
            if cur and (len(cur) >= max_files or cur_bytes + r.bytes > max_bytes):
                clusters.append({"dir": key, "files": [x.rel for x in cur],
                                 "risk": sum(x.risk for x in cur)})
                cur, cur_bytes = [], 0
            cur.append(r)
            cur_bytes += r.bytes
        if cur:
            clusters.append({"dir": key, "files": [x.rel for x in cur],
                             "risk": sum(x.risk for x in cur)})
    clusters.sort(key=lambda c: -c["risk"])
    return clusters


def write_surface_map(out: Path, meta: dict, reports: list, clusters: list,
                      excluded: int) -> None:
    interesting = sorted([r for r in reports if r.interesting], key=lambda r: -r.risk)
    unauth_entries = [(r, e) for r in reports for e in r.entry_points if e.get("tier") == "unauth"]
    admin_entries = [(r, e) for r in reports for e in r.entry_points if e.get("tier") == "admin"]
    open_rest = [r for r in reports if r.rest_open]

    L = []
    L.append(f"# Attack-surface map — {meta.get('name') or meta.get('slug','')}")
    L.append("")
    L.append(f"- version: `{meta.get('version','?')}`  |  requires PHP `{meta.get('requires_php','?')}`  |  requires WP `{meta.get('requires_wp','?')}`")
    L.append(f"- main file: `{meta.get('main_file','?')}`")
    L.append(f"- php files in scope: **{len(reports)}**  |  interesting: **{len(interesting)}**  |  excluded (vendor/min/assets): {excluded}")
    L.append("")
    L.append("> This map ROUTES the deep audit. Every in-scope file below must still be")
    L.append("> read end-to-end by an agent. Risk score orders the fan-out; it is not a verdict.")
    L.append("> **Patchstack scope (knowledge/patchstack-rules.md):** eligible roles are")
    L.append("> unauth (x2) > subscriber/customer (x1) > contributor (≥7.5 CVSS). Admin-only")
    L.append("> surface is **out of scope** and down-ranked. CVSS floor 6.5. `(oos)` = rejected class.")
    L.append("")

    L.append("## ⚠ Unauthenticated entry points (audit these first — x2 payout)")
    if unauth_entries:
        L.append("| handler | type | file | line |")
        L.append("|---|---|---|---|")
        for r, e in sorted(unauth_entries, key=lambda x: -x[0].risk):
            L.append(f"| `{e['name'] or '(rest route)'}` | {e['type']}{'·nopriv' if e['nopriv'] else ''} | `{r.rel}` | {e['line']} |")
    else:
        L.append("_none detected via wp_ajax_nopriv_ / admin_post_nopriv_ / open REST route_")
    L.append("")
    if open_rest:
        L.append("### Open REST routes (permission_callback => __return_true)")
        for r in open_rest:
            L.append(f"- `{r.rel}`")
        L.append("")

    L.append("## Interesting files (ranked)")
    L.append("| risk | scope | file | entry points | sources | sink classes | guards present |")
    L.append("|---:|---|---|---|---|---|---|")
    for r in interesting:
        eps = ", ".join(sorted({e["type"] + ("·nopriv" if e["nopriv"] else "") for e in r.entry_points})) or "—"
        srcs = ", ".join(r.sources) or "—"
        sink_set = sorted({s["class"] for s in r.sinks})
        sinks = ", ".join((c + " (oos)") if c in OOS_CLASSES else c for c in sink_set) or "—"
        guards = ", ".join(r.guards) or "**none**"
        L.append(f"| {r.risk} | {r.scope_hint} | `{r.rel}` | {eps} | {srcs} | {sinks} | {guards} |")
    L.append("")

    if admin_entries:
        L.append("## Admin-only entry points (likely OUT of scope — verify a lower role can't reach)")
        seen = set()
        for r, e in admin_entries:
            if r.rel in seen:
                continue
            seen.add(r.rel)
            L.append(f"- `{r.rel}` — {e['type']} (Patchstack: admin/manage_options not accepted)")
        L.append("")

    L.append("## Fan-out clusters (one subagent per row)")
    L.append("| # | dir | risk | files |")
    L.append("|---:|---|---:|---|")
    for i, c in enumerate(clusters, 1):
        L.append(f"| {i} | `{c['dir']}` | {c['risk']} | {', '.join('`'+f+'`' for f in c['files'])} |")
    L.append("")
    out.write_text("\n".join(L) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--slug", required=True)
    args = ap.parse_args()

    src = Path(args.src).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not src.is_dir():
        print(f"_prowl_audit: not a dir: {src}", file=sys.stderr)
        return 1

    meta = parse_header(src)
    meta["slug"] = args.slug

    reports, excluded = [], 0
    for php in sorted(src.rglob("*.php")):
        rel = str(php.relative_to(src))
        parts = set(Path(rel).parts)
        if parts & EXCLUDE_DIRS or EXCLUDE_FILE_RE.search(php.name):
            excluded += 1
            continue
        try:
            reports.append(scan_file(php, rel))
        except OSError:
            continue
    reports.sort(key=lambda r: -r.risk)
    clusters = cluster(reports)

    manifest = {
        "meta": meta,
        "counts": {
            "php_in_scope": len(reports),
            "interesting": sum(1 for r in reports if r.interesting),
            "excluded": excluded,
            "clusters": len(clusters),
        },
        "files": [asdict(r) for r in reports],
        "clusters": clusters,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    write_surface_map(out / "surface-map.md", meta, reports, clusters, excluded)

    # Stdout summary line for the bash caller (brief seeding).
    print(json.dumps({
        "slug": meta["slug"], "name": meta["name"], "version": meta["version"],
        "requires_php": meta["requires_php"], "requires_wp": meta["requires_wp"],
        "main_file": meta["main_file"],
        "php_in_scope": len(reports), "interesting": manifest["counts"]["interesting"],
        "clusters": len(clusters),
        "nopriv_entries": sum(1 for r in reports for e in r.entry_points if e["nopriv"]),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

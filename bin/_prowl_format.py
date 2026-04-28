#!/usr/bin/env python3
"""Read JSONL on stdin, emit short human-readable records for `prowl lookup`."""
import json, sys

for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    try:
        o = json.loads(raw)
    except Exception:
        continue
    print("---")
    print(f"[{o.get('source_type','?')}] {o.get('source_id','?')}")
    title = (o.get("title") or "").strip().replace("\n", " ")
    if title:
        print(f"title: {title[:160]}")
    content = (o.get("content") or "").strip().replace("\n", " ")
    if content:
        print(f"snippet: {content[:280]}")
    tags = o.get("tags") or []
    if tags:
        print(f"tags: {tags}")
    sev = o.get("severity")
    if sev:
        print(f"severity: {sev}")

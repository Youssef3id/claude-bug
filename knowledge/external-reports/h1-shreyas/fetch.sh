#!/usr/bin/env bash
# Polite bulk-fetch of H1 disclosed reports listed in h1-report-urls.txt.
# Resume-safe: skips IDs already on disk. Logs progress.
set -u
cd "$(dirname "$0")"
mkdir -p reports
URLS=h1-report-urls.txt
LOG=fetch.log
PROGRESS=fetch.progress
SLEEP=0.5   # 2 req/sec
UA="prowl-research/1.0 (+research; contact: youssefmohammedeid0@gmail.com)"

total=$(wc -l < "$URLS")
done=0
ok=0
skip=0
fail=0
echo "[start $(date -Iseconds)] total=$total" >> "$LOG"

while read -r url; do
  done=$((done+1))
  id="${url##*/}"
  out="reports/${id}.json"
  if [ -s "$out" ]; then
    skip=$((skip+1))
  else
    code=$(curl -sk -A "$UA" -H 'Accept: application/json' \
            -o "$out" -w '%{http_code}' "https://hackerone.com/reports/${id}.json" || echo 000)
    if [ "$code" = "200" ] && [ -s "$out" ]; then
      ok=$((ok+1))
    else
      rm -f "$out"
      fail=$((fail+1))
      echo "FAIL $id http=$code" >> "$LOG"
    fi
    sleep "$SLEEP"
  fi
  if [ $((done % 100)) -eq 0 ]; then
    echo "[$(date +%H:%M:%S)] $done/$total ok=$ok skip=$skip fail=$fail" >> "$PROGRESS"
  fi
done < "$URLS"

echo "[done $(date -Iseconds)] total=$done ok=$ok skip=$skip fail=$fail" >> "$LOG"

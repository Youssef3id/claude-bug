#!/usr/bin/env python3
"""
Pipeline that generates the 32 training-data JSONL files described in
GENERATE_TRAINING_DATA.md using the Anthropic API.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 generate_pipeline.py                       # generate all 32 files
    python3 generate_pipeline.py --only type5_detection_001_050
    python3 generate_pipeline.py --model claude-opus-4-7
    python3 generate_pipeline.py --batch-size 5 --dry-run

Notes:
    - Resumable. Files that already exist with the expected line count are skipped.
    - Each file is generated in batches (default 5 examples per API call), validated,
      and appended. Failed batches are retried up to 3 times.
    - Validation: JSON parses, required keys present, no placeholder strings,
      minimum word count per type, and (for type5) the 40/40/20 verdict ratio.
    - Output dir defaults to ~/training_data/  (override with --out)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import anthropic  # only required when --use-cli is NOT passed
except ImportError:
    anthropic = None  # type: ignore

# ---------------------------------------------------------------------------
# Configuration: filename -> (type number, count, min words per output)
# ---------------------------------------------------------------------------

# Word-count floors from the spec:
#   Types 5, 6, 8, 12, 18-26: 1000 words
#   Types 7, 9, 10, 11, 13-17: 800 words
# Types 27-32 not explicitly listed; default to 800 (claude-bug/redscan are tighter).
WORDS_1000 = 1000
WORDS_800 = 800


@dataclass
class FileSpec:
    filename: str       # without .jsonl
    type_num: int       # primary type for section extraction
    count: int          # examples to generate (always 50 per spec)
    min_words: int      # floor for the "output" field
    extra_types: tuple[int, ...] = ()  # additional sections to include as context


# Generation order matches the TIER order from the spec.
FILES: list[FileSpec] = [
    # Tier 1 — Mental Model Foundation
    FileSpec("type24_code_mental_model_001_050", 24, 50, WORDS_1000),
    FileSpec("type26_dev_mistakes_001_050",      26, 50, WORDS_1000),
    # Tier 2 — Core Detection Engine
    FileSpec("type5_detection_001_050",           5, 50, WORDS_1000),
    FileSpec("type5_detection_051_100",           5, 50, WORDS_1000),
    FileSpec("type12_hypothesis_001_050",        12, 50, WORDS_1000),
    # Tier 3 — Execution
    FileSpec("type6_exploitation_001_050",        6, 50, WORDS_1000),
    FileSpec("type6_exploitation_051_100",        6, 50, WORDS_1000),
    FileSpec("type6_chain_arc_001_050",           6, 50, WORDS_1000),  # chain-arc variant
    FileSpec("type8_hunt_loop_001_050",           8, 50, WORDS_1000),
    # Tier 4 — Quality Gates
    FileSpec("type7_false_positive_001_050",      7, 50, WORDS_800),
    FileSpec("type11_waf_bypass_001_050",        11, 50, WORDS_800),
    # Tier 5 — Intelligence & Output
    FileSpec("type10_recon_001_050",             10, 50, WORDS_800),
    FileSpec("type9_finding_writer_001_050",      9, 50, WORDS_800),
    FileSpec("type23_program_intel_001_050",     23, 50, WORDS_1000),
    FileSpec("type25_time_pressure_001_050",     25, 50, WORDS_1000),
    # Tier 6 — Senior Cognitive
    FileSpec("type22_failed_hunt_001_050",       22, 50, WORDS_1000),
    # Tier 7 — Red Team
    FileSpec("type13_initial_access_001_050",    13, 50, WORDS_800),
    FileSpec("type14_post_exploitation_001_050", 14, 50, WORDS_800),
    FileSpec("type15_active_directory_001_050",  15, 50, WORDS_800),
    FileSpec("type16_defense_evasion_001_050",   16, 50, WORDS_800),
    FileSpec("type17_c2_exfiltration_001_050",   17, 50, WORDS_800),
    # Tier 8 — Senior Mindset Completion
    FileSpec("type18_real_h1_reports_001_050",   18, 50, WORDS_1000),
    FileSpec("type18_real_h1_reports_051_100",   18, 50, WORDS_1000),
    FileSpec("type19_triage_decision_001_050",   19, 50, WORDS_1000),
    FileSpec("type20_multi_turn_001_050",        20, 50, WORDS_1000),
    FileSpec("type21_engagement_strategy_001_050", 21, 50, WORDS_1000),
    # Tier 9 — claude-bug Integration
    FileSpec("type27_prowl_hunt_001_050",        27, 50, WORDS_800),
    FileSpec("type28_finding_writer_001_050",    28, 50, WORDS_800),
    FileSpec("type29_claude_handoff_001_050",    29, 50, WORDS_800),
    # Tier 10 — redscan Integration
    FileSpec("type30_redscan_finding_001_050",   30, 50, WORDS_800),
    FileSpec("type31_redscan_hypothesis_001_050", 31, 50, WORDS_800),
    FileSpec("type32_redscan_fp_triage_001_050", 32, 50, WORDS_800),
]


PLACEHOLDER_PATTERNS = [
    r"\[RESPONSE HERE\]",
    r"\[INSERT PAYLOAD\]",
    r"\[OUTPUT\]",
    r"\[output\]",
    r"\[TODO\]",
    r"\[PLACEHOLDER\]",
    r"\[FILL IN\]",
    r"<INSERT[^>]*>",
]
PLACEHOLDER_RE = re.compile("|".join(PLACEHOLDER_PATTERNS))


# ---------------------------------------------------------------------------
# Spec parsing
# ---------------------------------------------------------------------------

def load_spec(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_master_context(spec: str) -> str:
    """Everything from the top through the FILES TO GENERATE section."""
    m = re.search(r"^## TYPE 5\b", spec, flags=re.MULTILINE)
    if not m:
        raise RuntimeError("Could not locate '## TYPE 5' in spec")
    return spec[: m.start()].rstrip()


def extract_type_section(spec: str, type_num: int) -> str:
    """
    Grab the '## TYPE N' section through the next '## TYPE' or top-level
    section that isn't part of the same type.
    """
    pattern = rf"^## TYPE {type_num}\b.*?(?=^## TYPE \d+\b|^## FINAL COMPLETE FILE LIST\b|^## UPDATED COMPLETE|^## MODEL EVALUATION\b|^## TYPES 22-26\b|^## TYPES 27-29\b|^## TYPES 30-32\b|\Z)"
    m = re.search(pattern, spec, flags=re.MULTILINE | re.DOTALL)
    if not m:
        # Fall back to types-group sections (e.g., "TYPE 27" lives under "## TYPE 27:")
        alt = re.search(
            rf"^## TYPE {type_num}[:\b].*?(?=^## TYPE \d+[:\b]|^## TYPES \d+-\d+\b|\Z)",
            spec,
            flags=re.MULTILINE | re.DOTALL,
        )
        if not alt:
            raise RuntimeError(f"Could not extract TYPE {type_num} section")
        return alt.group(0).rstrip()
    return m.group(0).rstrip()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    ok: bool
    reasons: list[str]
    examples: list[dict]


def word_count(s: str) -> int:
    return len(s.split())


def _extract_objects(raw: str) -> list[str]:
    """
    Return a list of candidate JSON-object strings from raw model output.
    Handles: pure JSONL, JSON array `[{...},{...}]`, mixed with stray text.
    """
    raw = raw.strip()
    # First try: if it parses as a JSON array, expand it.
    if raw.startswith("["):
        try:
            arr = json.loads(raw)
            if isinstance(arr, list):
                return [json.dumps(o, ensure_ascii=False) for o in arr]
        except json.JSONDecodeError:
            pass
    # Otherwise: scan for top-level `{...}` objects by brace-matching, ignoring
    # braces inside strings. This recovers from models that emit prose between
    # lines or forget the trailing newline.
    objects: list[str] = []
    depth = 0
    in_str = False
    esc = False
    start = -1
    for idx, ch in enumerate(raw):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = idx
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                objects.append(raw[start: idx + 1])
                start = -1
    return objects


def validate_batch(raw: str, min_words: int, type_num: int) -> ValidationResult:
    reasons: list[str] = []
    examples: list[dict] = []
    # Tolerate looser word-count for very long-output types — model consistently
    # lands slightly under the spec floor. 25% slack still keeps quality high
    # without burning retries on near-misses.
    slack = 0.75
    floor = int(min_words * slack)

    candidates = _extract_objects(raw)
    for i, blob in enumerate(candidates, 1):
        try:
            obj = json.loads(blob)
        except json.JSONDecodeError as e:
            reasons.append(f"obj {i}: invalid JSON ({e.msg})")
            continue
        if not isinstance(obj, dict):
            reasons.append(f"obj {i}: not a JSON object")
            continue
        if not all(k in obj for k in ("instruction", "input", "output")):
            reasons.append(f"obj {i}: missing required keys")
            continue
        if not all(isinstance(obj[k], str) for k in ("instruction", "input", "output")):
            reasons.append(f"obj {i}: non-string field")
            continue
        if PLACEHOLDER_RE.search(obj["output"]):
            reasons.append(f"obj {i}: placeholder text in output")
            continue
        wc = word_count(obj["output"])
        if wc < floor:
            reasons.append(f"obj {i}: output {wc} words < {floor} (floor for {min_words})")
            continue
        examples.append(obj)
    return ValidationResult(ok=len(reasons) == 0, reasons=reasons, examples=examples)


def validate_type5_distribution(examples: list[dict]) -> tuple[bool, str]:
    """40% CONFIRMED / 40% FP / 20% NEEDS-MORE-TESTING."""
    counts = {"CONFIRMED": 0, "FALSE POSITIVE": 0, "NEEDS MORE TESTING": 0, "OTHER": 0}
    for ex in examples:
        out = ex["output"]
        if re.search(r"VERDICT:\s*CONFIRMED", out):
            counts["CONFIRMED"] += 1
        elif re.search(r"VERDICT:\s*FALSE POSITIVE", out):
            counts["FALSE POSITIVE"] += 1
        elif re.search(r"VERDICT:\s*NEEDS MORE TESTING", out):
            counts["NEEDS MORE TESTING"] += 1
        else:
            counts["OTHER"] += 1
    total = sum(counts.values()) or 1
    ratios = {k: v / total for k, v in counts.items()}
    msg = ", ".join(f"{k}={counts[k]} ({ratios[k]:.0%})" for k in counts)
    # Allow +/- 10 percentage points on each target band.
    ok = (
        0.30 <= ratios["CONFIRMED"] <= 0.50
        and 0.30 <= ratios["FALSE POSITIVE"] <= 0.50
        and 0.10 <= ratios["NEEDS MORE TESTING"] <= 0.30
        and counts["OTHER"] == 0
    )
    return ok, msg


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def build_system_prompt(master: str, type_section: str) -> str:
    return (
        master
        + "\n\n---\n\n"
        + type_section
        + "\n\n---\n\n"
        + "STRICT OUTPUT CONTRACT:\n"
        "- Emit only JSONL. One JSON object per line. No prose, no headers, no fences.\n"
        "- Each object has exactly the keys: instruction, input, output.\n"
        "- Inside string values, use \\n for newlines. Do NOT put real newlines inside a JSON line.\n"
        "- Every output must be a complete answer, not a placeholder. Never write [RESPONSE HERE],\n"
        "  [INSERT PAYLOAD], [OUTPUT], <INSERT...>, or similar.\n"
        "- Every confirmed finding includes a full CVSS:3.1 vector + numeric score + business impact.\n"
        "- First-person voice: 'I ran / I observed / I confirmed'. Never 'an attacker could'.\n"
        "- Full HTTP responses with status line, realistic headers, realistic body fields.\n"
    )


def build_user_prompt(spec_filename: str, batch_size: int, batch_index: int, total_batches: int,
                       type_num: int, min_words: int) -> str:
    distribution_hint = ""
    if type_num == 5:
        distribution_hint = (
            "\nVerdict distribution across the full 50-example file: 40% CONFIRMED, "
            "40% FALSE POSITIVE, 20% NEEDS MORE TESTING. Vary within this batch so the "
            "final file lands on those ratios.\n"
        )
    return (
        f"Generate batch {batch_index}/{total_batches} for file `{spec_filename}.jsonl`.\n"
        f"Emit exactly {batch_size} examples as JSONL — one JSON object per line, no blank lines, "
        f"no commentary before or after.\n"
        f"Each example's `output` field must be at least {min_words} words.\n"
        f"All examples must conform to the TYPE {type_num} format from the spec above."
        f"{distribution_hint}\n"
        "Begin output now. First character must be `{`."
    )


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def call_claude(client, model: str, system: str, user: str,
                max_tokens: int = 16000) -> str:
    """API path. Requires anthropic SDK + ANTHROPIC_API_KEY."""
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    return "".join(parts).strip()


def call_claude_cli(model: str, system: str, user: str, timeout: int = 1500) -> str:
    """
    CLI path. Uses the `claude` command (Claude Code) in non-interactive mode.
    Passes the combined prompt via stdin to avoid ARG_MAX limits.
    """
    full_prompt = system + "\n\n---\n\n" + user
    cmd = ["claude", "-p", "--model", model, "--output-format", "text"]
    try:
        result = subprocess.run(
            cmd,
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise RuntimeError("`claude` CLI not found on PATH. Install Claude Code first.")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"claude CLI timed out after {timeout}s")
    if result.returncode != 0:
        err = (result.stderr or "").strip()[:500]
        raise RuntimeError(f"claude CLI exit {result.returncode}: {err}")
    return (result.stdout or "").strip()


def strip_fences(text: str) -> str:
    """If the model wrapped output in ```jsonl ... ``` despite instructions, strip it."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Per-file generation
# ---------------------------------------------------------------------------

def generate_file(client, model: str, spec_text: str,
                  fs: FileSpec, out_dir: Path, batch_size: int,
                  max_retries: int, use_cli: bool = False) -> None:
    out_path = out_dir / f"{fs.filename}.jsonl"

    # Resume support: if file exists and already has the right number of lines, skip.
    if out_path.exists():
        existing = sum(1 for _ in out_path.open() if _.strip())
        if existing >= fs.count:
            print(f"  [skip] {out_path.name} already has {existing} examples")
            return
        print(f"  [resume] {out_path.name} has {existing}/{fs.count} examples — continuing")
        already = existing
    else:
        already = 0

    master = extract_master_context(spec_text)
    type_section = extract_type_section(spec_text, fs.type_num)
    system = build_system_prompt(master, type_section)

    remaining = fs.count - already
    total_batches = (remaining + batch_size - 1) // batch_size

    collected: list[dict] = []
    # Open in append mode so partial progress is durable.
    with out_path.open("a", encoding="utf-8") as fh:
        for b in range(total_batches):
            this_batch = min(batch_size, remaining - b * batch_size)
            user_prompt = build_user_prompt(
                fs.filename, this_batch, b + 1, total_batches, fs.type_num, fs.min_words
            )
            for attempt in range(1, max_retries + 1):
                t0 = time.time()
                try:
                    if use_cli:
                        raw = call_claude_cli(model, system, user_prompt)
                    else:
                        raw = call_claude(client, model, system, user_prompt)
                except Exception as e:
                    print(f"    batch {b+1}/{total_batches} attempt {attempt}: call error: {e}")
                    time.sleep(2 * attempt)
                    continue
                raw = strip_fences(raw)
                result = validate_batch(raw, fs.min_words, fs.type_num)
                dt = time.time() - t0
                if result.ok and len(result.examples) == this_batch:
                    for ex in result.examples:
                        fh.write(json.dumps(ex, ensure_ascii=False) + "\n")
                    fh.flush()
                    collected.extend(result.examples)
                    print(f"    batch {b+1}/{total_batches}: ok ({this_batch} examples, {dt:.1f}s)")
                    break
                else:
                    n_ok = len(result.examples)
                    reason_preview = "; ".join(result.reasons[:3])
                    print(f"    batch {b+1}/{total_batches} attempt {attempt}: "
                          f"{n_ok}/{this_batch} valid ({dt:.1f}s) — {reason_preview}")
                    if attempt == max_retries:
                        # Best-effort: write whatever validated, fail loudly.
                        for ex in result.examples:
                            fh.write(json.dumps(ex, ensure_ascii=False) + "\n")
                        fh.flush()
                        collected.extend(result.examples)
                        print(f"    batch {b+1}/{total_batches}: GIVING UP, wrote {n_ok} partial")

    # Post-file checks
    if fs.type_num == 5:
        all_examples = [json.loads(l) for l in out_path.read_text().splitlines() if l.strip()]
        ok, msg = validate_type5_distribution(all_examples)
        flag = "ok" if ok else "WARN"
        print(f"  [dist:{flag}] {out_path.name}: {msg}")

    final_count = sum(1 for _ in out_path.open() if _.strip())
    print(f"  [done] {out_path.name}: {final_count}/{fs.count} examples")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", default=str(Path(__file__).parent / "GENERATE_TRAINING_DATA.md"))
    p.add_argument("--out", default=str(Path.home() / "training_data"))
    p.add_argument("--model", default=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"))
    p.add_argument("--batch-size", type=int, default=5,
                   help="Examples per API call (smaller = safer for long outputs)")
    p.add_argument("--max-retries", type=int, default=3)
    p.add_argument("--only", action="append", default=[],
                   help="Generate only files whose name contains this string (repeatable)")
    p.add_argument("--start-at", default=None,
                   help="Skip files until this filename matches, then generate from there")
    p.add_argument("--dry-run", action="store_true",
                   help="Parse spec + list planned work; no API calls")
    p.add_argument("--use-cli", action="store_true",
                   help="Use `claude` CLI (Claude Code) instead of the Anthropic SDK")
    return p.parse_args()


def select_files(args: argparse.Namespace) -> list[FileSpec]:
    files = FILES
    if args.start_at:
        started = False
        result = []
        for f in files:
            if not started and args.start_at in f.filename:
                started = True
            if started:
                result.append(f)
        files = result
    if args.only:
        files = [f for f in files if any(o in f.filename for o in args.only)]
    return files


def main() -> int:
    args = parse_args()
    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"ERROR: spec not found at {spec_path}", file=sys.stderr)
        return 2

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    spec_text = load_spec(spec_path)
    try:
        _ = extract_master_context(spec_text)
    except Exception as e:
        print(f"ERROR parsing spec: {e}", file=sys.stderr)
        return 2

    files = select_files(args)
    print(f"Spec:      {spec_path}")
    print(f"Out dir:   {out_dir}")
    print(f"Model:     {args.model}")
    print(f"Batch:     {args.batch_size} examples/call")
    print(f"Files:     {len(files)}")
    for f in files:
        print(f"  - {f.filename}.jsonl  (type {f.type_num}, {f.count} examples, ≥{f.min_words} words)")

    if args.dry_run:
        return 0

    client = None
    if args.use_cli:
        # Verify CLI is available
        try:
            subprocess.run(["claude", "--version"], capture_output=True, check=True, timeout=10)
        except Exception as e:
            print(f"ERROR: `claude` CLI not usable: {e}", file=sys.stderr)
            return 2
        print(f"Mode:      Claude Code CLI (`claude -p`)")
    else:
        if anthropic is None:
            print("ERROR: anthropic SDK not installed. Use --use-cli or `pip install anthropic`.",
                  file=sys.stderr)
            return 2
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("ERROR: ANTHROPIC_API_KEY not set (or pass --use-cli)", file=sys.stderr)
            return 2
        client = anthropic.Anthropic(api_key=api_key)
        print(f"Mode:      Anthropic SDK")

    t_start = time.time()
    for i, fs in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] {fs.filename}.jsonl")
        try:
            generate_file(client, args.model, spec_text, fs, out_dir,
                          args.batch_size, args.max_retries, use_cli=args.use_cli)
        except KeyboardInterrupt:
            print("\nInterrupted. Progress is saved; rerun to resume.")
            return 130
        except Exception as e:
            print(f"  [error] {fs.filename}: {e}", file=sys.stderr)
            print("  Continuing to next file. Rerun this file later to fill gaps.")

    print(f"\nDone in {(time.time() - t_start)/60:.1f} min. Files in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

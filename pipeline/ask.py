""""Ask the radar": guided questions answered only from this page's numbers.

Builds the facts of one site — the same facts as "Read the dance"
(summarize.py) plus the processing, the change types (types.json), the
"Why it changed" text and the "How to read it" basics shown on the page — and

  * writes them to web/layers/<site>/facts.json: the only context given to
    the experimental in-browser model, and the list of allowed numbers;
  * checks web/layers/<site>/ask.json (questions + answers, EN/ES): every
    number must exist in the facts, otherwise the script fails.

    python pipeline/ask.py --site cienaga           # write facts.json + check ask.json
    python pipeline/ask.py --site cienaga --check   # only check (CI)

The answers in ask.json are drafted offline and reviewed by the team (#25)
before they are published; `reviewed_by` stays empty until then.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from summarize import allowed_numbers, build_facts, load_site, unknown_numbers  # noqa: E402

# Text of the "How to read it" section of web/index.html (keep both in sync).
PAGE_FACTS = {
    "radar": "NISAR sends its own L-band pulse, about 24 cm long, and records the echo, so it sees day and night, "
             "through cloud and smoke. It revisits every 12 days.",
    "how_to_read": "Calm water reflects the pulse away and looks dark; rough ground, tree crowns and broken ice scatter "
                   "it back and look bright. A change in the echo is a change in roughness or moisture; floods, harvest "
                   "or ice movement are interpretations of it.",
    "collections": "NISAR data come in successive collections (BETA, PROVISIONAL, VALIDATED). The app only compares "
                   "two dates inside one collection and CRID.",
}


def _plain(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def build_ask_facts(site: dict, metas: dict[str, dict], why: dict | None, types: dict | None) -> dict:
    facts = build_facts(site, metas, why)
    pr = next(iter(metas.values()))["processing"]
    facts["processing"] = (f"{pr['speckle_filter']} {pr['window_px']}×{pr['window_px']} px speckle filter; "
                           "change = 10·log10(after/before) in dB")
    if why:
        facts["why_it_changed"] = _plain(why["en"]["html"])
    if types:
        facts["change_types_ai"] = {
            "method": "k-means (unsupervised AI) groups of how HH and HV changed together, named by fixed rules; "
                      "the names are interpretations, not ground truth",
            "share_of_area": {c["short_en"]: f"{c['pct']:.1f}%" for c in types["classes"]},
        }
    facts.update(PAGE_FACTS)
    return facts


def check_answers(ask: dict, allowed: set[str]) -> list[str]:
    """Problems found in ask.json: numbers that are not in the facts, empty or missing texts."""
    problems = []
    for q in ask["questions"]:
        for lang in ("en", "es"):
            item = q.get(lang) or {}
            for part in ("q", "a"):
                text = item.get(part, "")
                if not text.strip():
                    problems.append(f"{q['id']}.{lang}.{part}: empty")
                bad = unknown_numbers(text, allowed)
                if bad:
                    problems.append(f"{q['id']}.{lang}.{part}: numbers not in the facts {bad}")
    return problems


def load_types(layers: Path, site_id: str) -> dict | None:
    path = layers / site_id / "types.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--site", required=True)
    p.add_argument("--layers", default="web/layers")
    p.add_argument("--check", action="store_true", help="Only check ask.json against the facts (no writing)")
    args = p.parse_args()

    layers = Path(args.layers)
    site, metas, why = load_site(layers, args.site)
    facts = build_ask_facts(site, metas, why, load_types(layers, args.site))
    allowed = allowed_numbers(facts)
    if not args.check:
        out = layers / args.site / "facts.json"
        out.write_text(json.dumps(facts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Facts written to {out}")

    ask_path = layers / args.site / "ask.json"
    if not ask_path.exists():
        print("No ask.json for this site; nothing to check.")
        return
    problems = check_answers(json.loads(ask_path.read_text(encoding="utf-8")), allowed)
    if problems:
        raise SystemExit("ask.json has problems:\n  " + "\n  ".join(problems))
    print(f"ask.json OK: every number is in the facts ({ask_path})")


if __name__ == "__main__":
    main()

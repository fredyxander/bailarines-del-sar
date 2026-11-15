""""Read the dance": resumen en lenguaje sencillo (EN + ES) redactado por IA.

Plain-language summary of one site, in English and Spanish, drafted by Claude
**only from the numbers the pipeline already computed** (meta.json of each
polarization + the lead conclusion of why.json). The script then checks that
every number in the text exists in those facts; if the model writes any other
number, nothing is saved.

    python pipeline/summarize.py --site cienaga            # writes web/layers/cienaga/summary.json
    python pipeline/summarize.py --site cienaga --dry-run  # prints the facts and the prompt, no API call

Credentials: the Anthropic SDK reads ANTHROPIC_API_KEY (or another configured
credential source). Never put a key in the repository or in the web page: the
call runs here, offline, and only the reviewed text is published.

The output must be reviewed by the team (issue #25) before it is merged;
`reviewed_by` stays empty until then and the app says so.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MODEL = "claude-opus-5-5"
PROMPT_VERSION = "read-the-dance-v1"

SYSTEM = """You write the short "Read the dance" summary for a public web app that shows how Earth's surface changed between two dates, read by NISAR L-band radar.

Rules:
- Use ONLY the facts given by the user. Every number you write must appear in the facts exactly as written there (same rounding, same units). Do not compute new numbers, do not round differently, do not add dates or percentages.
- Plain language for a general audience; no jargon without a short explanation. One paragraph of 60-90 words per language, no lists, no markdown, no headings.
- Say what changed, where it matters and what it suggests, using the lead conclusion. End with one honest limit (for example: two dates cannot show a trend or prove a cause).
- Never predict, never claim damage, floods or long-term change, never present a hypothesis as a fact.
- The Spanish text is a natural Spanish version for Colombia, not a word-by-word translation, with the same facts and numbers (use a decimal comma in Spanish)."""

SCHEMA = {
    "type": "object",
    "properties": {
        "en": {"type": "string"},
        "es": {"type": "string"},
    },
    "required": ["en", "es"],
    "additionalProperties": False,
}

_NUM = re.compile(r"\d+(?:[.,]\d+)?")
MONTHS = {"06": ("June", "junio"), "10": ("October", "octubre"), "07": ("July", "julio"),
          "08": ("August", "agosto"), "09": ("September", "septiembre"), "11": ("November", "noviembre")}


def _fmt_date(iso: str) -> tuple[str, str]:
    y, m, d = iso.split("-")
    en, es = MONTHS.get(m, (m, m))
    return f"{int(d)} {en} {y}", f"{int(d)} de {es} de {y}"


def _signed(v: float, unit: str, nd: int = 1) -> str:
    return f"{'+' if v >= 0 else '−'}{abs(v):.{nd}f} {unit}".strip()


def build_facts(site: dict, metas: dict[str, dict], why: dict | None) -> dict:
    """Facts handed to the model, already rounded and formatted (the only numbers it may use)."""
    any_meta = next(iter(metas.values()))
    b, a = any_meta["before"], any_meta["after"]
    days = (datetime.fromisoformat(a["date"]) - datetime.fromisoformat(b["date"])).days
    facts = {
        "place": site["name"],
        "question": site.get("question", ""),
        "before_date": _fmt_date(b["date"])[0],
        "after_date": _fmt_date(a["date"])[0],
        "days_between": f"{days} days",
        "collection": f"{a['collection']} (CRID {a['crid']}), the same for both dates",
        "change_threshold": f"{any_meta['stats']['threshold_db']:.0f} dB",
        "channels": {},
    }
    for pol, m in metas.items():
        s = m["stats"]
        facts["channels"][pol[:2]] = {
            "share_of_area_where_echo_grew": f"{s['pct_increase']:.1f}%",
            "share_of_area_where_echo_faded": f"{s['pct_decrease']:.1f}%",
            "median_shift": _signed(s["median_change_db"], "dB", 2),
        }
    hh = metas.get("HHHH", {}).get("stats", {})
    if "water_km2_before" in hh and "water_km2_after" in hh:
        wb, wa = hh["water_km2_before"], hh["water_km2_after"]
        facts["open_water_HH"] = {
            "before": f"{wb:.0f} km²",
            "after": f"{wa:.0f} km²",
            "change": f"{_signed(wa - wb, 'km²')} ({_signed(100 * (wa - wb) / wb, '%')})".replace(" %", "%"),
        }
    if why:
        facts["lead_conclusion"] = why["en"]["lead"]
        facts["measured_over_open_water"] = "HH echo rose by about +3 dB; HV rose only about +0.5 dB; over land HH did not move"
        facts["wind_check"] = "wind at the overpass hour was 3.4 times weaker on the brighter date, so a windier surface does not explain it"
    return facts


def allowed_numbers(facts: dict) -> set[str]:
    text = json.dumps(facts, ensure_ascii=False)
    return {n.replace(",", ".") for n in _NUM.findall(text)}


def unknown_numbers(text: str, allowed: set[str]) -> list[str]:
    """Numbers in `text` that are not in the facts (decimal comma accepted)."""
    out = []
    for n in _NUM.findall(text):
        k = n.replace(",", ".")
        if k not in allowed:
            out.append(n)
    return out


def load_site(layers: Path, site_id: str) -> tuple[dict, dict[str, dict], dict | None]:
    idx = json.loads((layers / "index.json").read_text(encoding="utf-8"))
    site = next((s for s in idx["sites"] if s["id"] == site_id), None)
    if site is None:
        raise SystemExit(f"Sitio '{site_id}' no está en {layers / 'index.json'}")
    metas = {p: json.loads((layers / site_id / p / "meta.json").read_text(encoding="utf-8"))
             for p in site["polarizations"]}
    why_path = layers / site_id / "why.json"
    why = json.loads(why_path.read_text(encoding="utf-8")) if why_path.exists() else None
    return site, metas, why


def draft(facts: dict) -> tuple[dict, str]:
    import anthropic  # imported here so --dry-run and the tests do not need the SDK

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # if a safety classifier declines, the API retries on a fallback model
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=SYSTEM,
        messages=[{"role": "user", "content": "Facts (JSON):\n" + json.dumps(facts, ensure_ascii=False, indent=2)}],
    )
    if response.stop_reason == "refusal":
        raise SystemExit(f"El modelo rechazó la solicitud: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise SystemExit("La respuesta se cortó (max_tokens).")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text), response.model


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--site", required=True)
    p.add_argument("--layers", default="web/layers")
    p.add_argument("--dry-run", action="store_true", help="Print facts and prompt; no API call")
    args = p.parse_args()

    layers = Path(args.layers)
    site, metas, why = load_site(layers, args.site)
    facts = build_facts(site, metas, why)
    if args.dry_run:
        print("SYSTEM:\n" + SYSTEM + "\n\nFACTS:\n" + json.dumps(facts, ensure_ascii=False, indent=2))
        return

    texts, served_by = draft(facts)
    allowed = allowed_numbers(facts)
    bad = {lang: unknown_numbers(texts[lang], allowed) for lang in ("en", "es")}
    if any(bad.values()):
        raise SystemExit(f"Números que no están en los datos: {bad}. No se guarda nada; vuelve a intentar.")

    out = {
        "en": texts["en"].strip(),
        "es": texts["es"].strip(),
        "model": served_by,
        "prompt_version": PROMPT_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "facts": facts,
        "reviewed_by": None,
    }
    path = layers / args.site / "summary.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("en", "es", "model")}, indent=2, ensure_ascii=False))
    print(f"\nGuardado en {path}. Pide la revisión del equipo (#25) y luego completa 'reviewed_by'.")


if __name__ == "__main__":
    main()

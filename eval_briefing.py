#!/usr/bin/env python3
"""
BRIEFING Eval Suite
===================

Deterministische Qualitäts-/Regressions-Suite für die BRIEFING-Content-Pipeline
(zehnx.me Intelligence-Format). Prüft generierte Episoden-Scripts gegen die im
Generator dokumentierten Standards, gibt pro Prüfung 🟢/🟡/🔴 aus und endet mit
einem Exit-Code, der sich als CI-Gate nutzen lässt.

Jede Prüfung ist auf eine konkrete Quelle zurückführbar (kein erfundenes Kriterium):
- SPEC  = ~/.claude/commands/briefing.md  (Format-DNA, Struktur, Qualitätskriterien)
- TOM   = dokumentierte Redaktions-Standards (≥3 Quellen/Story, ≥5 Domains/Folge)

Aufruf:
    python3 eval_briefing.py                      # prüft ../BRIEFING_*_script.md
    python3 eval_briefing.py pfad/zu/script.md    # prüft konkrete Datei(en)

Exit-Code: 0 wenn kein 🔴, sonst 1.
"""

from __future__ import annotations

import glob
import os
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# Rubrik: Schwellen mit Herkunft. Wer die Latte ändern will, ändert sie HIER.  #
# --------------------------------------------------------------------------- #
MIN_SOURCES_TOTAL = 5        # SPEC Schritt 1 "Mindestens 5 unabhängige Quellen" / TOM 5 Domains/Folge
MIN_SOURCES_PER_BLOCK = 3    # SPEC Qualitätskriterien "Mindestens 3 unabhängige Quellen" / TOM ≥3/Story
MIN_BLOCKS = 3              # SPEC Schritt 2 "3–4 THEMATISCHE BLÖCKE"
MAX_BLOCKS = 4             # dito; 5 Blöcke -> WARN (toleriert, aber außerhalb der Vorgabe)
WORDS_MIN = 1500            # SPEC Länge 12–20 Min bei ~135 wpm dt. TTS -> ~1620–2700, gepuffert
WORDS_MAX = 3000
WORDS_SOFT = 300           # Toleranzband für 🟡 statt 🔴 an den Rändern

DISCLAIMER = ("Stimmen in diesem Format sind KI-generiert. "
              "Redaktion und inhaltliche Verantwortung: Thomas Frerich.")

# eigene Domain zählt NICHT als unabhängige Quelle
OWN_DOMAINS = {"zehnx.me", "zehnx.com"}

# Überschriften, hinter denen die Quellen-Dokumentation stehen kann (Format variiert je Folge)
SOURCE_HEADING_RE = re.compile(r"quellen|recherche|claim-audit|produktionsnotizen|sources", re.I)

# grobe englische Marker für die (heuristische) Titel-Sprachprüfung
EN_MARKERS = {"why", "the", "is", "are", "what", "how", "breaking", "news",
              "self", "know", "doesn't", "its", "power", "leaves"}

DOMAIN_RE = re.compile(
    # host + optionale Sub-Domains + Whitelist-TLD; '*' erlaubt auch Single-Dot (codersera.com)
    r"\b([a-z0-9][a-z0-9\-]*(?:\.[a-z0-9\-]+)*\.(?:com|de|org|ai|dev|me|eu|io|net|gov|edu|co|news))\b"
)

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
ICON = {PASS: "🟢", WARN: "🟡", FAIL: "🔴"}
RANK = {PASS: 0, WARN: 1, FAIL: 2}


@dataclass
class Result:
    name: str
    status: str
    detail: str


# --------------------------------------------------------------------------- #
# Parsing                                                                      #
# --------------------------------------------------------------------------- #
def split_sections(text: str) -> "OrderedDict[str, str]":
    """Zerlegt das Script an '## '-Überschriften in {Überschrift: Body}."""
    sections: "OrderedDict[str, str]" = OrderedDict()
    current = "_preamble"
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            sections[current] = "\n".join(buf).strip()
            current = m.group(1).strip()
            buf = []
        else:
            buf.append(line)
    sections[current] = "\n".join(buf).strip()
    return sections


def block_headings(sections) -> list[str]:
    return [h for h in sections if re.match(r"BLOCK\b", h, re.I)]


def spoken_text(sections) -> str:
    """Gesprochener Anteil: INTRO..OUTRO + DISCLAIMER, ohne Überschriftenzeilen,
    ohne Quellen-/Notiz-Sektionen (die werden nicht vorgelesen)."""
    parts = []
    for heading, body in sections.items():
        if heading in ("_preamble",):
            continue
        if SOURCE_HEADING_RE.search(heading):
            continue
        parts.append(body)
    return "\n".join(parts)


def title_line(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def find_source_section(sections) -> str | None:
    for heading, body in sections.items():
        if SOURCE_HEADING_RE.search(heading):
            return body
    return None


def domains_in(text: str) -> set[str]:
    found = {d.lower() for d in DOMAIN_RE.findall(text.lower())}
    return {d for d in found if d not in OWN_DOMAINS}


# --------------------------------------------------------------------------- #
# Checks: jeweils (raw, sections) -> Result                                    #
# --------------------------------------------------------------------------- #
def check_title_format(raw, sections) -> Result:
    t = title_line(raw)
    if re.match(r"^BRIEFING\s+(\d{2,3}|—\s*Sonderfolge).*", t):
        return Result("Titel-Format", PASS, f"'{t}'")
    return Result("Titel-Format", FAIL, f"erwartet 'BRIEFING NNN — …', gefunden '{t}'")


def check_title_language(raw, sections) -> Result:
    t = title_line(raw)
    subtitle = t.split("—", 1)[1] if "—" in t else t
    tokens = {w.lower().strip(".,:") for w in subtitle.split()}
    hits = tokens & EN_MARKERS
    if len(hits) >= 2:
        return Result("Titel Deutsch", WARN,
                      f"wirkt englisch ({', '.join(sorted(hits))}); SPEC: Titel auf Deutsch")
    return Result("Titel Deutsch", PASS, "deutsch")


def check_intro(raw, sections) -> Result:
    body = next((b for h, b in sections.items() if h.upper() == "INTRO"), None)
    if body is None:
        return Result("Intro", FAIL, "keine INTRO-Sektion")
    miss = []
    if not re.search(r"dies ist briefing", body, re.I):
        miss.append("'Dies ist Briefing'")
    if "zehnx punkt me" not in body.lower():
        miss.append("'zehnx punkt me'")
    if miss:
        return Result("Intro", WARN, "fehlt: " + ", ".join(miss))
    return Result("Intro", PASS, "Format-Identifikation vorhanden")


def check_blocks(raw, sections) -> Result:
    n = len(block_headings(sections))
    if MIN_BLOCKS <= n <= MAX_BLOCKS:
        return Result("Blöcke", PASS, f"{n} thematische Blöcke")
    if n in (MIN_BLOCKS - 1, MAX_BLOCKS + 1) and n >= 2:
        return Result("Blöcke", WARN, f"{n} Blöcke (SPEC: {MIN_BLOCKS}–{MAX_BLOCKS})")
    return Result("Blöcke", FAIL, f"{n} Blöcke (SPEC: {MIN_BLOCKS}–{MAX_BLOCKS})")


def check_outro(raw, sections) -> Result:
    body = next((b for h, b in sections.items() if h.upper() == "OUTRO"), None)
    if body is None:
        return Result("Outro", FAIL, "keine OUTRO-Sektion")
    low = body.lower()
    if "complete" in low and "next shift is already underway" in low:
        return Result("Outro", PASS, "Signature-Closing vorhanden")
    return Result("Outro", WARN, "Standard-Closing ('… complete. The next shift …') unvollständig")


def check_disclaimer(raw, sections) -> Result:
    norm = re.sub(r"\s+", " ", raw)
    if DISCLAIMER in norm:
        return Result("Disclaimer", PASS, "wörtlich vorhanden")
    if re.search(r"KI-generiert", raw) and re.search(r"Thomas Frerich", raw):
        return Result("Disclaimer", WARN, "sinngemäß, aber nicht im Standard-Wortlaut")
    return Result("Disclaimer", FAIL, "fehlt")


def check_one_voice(raw, sections) -> Result:
    # BRIEFING = eine Stimme, kein Dialog. Sucht Sprecher-Labels im gesprochenen Teil.
    spoken = spoken_text(sections)
    labels = re.findall(r"(?m)^\s*(Jan|Clara|Sprecher(?:in)?\s*[AB12]?|Stimme\s*[AB12])\s*:", spoken)
    if labels:
        return Result("Eine Stimme", FAIL, f"Dialog-Marker gefunden: {sorted(set(labels))}")
    return Result("Eine Stimme", PASS, "kein Dialog-Marker")


def check_domain_pronunciation(raw, sections) -> Result:
    spoken = spoken_text(sections)
    # Überschriften sind bereits raus; jetzt dotted 'zehnx.me' im Sprechtext = Aussprachefehler
    dotted = len(re.findall(r"zehnx\.me", spoken, re.I))
    spelled = "zehnx punkt me" in spoken.lower()
    if dotted:
        return Result("Domain-Aussprache", FAIL,
                      f"{dotted}× 'zehnx.me' im Sprechtext (SPEC: 'zehnx punkt me')")
    if not spelled:
        return Result("Domain-Aussprache", WARN, "'zehnx punkt me' kommt nicht vor")
    return Result("Domain-Aussprache", PASS, "'zehnx punkt me' korrekt")


def check_style_enumeration(raw, sections) -> Result:
    spoken = spoken_text(sections)
    hits = re.findall(r"\b(Erstens|Zweitens|Drittens|Viertens)\b", spoken)
    if hits:
        return Result("Anti-Vorlese-Stil", WARN,
                      f"Aufzählungs-Stakkato: {', '.join(sorted(set(hits)))} (SPEC: vermeiden)")
    return Result("Anti-Vorlese-Stil", PASS, "keine mechanische Aufzählung")


def check_length(raw, sections) -> Result:
    words = len(spoken_text(sections).split())
    if WORDS_MIN <= words <= WORDS_MAX:
        return Result("Länge", PASS, f"{words} Wörter (~{words // 135} Min)")
    if (WORDS_MIN - WORDS_SOFT) <= words <= (WORDS_MAX + WORDS_SOFT):
        return Result("Länge", WARN, f"{words} Wörter, knapp außerhalb 12–20 Min")
    return Result("Länge", FAIL, f"{words} Wörter, außerhalb 12–20 Min ({WORDS_MIN}–{WORDS_MAX})")


def check_sources_total(raw, sections) -> Result:
    src = find_source_section(sections)
    if src is None:
        return Result("Quellen gesamt", FAIL, "keine Quellen-/Recherche-Sektion")
    doms = domains_in(src)
    n = len(doms)
    if n >= MIN_SOURCES_TOTAL:
        return Result("Quellen gesamt", PASS, f"{n} unabhängige Domains")
    if n >= 3:
        return Result("Quellen gesamt", WARN, f"nur {n} Domains (Ziel ≥{MIN_SOURCES_TOTAL})")
    return Result("Quellen gesamt", FAIL, f"nur {n} Domains (Ziel ≥{MIN_SOURCES_TOTAL})")


def check_sources_per_block(raw, sections) -> Result:
    src = find_source_section(sections)
    if src is None:
        return Result("Quellen/Block", FAIL, "keine Quellen-Sektion")
    # Quellen-Sektion an '**Block N' oder 'Block N' unterteilen
    chunks = re.split(r"(?im)^\s*\**\s*block\s*\d", src)
    per_block = [len(domains_in(c)) for c in chunks[1:]]  # chunks[0] = Präambel vor erstem Block
    if not per_block:
        return Result("Quellen/Block", WARN, "keine Block-Struktur in Quellen (nicht prüfbar)")
    weak = [i + 1 for i, c in enumerate(per_block) if c < MIN_SOURCES_PER_BLOCK]
    if not weak:
        return Result("Quellen/Block", PASS,
                      f"alle {len(per_block)} Blöcke ≥{MIN_SOURCES_PER_BLOCK} Domains")
    return Result("Quellen/Block", WARN,
                  f"Block(s) {weak} < {MIN_SOURCES_PER_BLOCK} Domains")


CHECKS = [
    check_title_format,
    check_title_language,
    check_intro,
    check_blocks,
    check_outro,
    check_disclaimer,
    check_one_voice,
    check_domain_pronunciation,
    check_style_enumeration,
    check_length,
    check_sources_total,
    check_sources_per_block,
]


# --------------------------------------------------------------------------- #
# Runner + Report                                                             #
# --------------------------------------------------------------------------- #
def episode_id(path: str) -> str:
    base = os.path.basename(path)
    m = re.search(r"BRIEFING[_ ]?([0-9]{3}|SONDER[_A-Z0-9]*)", base, re.I)
    return m.group(1) if m else base.replace("_script.md", "")


def evaluate(path: str):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    sections = split_sections(raw)
    return [c(raw, sections) for c in CHECKS]


def main(argv):
    args = argv[1:]
    here = os.path.dirname(os.path.abspath(__file__))
    if args:
        paths = args
    else:
        # Reihenfolge: mitgelieferte Fixtures (self-contained) -> lokale echte Scripts eine Ebene höher
        paths = sorted(glob.glob(os.path.join(here, "fixtures", "BRIEFING_*_script.md")))
        if not paths:
            paths = sorted(glob.glob(os.path.join(here, "..", "BRIEFING_*_script.md")))
    if not paths:
        print("Keine BRIEFING_*_script.md gefunden. "
              "Übergib Pfade als Argumente oder lege Scripts in fixtures/ ab.")
        return 2

    print("=" * 64)
    print(" BRIEFING Eval Suite  ·  Qualitäts-/Regressions-Report")
    print("=" * 64)

    episodes = OrderedDict()
    for p in paths:
        eid = episode_id(p)
        results = evaluate(p)
        episodes[eid] = results
        worst = max((r.status for r in results), key=lambda s: RANK[s])
        print(f"\n▶ BRIEFING {eid}   {ICON[worst]}  ({os.path.basename(p)})")
        for r in results:
            print(f"   {ICON[r.status]}  {r.name:<20} {r.detail}")

    # Matrix
    check_names = [r.name for r in next(iter(episodes.values()))]
    print("\n" + "-" * 64)
    print(" Matrix  (Zeilen = Prüfung, Spalten = Episode)")
    print("-" * 64)
    header = "  " + " ".join(f"{e:>6}" for e in episodes)
    print(f"{'':<22}{header}")
    for i, name in enumerate(check_names):
        row = " ".join(f"{ICON[episodes[e][i].status]:>6}" for e in episodes)
        print(f"{name:<22}  {row}")

    # Summary
    total = sum(len(v) for v in episodes.values())
    counts = {PASS: 0, WARN: 0, FAIL: 0}
    for v in episodes.values():
        for r in v:
            counts[r.status] += 1
    print("\n" + "-" * 64)
    green_pct = 100 * counts[PASS] / total if total else 0
    print(f" Ergebnis: {ICON[PASS]} {counts[PASS]}   "
          f"{ICON[WARN]} {counts[WARN]}   {ICON[FAIL]} {counts[FAIL]}   "
          f"({green_pct:.0f}% grün von {total} Prüfungen über {len(episodes)} Episoden)")
    fails = counts[FAIL]
    print(f" Gate: {'BESTANDEN (kein 🔴)' if fails == 0 else f'DURCHGEFALLEN ({fails}× 🔴)'}")
    print("=" * 64)
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

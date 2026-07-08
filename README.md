# BRIEFING Eval Suite

[![eval-ci](https://github.com/SCHLUESSELKIND/briefing-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/SCHLUESSELKIND/briefing-eval/actions/workflows/ci.yml)

Eine kleine, dependency-freie **Qualitäts- und Regressions-Suite** für die
BRIEFING-Content-Pipeline (das Intelligence-Audioformat von zehnx.me). Sie prüft
jedes generierte Episoden-Script gegen die Standards, die im Generator selbst
dokumentiert sind, gibt pro Prüfung 🟢/🟡/🔴 aus und endet mit einem Exit-Code,
der sich als CI-Gate verwenden lässt.

> Warum es das gibt: Ein AI-Content-Generator ohne Eval ist ein Blindflug. Diese
> Suite macht die Qualitätskriterien maschinell überprüfbar, statt sie bei jeder
> Folge per Hand durchzugehen, und fängt Regressionen automatisch.

## Ausführen

```bash
python3 eval_briefing.py                    # ohne Argumente: prüft die Fixtures in fixtures/
python3 eval_briefing.py pfad/zu/script.md  # prüft konkrete Datei(en)
```

Kein `pip install` nötig, reine Standardbibliothek. Exit-Code `0`, wenn kein 🔴,
sonst `1`. Das Repo bringt zwei synthetische Beispiel-Scripts in `fixtures/` mit,
damit der Report ohne weitere Daten sofort läuft:

- `BRIEFING_900` — kompakte, saubere Folge: besteht alle Checks bis auf den
  Längen-Check (bewusst kürzer als eine echte Folge, zeigt den Längen-Check aktiv).
- `BRIEFING_901` — bewusst fehlerhaft: englischer Titel, „zehnx.me" im Sprechtext,
  Aufzählungs-Stakkato, fehlender Disclaimer, keine Quellen. Löst mehrere 🔴/🟡 aus.

Der gebündelte Lauf fällt also erwartungsgemäß durchs Gate — genau so demonstriert
er, dass das Gate funktioniert.

## Tests & CI

Das Werkzeug testet sich selbst: `test_eval.py` (stdlib `unittest`, keine Deps)
prüft gegen die Fixtures, dass die saubere Folge besteht und die fehlerhafte die
richtigen Findings auslöst, plus einen Regressionstest für die Domain-Erkennung.

```bash
python3 -m unittest -v test_eval
```

Ein GitHub-Actions-Workflow (`.github/workflows/ci.yml`) fährt diese Self-Tests
bei jedem Push auf Python 3.10 und 3.12. Status siehe Badge oben.

## Was geprüft wird

Jede Prüfung ist auf eine Quelle zurückführbar, keine ist erfunden.
`SPEC` = der BRIEFING-Generator-Prompt (die Format-Vorgabe), `TOM` = die
dokumentierten Redaktions-Standards.

| Prüfung | Kriterium | Herkunft |
|---|---|---|
| Titel-Format | `# BRIEFING NNN — …` | SPEC Schritt 4 |
| Titel Deutsch | Titel auf Deutsch (Heuristik) | SPEC Qualitätskriterien |
| Intro | „Dies ist Briefing" + „zehnx punkt me" | SPEC Schritt 2 |
| Blöcke | 3–4 thematische Blöcke | SPEC Schritt 2 |
| Outro | Signature-Closing „… complete. The next shift …" | SPEC Schritt 2 |
| Disclaimer | wörtlicher KI-Disclaimer | SPEC Schritt 2 / Qualitätskriterien |
| Eine Stimme | kein Dialog-/Sprecher-Marker | SPEC Format-DNA |
| Domain-Aussprache | „zehnx punkt me" statt „zehnx.me" im Sprechtext | SPEC Qualitätskriterien |
| Anti-Vorlese-Stil | keine „Erstens/Zweitens"-Aufzählung | SPEC Schreibstil |
| Länge | ~12–20 Min (Wortzahl-Proxy) | SPEC Format-DNA |
| Quellen gesamt | ≥5 unabhängige Domains dokumentiert | SPEC Schritt 1 / TOM 5 Domains/Folge |
| Quellen/Block | ≥3 Domains je inhaltlichem Block | SPEC Qualitätskriterien / TOM ≥3/Story |

Alle Schwellen stehen als benannte Konstanten oben in `eval_briefing.py` und lassen
sich an einer Stelle anpassen.

## Was der Lauf auf den echten Produktions-Episoden gefunden hat

_(4 reale Episoden, 48 Prüfungen; die Episoden selbst sind nicht Teil dieses
Repos, die mitgelieferten `fixtures/` erzeugen einen eigenen Beispiel-Report.)_

71 % grün, 10× 🟡, 4× 🔴, Gate rot. Die roten Punkte sind echte Findings, keine
Fehlalarme:

- **BRIEFING 001** (früheste Folge): englischer Titel, sagt 7× „zehnx.me" statt
  „zehnx punkt me", kein Standard-Disclaimer, keine dokumentierten Quellen.
  Die späteren Folgen haben genau das abgestellt, die Suite macht diesen
  Reifungssprung sichtbar.
- **BRIEFING 003**: dokumentiert Quellen als internen „Claim-Audit" ohne
  verifizierbare URLs → nicht maschinell prüfbar, zu Recht rot.
- **002/SONDER**: robust; 002 nur 🟡, weil ein Block seine Quellen als
  Outlet-Namen (CNBC, Yahoo Finance) statt als URL nennt.

Damit tut die Suite genau, was sie soll: Sie trennt „klingt gut" von
„ist nachweisbar sauber".

## Designentscheidungen & Grenzen

- **Nur deterministische Checks.** Bewusst kein LLM im Kern, damit der Lauf
  reproduzierbar, gratis und schnell ist. Der eine unvermeidlich weiche Punkt
  („klingt wie gesprochen, nicht vorgelesen") ist heute nur als grobe
  Aufzählungs-Heuristik abgebildet.
- **Quellen = geparste Domains.** Als Outlet-Name genannte Quellen ohne URL
  werden absichtlich nicht mitgezählt und als 🟡 sichtbar gemacht, statt still
  durchzuwinken.
- **Titel-Sprache** ist eine Heuristik (englische Marker-Wörter), daher 🟡, nie 🔴.

## Roadmap

- LLM-as-Judge als optionaler Zusatz-Layer für den Sprach-/Ton-Check (mit festem
  Rubric-Prompt, Ergebnis neben den deterministischen Checks).
- `--json`-Ausgabe für die Anbindung an CI / ein Dashboard.
- Zweite Stimmenlage abbilden (zehnx Daily/Weekly = Zwei-Stimmen-Format), damit
  die „Eine Stimme"-Prüfung formatabhängig greift.
- Schwellen pro Format aus einer `rubric.yaml` laden statt aus Konstanten.

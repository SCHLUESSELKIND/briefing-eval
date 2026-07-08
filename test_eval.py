"""
Selbst-Tests der BRIEFING Eval Suite.

Testet nicht die Episoden, sondern das Prüfwerkzeug: Läuft gegen die beiden
mitgelieferten Fixtures und stellt sicher, dass die saubere Folge besteht und
die bewusst fehlerhafte die erwarteten 🔴/🟡 auslöst. Dazu Unit-Tests für die
Domain-Erkennung (inkl. Regressionstest für einen früher gefixten Regex-Bug).

Reine Standardbibliothek (unittest), keine Dependencies:
    python3 -m unittest -v test_eval
"""

import os
import unittest

from eval_briefing import evaluate, domains_in, split_sections, PASS, WARN, FAIL

HERE = os.path.dirname(os.path.abspath(__file__))


def results(fixture_name):
    """Fixture prüfen und {Prüfname: Status} zurückgeben."""
    path = os.path.join(HERE, "fixtures", fixture_name)
    return {r.name: r.status for r in evaluate(path)}


class CleanFixture(unittest.TestCase):
    """BRIEFING_900: kompakte, saubere Folge. Alles grün außer Länge (bewusst kurz)."""

    @classmethod
    def setUpClass(cls):
        cls.r = results("BRIEFING_900_script.md")

    def test_disclaimer_passes(self):
        self.assertEqual(self.r["Disclaimer"], PASS)

    def test_domain_pronunciation_passes(self):
        self.assertEqual(self.r["Domain-Aussprache"], PASS)

    def test_sources_pass(self):
        self.assertEqual(self.r["Quellen gesamt"], PASS)

    def test_title_is_german(self):
        self.assertEqual(self.r["Titel Deutsch"], PASS)

    def test_single_voice(self):
        self.assertEqual(self.r["Eine Stimme"], PASS)

    def test_length_flags_compact_fixture(self):
        # Fixture ist bewusst kürzer als eine echte 12–20-Min-Folge -> Länge muss flaggen.
        self.assertEqual(self.r["Länge"], FAIL)


class BrokenFixture(unittest.TestCase):
    """BRIEFING_901: absichtlich fehlerhaft. Muss die passenden Findings auslösen."""

    @classmethod
    def setUpClass(cls):
        cls.r = results("BRIEFING_901_script.md")

    def test_disclaimer_missing(self):
        self.assertEqual(self.r["Disclaimer"], FAIL)

    def test_domain_pronunciation_fails(self):
        self.assertEqual(self.r["Domain-Aussprache"], FAIL)

    def test_title_flagged_as_english(self):
        self.assertEqual(self.r["Titel Deutsch"], WARN)

    def test_sources_missing(self):
        self.assertEqual(self.r["Quellen gesamt"], FAIL)

    def test_enumeration_style_flagged(self):
        self.assertEqual(self.r["Anti-Vorlese-Stil"], WARN)


class DomainParsing(unittest.TestCase):
    """Unit-Tests für die Domain-Erkennung."""

    def test_single_dot_domain_counted(self):
        # Regressionstest: der ursprüngliche Regex verlangte fälschlich zwei Punkte
        # und zählte 'codersera.com' nicht mit. Darf nie wieder passieren.
        doms = domains_in("Quelle: codersera.com und mager.co")
        self.assertIn("codersera.com", doms)
        self.assertIn("mager.co", doms)

    def test_subdomain_counted(self):
        self.assertIn("digital-strategy.ec.europa.eu",
                      domains_in("Quelle: digital-strategy.ec.europa.eu"))

    def test_own_domain_excluded(self):
        # zehnx.me ist keine unabhängige Quelle.
        doms = domains_in("zehnx.me und reuters.com")
        self.assertNotIn("zehnx.me", doms)
        self.assertIn("reuters.com", doms)


class Parsing(unittest.TestCase):
    def test_split_sections_finds_headings(self):
        text = "# Titel\n\npre\n\n## INTRO\nhallo\n\n## OUTRO\ntschüss"
        sec = split_sections(text)
        self.assertIn("INTRO", sec)
        self.assertIn("OUTRO", sec)
        self.assertEqual(sec["INTRO"], "hallo")


if __name__ == "__main__":
    unittest.main()

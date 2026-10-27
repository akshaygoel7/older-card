import json
import unittest
from pathlib import Path

import older_card


ROOT = Path(__file__).resolve().parents[1]
CARD = "Amma's Monday dal. Toor, haldi, one dried chilli, eaten with rice."
LATER = "Grandmother's famous butter chicken, her favorite, from 1972 in Delhi."


class AcceptTests(unittest.TestCase):
    def test_keeps_a_line_made_of_card_words(self):
        self.assertTrue(older_card.accept(CARD, LATER, "Toor, haldi, one dried chilli, eaten with rice."))

    def test_throws_away_a_borrowed_dish(self):
        self.assertFalse(older_card.accept(CARD, LATER, "Famous butter chicken from Delhi."))

    def test_throws_away_a_feeling_the_card_never_wrote(self):
        self.assertFalse(older_card.accept(CARD, LATER, "Toor dal, her favorite."))

    def test_throws_away_a_year(self):
        self.assertFalse(older_card.accept(CARD, LATER, "Monday dal from 1972."))

    def test_throws_away_a_moved_number(self):
        self.assertFalse(older_card.accept(CARD, LATER, "One rice."))

    def test_throws_away_a_blank_line(self):
        self.assertFalse(older_card.accept(CARD, LATER, "   "))


class ParseTests(unittest.TestCase):
    def test_json_line(self):
        self.assertEqual(older_card.parse_model_line('{"line":"Toor and haldi."}'), "Toor and haldi.")

    def test_json_with_chatter(self):
        self.assertEqual(
            older_card.parse_model_line('note {"line":"eaten with rice."} thanks'),
            "eaten with rice.",
        )

    def test_pile_splits_on_the_rule(self):
        records = older_card.parse_pile((ROOT / "samples" / "pile.txt").read_text())
        self.assertEqual(len(records), 4)
        self.assertIn("Toor", records[0]["card"])
        self.assertIn("butter chicken", records[0]["later"])

    def test_first_sentence_stops_at_the_period(self):
        self.assertEqual(older_card.first_sentence(CARD), "Amma's Monday dal.")


class RememberTests(unittest.TestCase):
    def test_unreachable_model_keeps_the_card(self):
        def ask(card, later):
            raise TimeoutError("down")

        row = older_card.remember_one({"card": CARD, "later": LATER}, ask)
        self.assertEqual(row["path"], "fallback")
        self.assertEqual(row["line"], "Amma's Monday dal.")
        self.assertIn("unreachable", row["reason"])

    def test_borrowed_line_is_thrown_away(self):
        def ask(card, later):
            return "Grandmother's famous butter chicken."

        row = older_card.remember_one({"card": CARD, "later": LATER}, ask)
        self.assertEqual(row["path"], "fallback")
        self.assertEqual(row["line"], "Amma's Monday dal.")
        self.assertIn("borrowed", row["reason"])

    def test_faithful_line_is_kept(self):
        def ask(card, later):
            return "Toor, haldi, and one dried chilli."

        row = older_card.remember_one({"card": CARD, "later": LATER}, ask)
        self.assertEqual(row["path"], "model")
        self.assertIn("chilli", row["line"])

    def test_rules_only_does_not_invent_a_line(self):
        report = older_card.remember_pile(
            [{"card": CARD, "later": LATER}],
            lambda card, later: "",
        )
        self.assertEqual(report["thrown_away"], 1)
        self.assertEqual(report["model_kept"], 0)
        self.assertEqual(report["items"][0]["line"], "Amma's Monday dal.")


class ReasonTests(unittest.TestCase):
    def test_reason_names_the_borrow(self):
        reason = older_card.rejection_reason(CARD, LATER, "butter chicken in Delhi")
        self.assertIn("later retelling", reason)

    def test_reason_names_a_moved_number(self):
        reason = older_card.rejection_reason(CARD, LATER, "one rice")
        self.assertIn("number", reason)


if __name__ == "__main__":
    unittest.main()

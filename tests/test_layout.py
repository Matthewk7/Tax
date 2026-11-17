import unittest

from tax_inventory.layout import extract_issuer_from_layout, words_to_segments


def words(*items):
    """(x, y, text) -> word boxes with a 10-unit line height and 6 units per character."""
    return [(x, y, x + 6 * len(text), y + 10, text) for x, y, text in items]


class LayoutTests(unittest.TestCase):
    def test_columns_on_one_row_are_separate_segments(self):
        rows = words_to_segments(words((10, 0, "PAYER'S"), (60, 0, "name"), (400, 0, "1a"), (420, 0, "Total")))
        self.assertEqual([s.text for s in rows[0]], ["PAYER'S name", "1a Total"])

    def test_issuer_read_from_box_below_label(self):
        rows = words_to_segments(words(
            (10, 0, "c"), (20, 0, "Employer’s"), (90, 0, "name,"), (125, 0, "address,"), (180, 0, "and"), (205, 0, "ZIP"),
            (400, 0, "Wages"),
            (10, 14, "UNIVERSITY"), (80, 14, "OF"), (98, 14, "PITTSBURGH"),
            (400, 14, "44629.35"),
            (10, 28, "200"), (35, 28, "SOUTH"), (75, 28, "CRAIG"),
        ))
        self.assertEqual(extract_issuer_from_layout(rows), "UNIVERSITY OF PITTSBURGH")

    def test_label_continuation_lines_are_skipped(self):
        rows = words_to_segments(words(
            (10, 0, "PAYER'S"), (60, 0, "name,"), (95, 0, "street"), (135, 0, "address"),
            (10, 14, "or"), (25, 14, "foreign"), (75, 14, "postal"), (115, 14, "code"),
            (10, 28, "MICHAEL"), (60, 28, "M"), (72, 28, "JORDAN"),
        ))
        self.assertEqual(extract_issuer_from_layout(rows), "MICHAEL M JORDAN")

    def test_blank_form_has_no_issuer(self):
        rows = words_to_segments(words(
            (10, 0, "PAYER'S"), (60, 0, "name,"), (95, 0, "street"), (135, 0, "address"),
            (10, 40, "PAYER'S"), (60, 40, "federal"), (110, 40, "identification"),
            (10, 54, "RECIPIENT'S"), (85, 54, "name"),
        ))
        self.assertIsNone(extract_issuer_from_layout(rows))


if __name__ == "__main__":
    unittest.main()

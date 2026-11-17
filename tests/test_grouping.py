import unittest

from tax_inventory.grouping import group_pages


def page(number, kind, confidence=0.97, text="Form 1099-B", printed=None, total=None, year=2025,
         issuer="Acme Brokerage", instructions=False, continuation_text=None):
    record = {
        "page_number": number,
        "classification": {"type": kind, "label": kind, "confidence": confidence, "reason": "test",
                           "is_instructions": instructions},
        "tax_year": year,
        "issuer": issuer,
        "printed_page_number": printed,
        "printed_page_total": total,
        "text_excerpt": text,
        "is_blank": False,
    }
    if continuation_text is not None:
        record["has_continuation_text"] = continuation_text
    return record


class GroupingTests(unittest.TestCase):
    def test_continued_1099b_pages_group(self):
        groups = group_pages([
            page(1, "1099_B", text="Form 1099-B Page 1 of 2", printed=1, total=2),
            page(2, "1099_B", text="Continued Page 2 of 2", printed=2, total=2),
        ])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["pages"], [1, 2])

    def test_two_w2s_stay_separate(self):
        groups = group_pages([
            page(1, "W2", text="Form W-2 Wage and Tax Statement", issuer="Employer A"),
            page(2, "W2", text="Form W-2 Wage and Tax Statement", issuer="Employer B"),
        ])
        self.assertEqual(len(groups), 2)

    def test_continued_text_without_page_number_does_not_crash(self):
        # Regression: printed_page_number=None used to raise TypeError.
        groups = group_pages([
            page(1, "W2", text="Form W-2", issuer="A"),
            page(2, "W2", text="Form W-2 continued", issuer="A"),
        ])
        self.assertEqual(len(groups), 2)

    def test_consolidated_statement_sections_group_together(self):
        groups = group_pages([
            page(1, "CONSOLIDATED_1099", printed=1, total=4),
            page(2, "1099_DIV", printed=2, total=4),
            page(3, "1099_INT", printed=3, total=4),
            page(4, "1099_B", printed=4, total=4),
        ])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["type"], "CONSOLIDATED_1099")
        self.assertEqual(groups[0]["pages"], [1, 2, 3, 4])

    def test_adjacent_1099s_from_different_issuers_stay_separate(self):
        groups = group_pages([
            page(1, "1099_INT", issuer="Bank A", printed=2, total=2),
            page(2, "1099_DIV", issuer="Broker B", printed=2, total=2),
        ])
        self.assertEqual(len(groups), 2)

    def test_page_one_starts_new_document_even_if_text_says_continued(self):
        groups = group_pages([
            page(1, "1099_B", printed=1, total=1),
            page(2, "1099_B", printed=1, total=3, continuation_text=True),
        ])
        self.assertEqual(len(groups), 2)

    def test_continuation_text_from_full_page_is_used(self):
        groups = group_pages([
            page(1, "1099_B", text="Form 1099-B"),
            page(2, "1099_B", text="Form 1099-B", continuation_text=True),
        ])
        self.assertEqual(len(groups), 1)

    def test_instructions_page_attaches_to_preceding_form(self):
        groups = group_pages([
            page(1, "W2", issuer="A"),
            page(2, "W2", issuer=None, instructions=True),
            page(3, "W2", issuer="B"),
        ])
        self.assertEqual([g["pages"] for g in groups], [[1, 2], [3]])
        self.assertEqual(groups[0]["page_classifications"], ["W2", "INSTRUCTIONS"])

    def test_copies_of_same_form_are_one_document(self):
        groups = group_pages([
            dict(page(1, "W2", issuer="A"), copy_label="B", amounts_key="abc"),
            dict(page(2, "W2", issuer="A"), copy_label="C", amounts_key="abc"),
            dict(page(3, "W2", issuer="A"), copy_label="2", amounts_key="abc"),
        ])
        self.assertEqual([g["pages"] for g in groups], [[1, 2, 3]])
        self.assertFalse(groups[0]["needs_review"])

    def test_same_payer_forms_with_different_amounts_stay_separate(self):
        groups = group_pages([
            dict(page(1, "W2", issuer="A"), copy_label="B", amounts_key="abc"),
            dict(page(2, "W2", issuer="A"), copy_label="B", amounts_key="xyz"),
        ])
        self.assertEqual(len(groups), 2)

    def test_repeated_copy_is_flagged_as_possible_duplicate(self):
        groups = group_pages([
            dict(page(1, "W2", issuer="A"), copy_label="B", amounts_key="abc"),
            dict(page(2, "W2", issuer="A"), copy_label="B", amounts_key="abc"),
        ])
        self.assertEqual(len(groups), 1)
        self.assertTrue(groups[0]["needs_review"])

    def test_standalone_instructions_page_is_flagged(self):
        groups = group_pages([page(1, "W2", instructions=True)])
        self.assertTrue(groups[0]["needs_review"])


if __name__ == "__main__":
    unittest.main()

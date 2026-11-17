import unittest

from tax_inventory.classifier import classify_page, extract_issuer, extract_tax_year


class ClassifierTests(unittest.TestCase):
    def test_w2(self):
        result = classify_page("Form W-2 Wage and Tax Statement 2025 Employer's name")
        self.assertEqual(result["type"], "W2")

    def test_1098_t_precedes_1098(self):
        result = classify_page("Form 1098-T Tuition Statement")
        self.assertEqual(result["type"], "1098_T")

    def test_1098_e_is_not_mortgage_1098(self):
        self.assertEqual(classify_page("Form 1098-E Student Loan Interest Statement")["type"], "1098_E")

    def test_other_1098_variants_are_not_mortgage_1098(self):
        self.assertNotEqual(classify_page("Form 1098-C Contributions of Motor Vehicles")["type"], "1098")
        self.assertNotEqual(classify_page("Form 1098-Q Qualifying Longevity Annuity")["type"], "1098")

    def test_mortgage_1098_still_matches(self):
        self.assertEqual(classify_page("Form 1098 Mortgage Interest Statement")["type"], "1098")
        self.assertEqual(classify_page("2025 Form 1098\nRecipient/lender")["type"], "1098")

    def test_unknown_is_explicit(self):
        result = classify_page("A random letter with no standard tax form label")
        self.assertEqual(result["type"], "UNKNOWN")

    def test_generic_phrase_alone_scores_low(self):
        result = classify_page("Dear customer, your savings account earned interest income this year.")
        self.assertEqual(result["type"], "1099_INT")
        self.assertLess(result["confidence"], 0.85)

    def test_form_number_scores_high(self):
        self.assertGreaterEqual(classify_page("Form 1099-INT Interest Income")["confidence"], 0.95)

    def test_page_listing_several_1099_sections_is_consolidated(self):
        result = classify_page("2025 Form 1099-DIV, Form 1099-INT and Form 1099-B summary")
        self.assertEqual(result["type"], "CONSOLIDATED_1099")

    def test_consolidated_label_wins(self):
        result = classify_page("2025 Consolidated Form 1099\nForm 1099-B Proceeds From Broker and Barter Exchange Transactions")
        self.assertEqual(result["type"], "CONSOLIDATED_1099")

    def test_instructions_page_flagged(self):
        result = classify_page("Instructions for Employee\nBox 1. Enter this amount on Form W-2 wages line of Form 1040.")
        self.assertEqual(result["type"], "W2")
        self.assertTrue(result["is_instructions"])

    def test_form_with_amounts_is_not_instructions(self):
        text = "Form W-2 Wage and Tax Statement\n1 Wages 52,000.00\n2 Federal 6,100.00\n3 SS wages 52,000.00\nNotice to Employee"
        self.assertFalse(classify_page(text)["is_instructions"])

    def test_w2_identified_by_box_labels_without_title(self):
        # Payroll-provider W-2s often extract with the title split apart and no "Form W-2".
        text = ("Wage\nControl number\nWages, tips, other comp.\nSocial security wages\nand\nMedicare wages and tips\n"
                "Tax\nSocial security tax withheld\nMedicare tax withheld\nEmployer’s FED ID number\nStatement")
        result = classify_page(text)
        self.assertEqual(result["type"], "W2")
        self.assertGreaterEqual(result["confidence"], 0.95)

    def test_passing_mention_of_another_form_does_not_win(self):
        text = ("Instructions for Recipient\nForm 1099-MISC incorrect? Contact the payer.\n"
                "You received this form instead of Form W-2 because the payer did not consider you an employee.\n"
                "Box 1. Report rents on Schedule E. Box 2. Report royalties. Form 1099-MISC")
        result = classify_page(text)
        self.assertEqual(result["type"], "1099_MISC")
        self.assertIn("W-2", result["reason"])

    def test_older_form_year_is_extracted(self):
        self.assertEqual(extract_tax_year("Form 1099-MISC\n2012\nMiscellaneous Income"), 2012)

    def test_issuer_skips_neighboring_box_labels(self):
        self.assertIsNone(extract_issuer("Employer’s name, address, and ZIP code\nc\nEmployee’s SSA number"))

    def test_contextual_tax_year(self):
        self.assertEqual(extract_tax_year("Tax year 2025 issued in 2026"), 2025)

    def test_issuer_with_curly_apostrophe(self):
        self.assertEqual(extract_issuer("Employer’s name\nAcme Corp"), "Acme Corp")
        self.assertEqual(extract_issuer("PAYER’S name, street address\nFirst Bank"), "First Bank")


if __name__ == "__main__":
    unittest.main()

import unittest

import pymupdf

from tax_inventory.grouping import group_pages
from tax_inventory.processor import process_pdf


def synthetic_pdf(page_texts):
    document = pymupdf.open()
    for text in page_texts:
        document.new_page().insert_text((72, 72), text, fontsize=9)
    data = document.tobytes()
    document.close()
    return data


class ProcessorTests(unittest.TestCase):
    """End-to-end on native-text PDFs (no OCR, so Tesseract is not required)."""

    def test_consolidated_brokerage_pdf_is_one_document(self):
        data = synthetic_pdf([
            "Acme Brokerage 2025 Consolidated Form 1099\nTax year 2025\nPage 1 of 4\nSummary of Form 1099-DIV and Form 1099-INT",
            "Form 1099-DIV Dividends and Distributions\nTax year 2025\nPage 2 of 4",
            "Form 1099-INT Interest Income\nTax year 2025\nPage 3 of 4",
            "Form 1099-B Proceeds From Broker and Barter Exchange Transactions\nTax year 2025\nPage 4 of 4",
        ])
        groups = group_pages(process_pdf(data))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["type"], "CONSOLIDATED_1099")
        self.assertEqual(groups[0]["pages"], [1, 2, 3, 4])

    def test_w2_followed_by_1099_int_are_separate(self):
        data = synthetic_pdf([
            "Form W-2 Wage and Tax Statement 2025\nEmployer's name\nAcme Corp\n1 Wages 52,000.00",
            "Form 1099-INT Interest Income 2025\nPAYER'S name\nFirst Bank\n1 Interest 120.00",
        ])
        groups = group_pages(process_pdf(data))
        self.assertEqual([g["type"] for g in groups], ["W2", "1099_INT"])
        self.assertEqual(groups[0]["issuer"], "Acme Corp")


if __name__ == "__main__":
    unittest.main()

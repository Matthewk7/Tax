# Tax Document Inventory — Local Proof of Concept

A small local app that accepts **one PDF or one image per run**, extracts page text, applies transparent document-identification rules, conservatively groups adjacent pages, and exports an inventory as JSON.

**No LLM. No cloud API. No external upload.** OCR is performed locally using Tesseract. This is an engineering prototype, not a validated tax-preparation product.

## What it does

- Accepts one multipage PDF or one image (`.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`, `.webp`, `.heic`, `.heif`).
- Extracts embedded PDF text with PyMuPDF.
- Uses local Tesseract OCR only when a PDF page has little/no extractable text, and for images.
- Applies rules for W-2, common 1099 forms, 1098 / 1098-T, 1099-R, Schedule K-1, 1095-A, property-tax statements, charitable-contribution summaries, and brokerage statements.
- Captures page number, likely tax year, best-effort issuer, heuristic match score, and review warnings.
- Groups only adjacent pages when continuation evidence is present. It intentionally errs on the side of separate documents / human review.
- Lets a user correct a document type in the UI and download JSON.

## What it does not do

- It does not determine whether a client's tax package is complete or whether a document is required for a return.
- It does not reliably identify every possible tax/supporting document.
- It does not reliably infer document boundaries when the PDF has no page numbers or continuation cues.
- It does not support multiple image files in one upload or batch/folder processing.
- It does not save uploads or results to a database. Streamlit holds the upload and analysis in the local app session; the JSON download is user-initiated.
- It is not production-secure or approved for real taxpayer information merely because it runs locally.

## Requirements

- Python 3.11–3.15 (the Windows build works with 3.15 via `py -3.15`).
- Tesseract OCR installed as a separate system application.
- macOS, Windows, or Linux.

### Windows setup (Python, for development)

1. Install Python 3.10+ from python.org and Tesseract OCR (the Tesseract project lists Windows installation options in its installation guide).
2. Open PowerShell in the unzipped project directory.
3. Create/activate a virtual environment:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

5. Run:

   ```powershell
   python -m streamlit run app.py --server.address 127.0.0.1
   ```

If Python cannot find Tesseract, add the Tesseract installation directory to PATH, restart PowerShell, and verify with `tesseract --version`.

## How to use it

1. Start the app using the command above.
2. In the browser, upload one PDF or one image.
3. Click **Analyze file**.
4. Review the detected document types, page ranges, tax years, issuers, rule-match scores, and warnings.
5. Correct any document type that is wrong. Note that the correction does not recalculate page grouping.
6. Download the JSON inventory.
7. Manually compare results with the source document. Do not treat the result as tax intake approval.

## Troubleshooting

- **`Tesseract was not found`:** install Tesseract as a system application and confirm `tesseract --version` works in the same Terminal/PowerShell session used to start Streamlit.
- **HEIC cannot open:** confirm `pillow-heif` installed successfully (`python -m pip show pillow-heif`). Convert a test photo to JPEG if needed.
- **Scanned PDF seems blank:** confirm Tesseract is installed and inspect the source scan. Very faint, blurry, rotated, or cropped images may not OCR reliably.
- **A PDF is password-protected:** remove the password using an authorized local workflow before upload.
- **Wrong classification:** inspect extracted page text. Add or refine a rule, and create a regression test with a synthetic or redacted sample.

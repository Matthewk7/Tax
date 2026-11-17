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

### macOS setup (recommended path)

1. Install Python if needed. Verify:

   ```bash
   python3 --version
   ```

2. Install Tesseract using Homebrew:

   ```bash
   brew install tesseract
   ```

3. Verify Tesseract:

   ```bash
   tesseract --version
   ```

4. Unzip this project, open Terminal, and change into its directory:

   ```bash
   cd tax-doc-inventory-poc
   ```

5. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

6. Install Python dependencies:

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

7. Run the local app, bound to loopback only:

   ```bash
   python -m streamlit run app.py --server.address 127.0.0.1
   ```

8. Open the local address printed in Terminal (normally `http://127.0.0.1:8501`). Keep the Terminal window running while using the app.

### Windows one-click app (no Python for recipients)

The UI is still Streamlit, so **yes, it runs in a browser** — but only on the same PC, at `http://127.0.0.1:8501`. Nothing is uploaded to the internet. Double-clicking the app starts a small local server, opens that page, and closing the black console window stops it.

You cannot produce a Windows `.exe` from macOS. Build on a Windows PC, or use the GitHub Action in this repo.

**On a Windows PC that already has Python and Tesseract:**

1. Install [Tesseract OCR for Windows](https://github.com/UB-Mannheim/tesseract/wiki) if needed (default folder `C:\Program Files\Tesseract-OCR`).
2. In PowerShell, from this project folder:

   ```powershell
   .\build-windows.ps1
   ```

3. Zip `dist\TaxDocInventory` and send the zip.

**For the person running it:** unzip, double-click `TaxDocInventory.exe`. Windows SmartScreen may say the app is unrecognized (it is unsigned). Choose **More info** → **Run anyway**. Keep the console window open while using the app.

The zip is a folder, not a single `.exe`, because Streamlit plus Tesseract is more reliable that way. After unzip, launching is still one double-click.

**GitHub Actions:** if this project is on GitHub, run the **Build Windows app** workflow, then download the `TaxDocInventory-windows` artifact.

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

## Run the unit tests

From the project directory with the virtual environment active:

```bash
python -m unittest discover -s tests -v
```

These tests validate a few rules and grouping examples; they are not a representative accuracy benchmark.

## How classification works

The classifier uses regular expressions and phrases in the extracted page text. A match score is a **heuristic rule score**, not a statistically calibrated probability. For example, it is not valid to interpret a 98% score as a measured 98% chance that the type is correct.

The configured patterns live in `tax_inventory/classifier.py`. Add new form rules there and add unit tests for both positive and negative examples. Be careful with overlapping form numbers (for example, 1098-T must be tested before a generic 1098 rule).

## How page grouping works

The grouping code is in `tax_inventory/grouping.py`. It starts a new document unless adjacent pages have the same type/year/issuer and there is continuation evidence such as `Page 2 of 4` or `continued`. Unknown pages with continuation signals may be attached to the preceding item but are explicitly flagged for review.

This is deliberately conservative. Two W-2s from the same employer may still be two distinct copies; two unrelated same-type forms may appear next to one another; statement pages may omit continuation labels. The prototype cannot resolve all these cases. The reviewer must verify page ranges.

## Troubleshooting

- **`Tesseract was not found`:** install Tesseract as a system application and confirm `tesseract --version` works in the same Terminal/PowerShell session used to start Streamlit.
- **HEIC cannot open:** confirm `pillow-heif` installed successfully (`python -m pip show pillow-heif`). Convert a test photo to JPEG if needed.
- **Scanned PDF seems blank:** confirm Tesseract is installed and inspect the source scan. Very faint, blurry, rotated, or cropped images may not OCR reliably.
- **A PDF is password-protected:** remove the password using an authorized local workflow before upload.
- **Wrong classification:** inspect extracted page text. Add or refine a rule, and create a regression test with a synthetic or redacted sample.

## Suggested POC evaluation

Use only synthetic, redacted, or explicitly approved/de-identified files. For each sample, manually label every document's type, page range, issuer (if available), and tax year (if available). Keep a holdout set that is not used while tuning rules. Include digitally generated PDFs, scanned PDFs, smartphone photos, multipage brokerage statements, duplicate forms, mixed years, blank pages, and unknown supporting records.

Measure at minimum:

- **Document recall:** correctly detected ground-truth documents / all ground-truth documents.
- **Classification accuracy:** correctly typed detected documents / all detected documents with known labels.
- **Exact page-grouping accuracy:** groups whose complete page range matches ground truth / all ground-truth groups.
- **Unknown/review rate:** documents flagged for review / all detected document groups.
- **False-merge rate:** two real documents incorrectly combined into one group.
- **False-split rate:** one real multi-page document incorrectly split into multiple groups.
- **Processing time and cost:** local runtime and machine specs; for this no-cloud POC, there is no per-page OCR API charge, but there is local compute/time cost.

Do not claim a target accuracy based on the small unit-test suite. Measure on unseen files and report results by input type (native PDF, scanned PDF, photo).

## Before using real client documents

Local execution reduces third-party disclosure, but it is not a complete security program. Confirm the firm's WISP, access controls, workstation encryption, endpoint protection, backup/retention policies, incident response, and legal review. Do not enable remote access or expose Streamlit to the LAN. Avoid sharing logs, screenshots, or exported JSON containing taxpayer information. Use synthetic or properly approved data until the firm authorizes the workflow.

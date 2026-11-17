from __future__ import annotations

import json
from datetime import datetime, timezone

import streamlit as st

from tax_inventory.processor import process_upload
from tax_inventory.grouping import group_pages
from tax_inventory.classifier import RULES

st.set_page_config(page_title="Tax Document Inventory", page_icon="📄", layout="wide")
st.title("Tax Document Inventory")
st.caption("One PDF or one image per run · rule-based classification · local OCR · no LLM · no cloud processing")

# with st.expander("Important: POC and privacy limitations", expanded=True):
#     st.warning(
#         "Use synthetic, redacted, or specifically authorized test files only. This prototype is not production-ready, "
#         "does not establish tax-return completeness, and does not guarantee correct document classification or grouping. "
#         "It runs on your computer when started with the provided local-only command. Do not expose it to your network or the internet."
#     )

uploaded = st.file_uploader(
    "Choose one PDF or one image",
    type=["pdf", "jpg", "jpeg", "png", "tif", "tiff", "heic", "heif", "webp"],
    accept_multiple_files=False,
    help="One multipage PDF or one individual image per analysis. Multi-image batches are intentionally out of scope.",
)

if uploaded:
    st.write(f"**File:** {uploaded.name} · **Size:** {uploaded.size / 1024:,.1f} KB")
    if st.button("Analyze file", type="primary"):
        with st.spinner("Extracting text and identifying documents locally..."):
            try:
                file_bytes = uploaded.getvalue()
                page_records = process_upload(uploaded.name, file_bytes)
                document_groups = group_pages(page_records)
                st.session_state["analysis"] = {
                    "filename": uploaded.name,
                    "file_size_bytes": uploaded.size,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "pages": page_records,
                    "documents": document_groups,
                }
            except Exception as exc:
                st.error(str(exc))
                st.stop()

analysis = st.session_state.get("analysis")
if analysis:
    st.divider()
    pages = analysis["pages"]
    docs = analysis["documents"]
    unknown_pages = sum(1 for p in pages if p["classification"]["type"] == "UNKNOWN" and not p["is_blank"])
    reviews = sum(1 for d in docs if d["needs_review"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pages", len(pages))
    c2.metric("Documents detected", len(docs))
    c3.metric("Pages unidentified", unknown_pages)
    c4.metric("Documents needing review", reviews)

    st.subheader("Document inventory")
    st.caption("The score is a heuristic rule-match score, not a calibrated probability of correctness.")
    type_options = {rule.code: rule.label for rule in RULES}
    type_options["UNKNOWN"] = "Unidentified / other"
    type_codes = list(type_options.keys())

    exported_docs = []
    for index, doc in enumerate(docs):
        title = f"{doc['label']} · page(s) {', '.join(map(str, doc['pages']))}"
        with st.expander(title, expanded=doc["needs_review"]):
            current_type = doc["type"] if doc["type"] in type_codes else "UNKNOWN"
            selected_type = st.selectbox(
                "Document type (you can correct the POC result)",
                options=type_codes,
                index=type_codes.index(current_type),
                format_func=lambda code: f"{code} — {type_options[code]}",
                key=f"type_{analysis['filename']}_{index}",
            )
            col1, col2, col3 = st.columns(3)
            col1.write(f"**Pages:** {', '.join(map(str, doc['pages']))}")
            col2.write(f"**Tax year:** {doc['tax_year'] or 'Not identified'}")
            col3.write(f"**Issuer:** {doc['issuer'] or 'Not identified'}")
            st.write(f"**Rule-match score:** {doc['confidence']:.0%}")
            if doc["review_reasons"]:
                for reason in doc["review_reasons"]:
                    st.warning(reason)
            if selected_type != doc["type"]:
                st.info("Classification manually changed in this session. Grouping/page boundaries have not been recalculated.")
            exported = dict(doc)
            exported["type"] = selected_type
            exported["label"] = type_options[selected_type]
            exported["manually_corrected"] = selected_type != doc["type"]
            exported_docs.append(exported)

    st.subheader("Page-by-page extraction details")
    for page in pages:
        classification = page["classification"]
        status = "Blank / unreadable" if page["is_blank"] else f"{classification['type']} ({classification['confidence']:.0%})"
        with st.expander(f"Page {page['page_number']} — {status}"):
            st.write(
                f"OCR used: **{page['ocr_used']}** · Extracted characters: **{page['text_chars']}** · "
                f"Tax year: **{page['tax_year'] or 'Unknown'}** · Issuer: **{page['issuer'] or 'Unknown'}**"
            )
            if page["warnings"]:
                for warning in page["warnings"]:
                    st.warning(warning)
            st.code(page["text_excerpt"] or "[No readable text extracted]", language="text")

    payload = {
        "schema_version": "0.1.0",
        "source_file": {
            "filename": analysis["filename"],
            "size_bytes": analysis["file_size_bytes"],
            "processed_at": analysis["processed_at"],
        },
        "documents": exported_docs,
        "pages": pages,
        "limitations": [
            "Local POC; not production-ready.",
            "Classification scores are heuristic, not calibrated probabilities.",
            "Grouping is conservative and rule-based; verify page boundaries manually.",
            "This inventory does not determine whether a tax return is complete.",
        ],
    }
    st.download_button(
        "Download inventory JSON",
        data=json.dumps(payload, indent=2, ensure_ascii=False),
        file_name="tax_document_inventory.json",
        mime="application/json",
    )

st.divider()
with st.expander("Document types covered by the initial rules"):
    st.write(", ".join(f"**{r.code}** ({r.label})" for r in RULES))
    st.caption("This is an editable starting taxonomy, not an exhaustive list of tax or supporting documents.")

from __future__ import annotations

import uuid
from typing import Any

from .classifier import CONSOLIDATED_FAMILY, RULES_BY_CODE, amounts_key, has_continuation_text

MULTI_PAGE_TYPES = {"1099_B", "BROKERAGE_STATEMENT", "SCHEDULE_K1", "CONSOLIDATED_1099"}
NO_AMOUNTS_KEY = amounts_key("")


def _has_continuation_evidence(page: dict[str, Any], current: dict[str, Any]) -> bool:
    printed = page.get("printed_page_number")
    if printed == 1:
        # "Page 1 of N" starts a document, whatever else the page says.
        return False
    if printed and printed > 1:
        return True
    if "has_continuation_text" in page:
        return bool(page["has_continuation_text"])
    return has_continuation_text(page.get("text_excerpt") or "")


def _numbering_continues(page: dict[str, Any], current: dict[str, Any]) -> bool:
    printed = page.get("printed_page_number")
    last = current.get("_last_printed")
    if not printed or not last or printed != last + 1:
        return False
    total, last_total = page.get("printed_page_total"), current.get("_last_total")
    return not total or not last_total or total == last_total


def _same_issuer(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return True
    return " ".join(a.lower().split()) == " ".join(b.lower().split())


def group_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Conservative adjacent-page grouping; uncertain pages remain reviewable.

    This POC does not perform visual layout matching or semantic statement
    reconciliation. It only joins adjacent pages when continuation evidence
    supports the decision.
    """
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def new_group(page: dict[str, Any]) -> dict[str, Any]:
        classification = page["classification"]
        instructions_only = bool(classification.get("is_instructions"))
        reasons = []
        if instructions_only:
            reasons.append(
                f"Page {page['page_number']} looks like form instructions with no preceding form of the same type; "
                "confirm it is not a separate document."
            )
        return {
            "document_id": str(uuid.uuid4()),
            "type": classification["type"],
            "label": classification["label"],
            "pages": [page["page_number"]],
            "tax_year": page.get("tax_year"),
            "issuer": page.get("issuer"),
            "confidence": classification["confidence"],
            "needs_review": instructions_only or classification["type"] == "UNKNOWN" or classification["confidence"] < 0.85,
            "review_reasons": reasons,
            "page_classifications": ["INSTRUCTIONS" if instructions_only else classification["type"]],
            "_last_printed": page.get("printed_page_number"),
            "_last_total": page.get("printed_page_total"),
            "_amounts_key": page.get("amounts_key"),
            "_copy_labels": {page["copy_label"]} if page.get("copy_label") else set(),
        }

    def attach(page: dict[str, Any], page_type: str) -> None:
        current["pages"].append(page["page_number"])
        current["page_classifications"].append(page_type)
        current["_last_printed"] = page.get("printed_page_number")
        current["_last_total"] = page.get("printed_page_total")
        if page.get("tax_year") and not current.get("tax_year"):
            current["tax_year"] = page["tax_year"]
        if page.get("issuer") and not current.get("issuer"):
            current["issuer"] = page["issuer"]

    for page in pages:
        classification = page["classification"]
        ctype = classification["type"]
        if page.get("is_blank"):
            # Blank pages are retained in page-level results, but aren't counted
            # as tax documents. They are not silently attached to either side.
            current = None
            continue

        if current is None:
            current = new_group(page)
            groups.append(current)
            continue

        same_tax_year = not page.get("tax_year") or not current.get("tax_year") or page.get("tax_year") == current.get("tax_year")
        same_issuer = _same_issuer(page.get("issuer"), current.get("issuer"))
        starts_new = page.get("printed_page_number") == 1
        continuation = _has_continuation_evidence(page, current) or _numbering_continues(page, current)

        # Instruction pages (e.g., the back of a W-2 or 1099) belong to the
        # preceding form rather than counting as another document.
        if classification.get("is_instructions") and not starts_new and ctype in {current["type"], "UNKNOWN"} | (
            CONSOLIDATED_FAMILY if current["type"] in CONSOLIDATED_FAMILY else set()
        ):
            attach(page, "INSTRUCTIONS")
            continue

        # Separate copies of one form (Copy B, Copy C, Copy 2...) carry the same
        # amounts; they are one document, not several.
        if (
            ctype != "UNKNOWN" and ctype == current["type"] and same_tax_year and same_issuer
            and page.get("copy_label") and page.get("amounts_key")
            and page["amounts_key"] == current.get("_amounts_key")
        ):
            attach(page, "COPY")
            if page["copy_label"] in current["_copy_labels"]:
                current["needs_review"] = True
                current["review_reasons"].append(
                    f"Page {page['page_number']} repeats Copy {page['copy_label']} of the same form; it may be a duplicate."
                )
            if page["amounts_key"] == NO_AMOUNTS_KEY:
                current["needs_review"] = True
                current["review_reasons"].append(
                    f"Page {page['page_number']} was treated as another copy of the same form, but no amounts were "
                    "found to confirm it; verify it is not a separate form."
                )
            current["_copy_labels"].add(page["copy_label"])
            continue

        if ctype == "UNKNOWN" and continuation:
            attach(page, "UNKNOWN_CONTINUATION")
            current["needs_review"] = True
            current["review_reasons"].append(
                f"Page {page['page_number']} was attached based on continuation evidence but its document type was not identified."
            )
            current["confidence"] = min(current["confidence"], 0.65)
            continue

        same_type = ctype != "UNKNOWN" and ctype == current["type"]
        if same_type and same_tax_year and same_issuer and continuation and (
            current["type"] in MULTI_PAGE_TYPES or (page.get("printed_page_number") or 1) > 1
        ):
            attach(page, ctype)
            current["confidence"] = min(current["confidence"], classification["confidence"])
            continue

        # Consolidated broker/bank statements mix 1099-INT/DIV/B/MISC sections
        # under one page sequence; keep them together as one document.
        same_family = ctype in CONSOLIDATED_FAMILY and current["type"] in CONSOLIDATED_FAMILY
        if same_family and same_tax_year and same_issuer and continuation:
            attach(page, ctype)
            if ctype != current["type"]:
                current["type"] = "CONSOLIDATED_1099"
                current["label"] = RULES_BY_CODE["CONSOLIDATED_1099"].label
            current["confidence"] = min(current["confidence"], classification["confidence"])
            continue

        current = new_group(page)
        groups.append(current)

    for group in groups:
        # Deduplicate review reasons while retaining order.
        group["review_reasons"] = list(dict.fromkeys(group["review_reasons"]))
        group.pop("_last_printed", None)
        group.pop("_last_total", None)
        group.pop("_amounts_key", None)
        group.pop("_copy_labels", None)
    return groups

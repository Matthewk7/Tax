"""Transparent, rule-based tax-document classifier.

Scores are heuristic rule-match scores, not statistically calibrated probabilities.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Rule:
    code: str
    label: str
    # Form numbers / official titles. A match is strong evidence of the type.
    patterns: tuple[str, ...]
    base_score: float = 0.88
    # Generic phrases that also appear on unrelated documents. A weak-only
    # match yields a low score so the result is always flagged for review.
    weak_patterns: tuple[str, ...] = ()
    # Box labels printed on the form itself. Matching at least
    # min_fingerprints of them identifies the form even when its title is
    # missing or the extracted text order is scrambled.
    fingerprints: tuple[str, ...] = ()
    min_fingerprints: int = 4


# "Form 1098" must not match 1098-E / 1098-C / 1098-Q / 1098-T etc.
_NO_FORM_SUFFIX = r"(?![\s-]?[a-z]\b|-[a-z])"

RULES: tuple[Rule, ...] = (
    Rule("W2", "W-2", (r"\bform\s+w[\s-]?2\b", r"\bwage[s]?\s+and\s+tax\s+statement\b"), 0.98,
         fingerprints=(
             r"wages,\s*tips,\s*other\s+comp", r"social\s+security\s+wages", r"medicare\s+wages\s+and\s+tips",
             r"social\s+security\s+tax\s+withheld", r"medicare\s+tax\s+withheld", r"allocated\s+tips",
             r"dependent\s+care\s+benefits", r"nonqualified\s+plans",
             r"employer's\s+(?:fed(?:eral)?\s+id|identification)\s+number",
             r"employee's\s+(?:ssa|social\s+security)\s+number",
         )),
    Rule("CONSOLIDATED_1099", "Consolidated / composite 1099 statement",
         (r"\b(?:consolidated|composite|combined)\s+(?:form\s+)?1099\b", r"\btax\s+information\s+statement\b",
          r"\btax\s+reporting\s+statement\b"), 0.95),
    Rule("1099_INT", "1099-INT", (r"\bform\s+1099[\s-]?int\b",), 0.97, (r"\binterest\s+income\b",),
         fingerprints=(
             r"early\s+withdrawal\s+penalty", r"interest\s+on\s+u\.?\s?s\.?\s+savings\s+bonds",
             r"tax.exempt\s+interest", r"bond\s+premium", r"market\s+discount",
         ), min_fingerprints=3),
    Rule("1099_DIV", "1099-DIV", (r"\bform\s+1099[\s-]?div\b",), 0.97, (r"\bdividends\s+and\s+distributions\b",),
         fingerprints=(
             r"total\s+ordinary\s+dividends", r"qualified\s+dividends", r"total\s+capital\s+gain\s+distr",
             r"nondividend\s+distributions", r"section\s+199a\s+dividends", r"unrecap\.?\s+sec\.?\s+1250\s+gain",
             r"collectibles\s+\(28%\)\s+gain", r"exempt.interest\s+dividends",
         )),
    Rule("1099_NEC", "1099-NEC", (r"\bform\s+1099[\s-]?nec\b",), 0.97, (r"\bnonemployee\s+compensation\b",)),
    Rule("1099_MISC", "1099-MISC", (r"\bform\s+1099[\s-]?misc\b",), 0.96, (r"\bmiscellaneous\s+information\b",),
         fingerprints=(
             r"\brents\b", r"\broyalties\b", r"fishing\s+boat\s+proceeds", r"medical\s+and\s+health\s+care\s+payments",
             r"crop\s+insurance\s+proceeds", r"gross\s+proceeds\s+paid\s+to\s+an\s+attorney",
             r"excess\s+golden\s+parachute",
         )),
    Rule("1099_K", "1099-K", (r"\bform\s+1099[\s-]?k\b", r"\bpayment\s+card\s+and\s+third.party\s+network\s+transactions\b"), 0.96),
    Rule("1099_B", "1099-B / Brokerage statement", (r"\bform\s+1099[\s-]?b\b", r"\bproceeds\s+from\s+broker\s+and\s+barter\s+exchange\s+transactions\b"), 0.97),
    Rule("1098_T", "1098-T", (r"\bform\s+1098[\s-]?t\b",), 0.96, (r"\btuition\s+statement\b",)),
    Rule("1098_E", "1098-E Student Loan Interest Statement", (r"\bform\s+1098[\s-]?e\b", r"\bstudent\s+loan\s+interest\s+statement\b"), 0.96),
    Rule("1098", "1098 Mortgage Interest Statement", (r"\bform\s+1098\b" + _NO_FORM_SUFFIX, r"\bmortgage\s+interest\s+statement\b"), 0.95),
    Rule("1099_R", "1099-R", (r"\bform\s+1099[\s-]?r\b", r"\bdistributions\s+from\s+pensions\b"), 0.96,
         fingerprints=(
             r"gross\s+distribution", r"taxable\s+amount\s+not\s+determined", r"distribution\s+code",
             r"ira/\s*sep/\s*simple", r"employee\s+contributions",
         ), min_fingerprints=3),
    Rule("SCHEDULE_K1", "Schedule K-1", (r"\bschedule\s+k[\s-]?1\b", r"\bpartner.s\s+share\s+of\s+income\b", r"\bshareholder.s\s+share\s+of\s+income\b"), 0.94),
    Rule("1095_A", "1095-A", (r"\bform\s+1095[\s-]?a\b", r"\bhealth\s+insurance\s+marketplace\s+statement\b"), 0.96),
    Rule("PROPERTY_TAX", "Property tax statement", (r"\bproperty\s+tax\s+statement\b", r"\breal\s+estate\s+tax\s+bill\b", r"\bcounty\s+tax\s+collector\b"), 0.83),
    Rule("CHARITABLE_CONTRIBUTIONS", "Charitable contributions / donation summary", (r"\bcharitable\s+contribution[s]?\b", r"\bdonation\s+(?:receipt|summary|statement)\b", r"\bnoncash\s+charitable\s+contributions\b"), 0.82),
    Rule("BROKERAGE_STATEMENT", "Brokerage statement (not specifically identified as 1099-B)", (r"\bbrokerage\s+account\s+statement\b", r"\binvestment\s+account\s+statement\b"), 0.82),
)

RULES_BY_CODE = {rule.code: rule for rule in RULES}

# Sections that commonly appear together in one broker/bank consolidated statement.
CONSOLIDATED_SECTION_TYPES = {"1099_INT", "1099_DIV", "1099_B", "1099_MISC"}
CONSOLIDATED_FAMILY = CONSOLIDATED_SECTION_TYPES | {"CONSOLIDATED_1099", "BROKERAGE_STATEMENT"}

WEAK_ONLY_SCORE = 0.6

INSTRUCTION_PATTERNS = (
    r"\binstructions\s+for\s+(?:recipient|employee|borrower|student|payer|partner|shareholder|beneficiary)\b",
    r"\bnotice\s+to\s+employee\b",
)
# Money amounts like 1,234.56 or 1234.56 — form data pages have several; instruction pages rarely do.
_AMOUNT = r"(?<![\d,.])\d{1,3}(?:,\d{3})+\.\d{2}\b|(?<![\d,.])\d+\.\d{2}\b"


def normalize_text(text: str) -> str:
    text = text.replace(" ", " ")
    text = text.replace("—", "-").replace("–", "-")
    text = re.sub(r"[‘’ʼ′`]", "'", text)
    return re.sub(r"[ \t]+", " ", text).lower()


def is_instructions_page(text: str) -> bool:
    """True when the page looks like form instructions rather than form data."""
    normalized = normalize_text(text)
    if not any(re.search(p, normalized) for p in INSTRUCTION_PATTERNS):
        return False
    return len(re.findall(_AMOUNT, normalized)) < 3


def classify_page(text: str) -> dict:
    """Return a conservative type classification based on visible text only."""
    normalized = normalize_text(text)
    # (score, rule, matched descriptions, evidence count)
    candidates: list[tuple[float, Rule, list[str], int]] = []
    for rule in RULES:
        strong = [p for p in rule.patterns if re.search(p, normalized)]
        weak = [p for p in rule.weak_patterns if re.search(p, normalized)]
        prints = [p for p in rule.fingerprints if re.search(p, normalized)]
        has_prints = len(prints) >= rule.min_fingerprints
        if not strong and not weak and not has_prints:
            continue
        # How much of the page supports this type. A form that is merely
        # mentioned in passing ("instead of Form W-2") scores low here.
        evidence = sum(len(re.findall(p, normalized)) for p in strong) + (len(prints) if has_prints else 0)
        matched = strong + weak + ([f"{len(prints)} {rule.label} box labels"] if has_prints else [])
        if strong or has_prints:
            score = rule.base_score
            if len(strong) + len(weak) + int(has_prints) > 1:
                score = min(0.995, score + 0.02)
        else:
            score = WEAK_ONLY_SCORE
        if rule.code in {"PROPERTY_TAX", "CHARITABLE_CONTRIBUTIONS", "BROKERAGE_STATEMENT"}:
            score = min(score, 0.90)
        candidates.append((score, rule, matched, evidence))

    instructions = is_instructions_page(text)

    if not candidates:
        return {
            "type": "UNKNOWN",
            "label": "Unidentified / other",
            "confidence": 0.0,
            "reason": "No configured document-identification rule matched the extracted text.",
            "is_instructions": instructions,
        }

    # A page labeled as a consolidated statement, or naming several 1099
    # sections by form number, is a consolidated statement rather than any
    # single one of those forms.
    strong_sections = sorted(
        c[1].code for c in candidates
        if c[1].code in CONSOLIDATED_SECTION_TYPES and c[0] > WEAK_ONLY_SCORE
    )
    consolidated = [c for c in candidates if c[1].code == "CONSOLIDATED_1099"]
    if consolidated:
        candidates = consolidated
    elif len(strong_sections) >= 2:
        candidates = [(0.9, RULES_BY_CODE["CONSOLIDATED_1099"], ["multiple 1099 sections: " + ", ".join(strong_sections)], 1)]

    # Strong matches beat weak ones; among strong matches the type with the
    # most supporting evidence wins; then score, then the most specific code
    # (e.g., 1098-T over 1098).
    candidates.sort(key=lambda c: (c[0] > WEAK_ONLY_SCORE, c[3], c[0], len(c[1].code)), reverse=True)
    score, rule, matched, _ = candidates[0]
    reason = "Matched text pattern(s): " + ", ".join(matched)
    if score == WEAK_ONLY_SCORE:
        reason = "Only generic phrase(s) matched, no form number or title: " + ", ".join(matched)
    others = [c[1].label for c in candidates[1:] if c[0] > WEAK_ONLY_SCORE]
    if score > WEAK_ONLY_SCORE and others:
        score = max(WEAK_ONLY_SCORE, score - 0.05)
        reason += ". Page also references: " + ", ".join(others)
    return {
        "type": rule.code,
        "label": rule.label,
        "confidence": round(score, 3),
        "reason": reason,
        "is_instructions": instructions,
    }


def extract_tax_year(text: str) -> Optional[int]:
    """Extract a likely tax year; intentionally returns None when ambiguous."""
    normalized = normalize_text(text)
    contextual = re.findall(
        r"(?:tax\s+year|for\s+the\s+year|calendar\s+year|year\s+ended|tax\s+period)\D{0,18}(20\d{2})",
        normalized,
        re.I,
    )
    if contextual:
        years = [int(y) for y in contextual]
        return max(set(years), key=years.count)

    # Form-year headings are commonly near the top. Avoid deriving a year from
    # arbitrary account numbers or dates; require a plausible four-digit year.
    years = [int(y) for y in re.findall(r"\b(20[1-3]\d)\b", normalized)]
    if not years:
        return None
    counts = {year: years.count(year) for year in set(years)}
    best = max(counts, key=counts.get)
    # If multiple years are equally frequent, leave it unknown rather than guess.
    if list(counts.values()).count(counts[best]) > 1:
        return None
    return best


def extract_issuer(text: str) -> Optional[str]:
    """Best-effort issuer extraction from explicitly labeled fields.

    This intentionally returns None rather than guessing from arbitrary names
    on a form (which may be the taxpayer or recipient).
    """
    text = re.sub(r"[‘’ʼ′`]", "'", text)
    lines = [re.sub(r"\s+", " ", line).strip(" :|\t") for line in text.splitlines()]
    labels = (
        "employer's name", "employer name", "payer's name", "payer name",
        "lender's name", "lender name", "filer's name", "filer name",
        "financial institution", "brokerage firm",
    )
    placeholder_terms = (
        "address", "city or town", "state or province", "country", "zip code",
        "employee's name", "recipient's name", "social security", "account number",
    )
    for index, line in enumerate(lines):
        low = line.lower()
        for label in labels:
            position = low.find(label)
            if position < 0:
                continue
            tail = line[position + len(label):].strip(" :,-")
            if tail and not any(term in tail.lower() for term in placeholder_terms) and len(tail) >= 3:
                return tail[:100]
            for candidate in lines[index + 1:index + 3]:
                candidate_low = candidate.lower()
                if not candidate or any(term in candidate_low for term in placeholder_terms):
                    continue
                if any(other in candidate_low for other in labels):
                    continue
                # Another box label (e.g., "Employee's SSA number"), not a value.
                if re.search(r"\b[a-z]+'s\b|\bnumber\b|\bidentification\b", candidate_low):
                    continue
                if len(candidate) >= 3 and not re.fullmatch(r"[0-9 .,/()-]+", candidate):
                    return candidate[:100]
    return None


def page_number_hint(text: str) -> tuple[Optional[int], Optional[int]]:
    match = re.search(r"\bpage\s+(\d{1,3})\s+(?:of|/)\s+(\d{1,3})\b", text, re.I)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


CONTINUATION_TERMS = (
    "continued", "continuation", "see next page", "page follows", "carry over", "carryover",
)


def copy_label(text: str) -> Optional[str]:
    """The form copy printed on the page (e.g., 'B' for Copy B), if any."""
    match = re.search(r"\bcopy\s+([a-d12])\b", normalize_text(text))
    return match.group(1).upper() if match else None


def amounts_key(text: str) -> str:
    """Opaque digest of the money amounts on a page.

    Identical copies of one form (Copy B, Copy C, Copy 2...) carry identical
    amounts. A digest lets grouping compare them without storing the amounts.
    """
    amounts = sorted(set(re.findall(_AMOUNT, normalize_text(text))))
    return hashlib.sha256("|".join(amounts).encode()).hexdigest()[:16]


def has_continuation_text(text: str) -> bool:
    normalized = normalize_text(text)
    return any(term in normalized for term in CONTINUATION_TERMS)

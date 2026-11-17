"""Position-aware text helpers.

Form PDFs and OCR output often emit text in an order unrelated to the visual
layout (columns interleaved, values far from their box labels). These helpers
rebuild visual rows from word coordinates so a value can be read from the box
directly beneath its label.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import median
from typing import Iterable, Optional

Word = tuple[float, float, float, float, str]  # x0, y0, x1, y1, text


@dataclass
class Segment:
    """A run of words on one visual row, split from neighbors by a wide gap."""
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


def words_to_segments(words: Iterable[Word]) -> list[list[Segment]]:
    """Group words into visual rows, then split each row into column segments."""
    words = [w for w in words if w[4].strip()]
    if not words:
        return []
    line_height = median(w[3] - w[1] for w in words) or 1.0

    rows: list[list[Word]] = []
    row_center = 0.0
    for word in sorted(words, key=lambda w: (w[1] + w[3]) / 2):
        center = (word[1] + word[3]) / 2
        if rows and abs(center - row_center) <= line_height * 0.5:
            rows[-1].append(word)
            row_center = sum((w[1] + w[3]) / 2 for w in rows[-1]) / len(rows[-1])
        else:
            rows.append([word])
            row_center = center

    result: list[list[Segment]] = []
    for row in rows:
        row.sort(key=lambda w: w[0])
        segments: list[list[Word]] = [[row[0]]]
        for word in row[1:]:
            previous = segments[-1][-1]
            # Column gaps on forms are several characters wide; word gaps
            # (even with irregular OCR boxes) are narrower.
            if word[0] - previous[2] > max(word[3] - word[1], previous[3] - previous[1]) * 2.5:
                segments.append([word])
            else:
                segments[-1].append(word)
        result.append([
            Segment(
                min(w[0] for w in seg), min(w[1] for w in seg),
                max(w[2] for w in seg), max(w[3] for w in seg),
                " ".join(w[4] for w in seg),
            )
            for seg in segments
        ])
    return result


def segments_to_text(rows: list[list[Segment]]) -> str:
    """Render rows as text; column segments on one row are separated by ' | '."""
    return "\n".join(" | ".join(seg.text for seg in row) for row in rows)


_ISSUER_LABEL = re.compile(
    r"\b(?:employer|payer|lender|filer|recipient/lender|trustee)'?s?\s+name\b|\bfinancial\s+institution\b|\bbrokerage\s+firm\b",
    re.I,
)
# Text that is part of a box label (or its continuation), never a value.
_LABEL_TEXT = re.compile(
    r"\baddress\b|\bzip\b|\bpostal\s+code\b|\btelephone\b|\bcity\s+or\s+town\b|\bstate\s+or\s+province\b|"
    r"\bidentification\b|\bnumber\b|\bstreet\b",
    re.I,
)
# A possessive heading (e.g., "RECIPIENT'S TIN") means we've reached another box.
_OTHER_BOX = re.compile(r"\b[a-z]+'s\b", re.I)


def _normalize_quotes(text: str) -> str:
    return re.sub(r"[‘’ʼ′`]", "'", text)


def extract_issuer_from_layout(rows: list[list[Segment]]) -> Optional[str]:
    """Return the first value printed beneath an employer/payer/lender name label."""
    segments = [seg for row in rows for seg in row]
    for label in segments:
        if not _ISSUER_LABEL.search(_normalize_quotes(label.text)):
            continue
        height = max(label.y1 - label.y0, 1.0)
        below = sorted(
            (
                seg for seg in segments
                if seg.y0 >= label.y1 - height * 0.3
                and seg.y0 <= label.y1 + height * 8
                and seg is not label
                and seg.x0 >= label.x0 - height * 2
                and seg.x0 < label.x0 + (label.x1 - label.x0) * 0.6
            ),
            key=lambda seg: seg.y0,
        )
        for candidate in below:
            text = _normalize_quotes(candidate.text).strip(" :|,-")
            if _OTHER_BOX.search(text):
                break
            if _LABEL_TEXT.search(text):
                continue
            if len(re.findall(r"[A-Za-z]", text)) >= 3:
                return text[:100]
    return None

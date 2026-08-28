from __future__ import annotations

import re


def extract_cin(text: str) -> str | None:
    match = re.search(r"\b[A-Z]{1,2}\d{5,6}\b", text)
    return match.group(0) if match else None


def extract_cnss(text: str) -> str | None:
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 9:
        return digits[:9]
    return None


def extract_date_embauche(text: str) -> str | None:
    # YYYY-MM-DD or YYYY/MM/DD first (ISO + slash variant).
    match = re.search(r"\b(\d{4})[/-](\d{2})[/-](\d{2})\b", text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    # DD/MM/YYYY or DD-MM-YYYY — common in Tunisian HR documents.
    match = re.search(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b", text)
    if match:
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
    return None


def extract_salaire_brut(text: str) -> float | None:
    """Match numbers with optional thousand separators (space, comma, dot).

    Captures the first numeric block immediately following a salary
    keyword, normalises thousand separators, then parses as float.
    """
    match = re.search(
        r"(?:salaire\s*(?:brut)?|brut\s*(?:salaire)?)\s*[:\-]?\s*"
        r"([0-9]+(?:[\s.,][0-9]{3})*(?:[.,][0-9]{1,2})?)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    raw = match.group(1)
    # Eliminate thousand separators (spaces and dots that sit between
    # digit groups), then turn the decimal comma into a dot.
    normalized = re.sub(r"[\s.]", "", raw).replace(",", ".")
    return float(normalized)


def extract_nom_prenom(text: str) -> tuple[str | None, str | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        parts = line.split()
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
    return None, None


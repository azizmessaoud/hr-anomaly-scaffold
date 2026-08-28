from __future__ import annotations

import re


SALARY_LABEL = re.compile(
    r"(?:"
    r"salaire\s*(?:brut)?(?:\s+(?:mensuel|monthly))?"
    r"|brut\s*(?:salaire)?"
    r"|salary(?:\s+(?:gross|brut|monthly))?"
    r"|gross\s+salary"
    r")",
    flags=re.IGNORECASE,
)


def extract_cin(text: str) -> str | None:
    match = re.search(r"\b[A-Z]{1,2}\d{5,6}\b", text)
    return match.group(0) if match else None


def extract_cnss(text: str) -> str | None:
    labelled = re.search(
        r"(?:n\s*[´`'’]?\s*[°ºo]?\s*)?(?:cnss|num[eé]ro\s+cnss)\s*[:\-]?\s*(\d{9,})\b",
        text,
        flags=re.IGNORECASE,
    )
    if labelled:
        return labelled.group(1)[:9]
    return None


def extract_date_embauche(text: str) -> str | None:
    labelled = re.search(
        r"(?:date\s+d['’]?embauche|date\s+embauche|date|embauch[eé](?:e|é)?(?:\s+le)?)"
        r"\s*[:\-]?\s*"
        r"(?P<date>\d{4}[/-]\d{2}[/-]\d{2}|\d{2}[/-]\d{2}[/-]\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if not labelled:
        return None
    value = labelled.group("date")
    match = re.fullmatch(r"(\d{4})[/-](\d{2})[/-](\d{2})", value)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    # DD/MM/YYYY or DD-MM-YYYY — common in Tunisian HR documents.
    match = re.fullmatch(r"(\d{2})[/-](\d{2})[/-](\d{4})", value)
    if match:
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
    return None


def _normalize_salary(raw: str) -> float:
    value = re.sub(r"\s", "", raw.strip())
    if not value or not re.fullmatch(r"[\d.,]+", value):
        raise ValueError(f"Invalid salary format: {raw!r}")

    dot = value.rfind(".")
    comma = value.rfind(",")
    if dot != -1 and comma != -1:
        if dot > comma:
            value = value.replace(",", "")
        else:
            value = value.replace(".", "").replace(",", ".")
    elif dot != -1 or comma != -1:
        separator = "." if dot != -1 else ","
        position = value.rfind(separator)
        after = value[position + 1:]
        if len(after) == 3:
            value = value.replace(",", "").replace(".", "")
        elif separator == ",":
            value = value.replace(",", ".")
    return float(value)


def extract_salaire_brut(text: str) -> float | None:
    """Match numbers with optional thousand separators (space, comma, dot).

    Captures the first numeric block immediately following a salary
    keyword, normalises thousand separators, then parses as float.
    """
    match = re.search(
        SALARY_LABEL.pattern + r"\s*[:\-]?\s*"
        r"([0-9]+(?:[\s.,][0-9]{3})*(?:[.,][0-9]{1,2})?)",
        text,
        flags=SALARY_LABEL.flags,
    )
    if not match:
        return None
    raw = match.group(1)
    # Eliminate thousand separators (spaces and dots that sit between
    # digit groups), then turn the decimal comma into a dot.
    return _normalize_salary(raw)


def extract_nom_prenom(text: str) -> tuple[str | None, str | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    nom: str | None = None
    prenom: str | None = None
    for line in lines:
        match = re.match(r"(?i)^nom\s*[:\-]\s*(?P<value>.+?)\s*$", line)
        if match:
            nom = match.group("value").strip()
        match = re.match(r"(?i)^pr[ée]nom\s*[:\-]\s*(?P<value>.+?)\s*$", line)
        if match:
            prenom = match.group("value").strip()
    if nom is not None or prenom is not None:
        return nom, prenom
    for line in lines:
        parts = line.split()
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
    return None, None


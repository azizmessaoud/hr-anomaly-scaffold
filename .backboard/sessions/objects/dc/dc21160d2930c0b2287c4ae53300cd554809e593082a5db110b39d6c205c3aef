from __future__ import annotations

import re
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class RecStatus(StrEnum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class Flag(BaseModel):
    moteur: str
    detail: str
    score: Optional[float] = None


class HRRecord(BaseModel):
    id: str = Field(..., description="Stable identifier, typically a UUID")
    revision: int = Field(default=0, ge=0, description="Increments on resubmission")
    nom: Optional[str] = None
    prenom: Optional[str] = None
    cin: Optional[str] = None
    cnss: Optional[str] = None
    date_embauche: Optional[str] = None
    salaire_brut: Optional[float] = None
    poste: Optional[str] = None
    departement: Optional[str] = None
    confiance: float = Field(default=0.0, ge=0.0, le=1.0)
    flags: list[Flag] = Field(default_factory=list)
    statut: RecStatus = Field(default=RecStatus.RED)
    erreur_traitement: Optional[str] = Field(default=None)

    @field_validator("cin")
    @classmethod
    def validate_cin_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        if not re.fullmatch(r"[A-Z]{1,2}\d{5,6}", v.strip()):
            raise ValueError(
                "CIN must match pattern [A-Z]{1,2}\\d{5,6}, e.g. AB123456"
            )
        return v.strip().upper()

    @field_validator("cnss")
    @classmethod
    def validate_cnss_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        digits = re.sub(r"\D", "", v)
        if len(digits) != 9:
            raise ValueError("CNSS must contain exactly 9 digits")
        return digits

    @field_validator("date_embauche")
    @classmethod
    def validate_date_embauche(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()):
            raise ValueError("date_embauche must be ISO format YYYY-MM-DD")
        return v.strip()

    @field_validator("salaire_brut")
    @classmethod
    def validate_salaire_brut_positive(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("salaire_brut must be greater than zero")
        return v

"""Config-target inventory helpers for PSD-linked parameters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PURE_DIRECT_KEYS = {
    "DOWNPAYMENT_FTB_SCALE",
    "DOWNPAYMENT_FTB_SHAPE",
    "DOWNPAYMENT_OO_SCALE",
    "DOWNPAYMENT_OO_SHAPE",
    "BANK_LTI_HARD_MAX_FTB",
    "BANK_LTI_HARD_MAX_HM",
}

PURE_BLOCKED_KEYS = {
    "MORTGAGE_DURATION_YEARS",
    "BANK_AFFORDABILITY_HARD_MAX",
}


@dataclass(frozen=True)
class PsdInventoryRow:
    """One PSD-linked config target record."""

    key: str
    value: str
    comment: str
    classification: str
    status: str



def classify_psd_key(key: str) -> str:
    if key in PURE_DIRECT_KEYS:
        return "pure_direct"
    if key in PURE_BLOCKED_KEYS:
        return "pure_blocked"
    return "hybrid"



def status_for_classification(classification: str) -> str:
    if classification == "pure_direct":
        return "in_scope"
    if classification == "pure_blocked":
        return "blocked"
    return "out_of_scope"



def read_psd_inventory(config_path: Path | str) -> list[PsdInventoryRow]:
    """Read all PSD-tagged keys from a Java-style config.properties file."""
    path = Path(config_path)
    if not path.exists():
        raise ValueError(f"Missing config file: {path}")

    rows: list[PsdInventoryRow] = []
    pending_comments: list[str] = []

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()

            if stripped.startswith("#"):
                pending_comments.append(stripped.lstrip("#").strip())
                continue

            if not stripped:
                pending_comments = []
                continue

            if stripped.startswith("!"):
                pending_comments = []
                continue

            if "=" not in stripped:
                pending_comments = []
                continue

            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip()
            comment = " ".join(comment for comment in pending_comments if comment).strip()
            pending_comments = []

            if "PSD" not in comment and "psd" not in comment:
                continue

            classification = classify_psd_key(key)
            rows.append(
                PsdInventoryRow(
                    key=key,
                    value=value,
                    comment=comment,
                    classification=classification,
                    status=status_for_classification(classification),
                )
            )

    return rows


__all__ = [
    "PURE_BLOCKED_KEYS",
    "PURE_DIRECT_KEYS",
    "PsdInventoryRow",
    "classify_psd_key",
    "read_psd_inventory",
    "status_for_classification",
]

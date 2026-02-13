"""Shared column and target key dataclasses for NMG scripts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DesiredRentColumnNames:
    qhousing: str = "qhousing"
    weight: str = "we_factor"
    income_band: str = "incomev2comb"
    income_free_1: str = "qincomefreev2_n_1"
    income_free_2: str = "qincomefreev2_n_2"
    income_free_3: str = "qincomefreev2_n_3"
    rent_band: str = "spq07"
    rent_free_candidates: tuple[str, ...] = ("SPQ07free_1", "spq07free_1")


@dataclass(frozen=True)
class RentalLognormalColumns:
    qhousing: str = "qhousing"
    rent_candidates: tuple[str, ...] = ("SPQ07free_1", "spq07free_1")
    weight: str = "we_factor"


@dataclass(frozen=True)
class RentalParameterColumns:
    qhousing: str = "qhousing"
    rent_candidates: tuple[str, ...] = ("SPQ07free_1", "spq07free_1")
    weight: str = "we_factor"


@dataclass(frozen=True)
class DesiredRentTargetKeys:
    scale: str = "DESIRED_RENT_SCALE"
    exponent: str = "DESIRED_RENT_EXPONENT"


@dataclass(frozen=True)
class RentalTargetKeys:
    scale: str = "RENTAL_PRICES_SCALE"
    shape: str = "RENTAL_PRICES_SHAPE"


@dataclass(frozen=True)
class BtlStrategyColumnNames:
    weight: str = "we_factor"
    btl_owner_screen: str = "boe72"
    boe77_option_columns: tuple[str, ...] = (
        "boe77_1",
        "boe77_2",
        "boe77_3",
        "boe77_4",
        "boe77_5",
        "boe77_6",
        "boe77_7",
    )
    proxy_concern_column: str = "qbe22b"
    proxy_reason_columns: tuple[str, ...] = (
        "be22bb_1",
        "be22bb_2",
        "be22bb_3",
        "be22bb_4",
        "be22bb_5",
        "be22bb_6",
        "be22bb_7",
        "be22bb_8",
        "be22bb_9",
    )


@dataclass(frozen=True)
class BtlStrategyTargetKeys:
    income: str = "BTL_P_INCOME_DRIVEN"
    capital: str = "BTL_P_CAPITAL_DRIVEN"

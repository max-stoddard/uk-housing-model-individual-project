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
    rent: str = "SPQ07free_1"
    weight: str = "we_factor"


@dataclass(frozen=True)
class DesiredRentTargetKeys:
    scale: str = "DESIRED_RENT_SCALE"
    exponent: str = "DESIRED_RENT_EXPONENT"


@dataclass(frozen=True)
class RentalTargetKeys:
    scale: str = "RENTAL_PRICES_SCALE"
    shape: str = "RENTAL_PRICES_SHAPE"

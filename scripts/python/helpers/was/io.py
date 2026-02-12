"""I/O helpers for WAS calibration and validation scripts."""

from __future__ import annotations

import os

import pandas as pd

from scripts.python.helpers.was.constants import WAS_COLUMN_MAP
from scripts.python.helpers.was.config import WAS_DATA_FILENAME, WAS_DATA_SEPARATOR


def read_was_data(root: str, column_constants: list[str]) -> pd.DataFrame:
    """Read WAS data with internal column names."""
    use_columns = [WAS_COLUMN_MAP[column] for column in column_constants]
    chunk = pd.read_csv(
        os.path.join(root, WAS_DATA_FILENAME),
        usecols=use_columns,
        sep=WAS_DATA_SEPARATOR,
    )
    rename_map = {WAS_COLUMN_MAP[column]: column for column in column_constants}
    chunk.rename(columns=rename_map, inplace=True)
    return chunk


def read_results(file_name: str, start_time: int, end_time: int) -> list[float]:
    """Read micro-data from file_name, one line per year, returning values within the time range."""
    data_float: list[float] = []
    with open(file_name, "r") as handle:
        for line in handle:
            stripped_line = line.strip()
            if not stripped_line:
                continue
            delimiter = ";" if ";" in stripped_line else ","
            columns = [column.strip() for column in stripped_line.split(delimiter)]
            if not columns or not columns[0]:
                continue
            try:
                year = int(columns[0])
            except ValueError:
                continue
            if start_time <= year <= end_time:
                for column in columns[1:]:
                    if column:
                        data_float.append(float(column))
    return data_float

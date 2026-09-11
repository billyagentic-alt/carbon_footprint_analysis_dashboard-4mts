import logging
import sys
import time
import random
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping, Optional, Union

import pandas as pd
import requests
import streamlit as st

from src.config import CONFIG

__all__ = [
    "get_logger",
    "set_log_level",
    "format_large_number",
    "safe_merge",
    "add_year_column",
    "to_numeric",
    "DataFetchError",
    "http_get",
    "cache_dataframe",
]


def _default_log_formatter() -> logging.Formatter:
    """
    Return a formatter used for the default logger.

    The format includes the timestamp, log level, logger name and the message.
    """
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    return logging.Formatter(fmt=fmt, datefmt=datefmt)


def get_logger(name: str = __name__) -> logging.Logger:
    """
    Retrieve a configured :class:`logging.Logger` instance.

    The logger is configured with a :class:`logging.StreamHandler` that writes to
    ``sys.stderr`` using a human‑readable format. If the logger already has
    handlers attached, they are left untouched to avoid duplicate log lines.

    Parameters
    ----------
    name:
        Name of the logger. By default the module name is used.

    Returns
    -------
    logging.Logger
        Configured logger ready for use.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(_default_log_formatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


def set_log_level(level: Union[int, str]) -> None:
    """
    Set the logging level for **all** loggers created via :func:`get_logger`.

    This is a convenience wrapper used mainly in Streamlit applications where
    the user can toggle verbosity from the UI.

    Parameters
    ----------
    level:
        Logging level as an integer (e.g. ``logging.DEBUG``) or a case‑insensitive
        string such as ``"debug"``, ``"info"``, ``"warning"``, ``"error"``,
        ``"critical"``.
    """
    if isinstance(level, str):
        level = level.upper()
        if not hasattr(logging, level):
            raise ValueError(f"Invalid logging level string: {level!r}")
        level = getattr(logging, level)

    logging.basicConfig(level=level)


def format_large_number(
    value: Union[int, float, str],
    *,
    decimal_places: int = 2,
    use_space_separator: bool = True,
    locale: Literal["fr", "en"] = "fr",
) -> str:
    """
    Format a large number according to French (or English) conventions.

    The function inserts a non‑breaking space (or a regular space) as the
    thousands separator and uses a comma as decimal separator for French
    locale. For English locale a comma is used for thousands and a dot for
    decimals.

    Parameters
    ----------
    value:
        Numeric value to format. Strings are accepted and converted to ``float``.
    decimal_places:
        Number of digits after the decimal separator. Ignored for integer
        values.
    use_space_separator:
        When ``True`` (default) a space is used as thousands separator for the
        French locale. For English locale a comma is always used.
    locale:
        Either ``"fr"`` (default) or ``"en"``. Determines the separator
        characters.

    Returns
    -------
    str
        Human‑readable representation of ``value``.

    Raises
    ------
    ValueError
        If ``value`` cannot be converted to a number.
    """
    logger = get_logger(__name__)

    try:
        num = float(value)
    except (TypeError, ValueError) as exc:
        logger.error("Unable to convert %r to float for formatting", value)
        raise ValueError(f"Cannot format non‑numeric value: {value!r}") from exc

    is_int = num.is_integer()
    if is_int:
        num_int = int(num)
        if locale == "fr":
            sep = "\u202f" if use_space_separator else ""
            formatted = f"{num_int:,}".replace(",", sep)
        else:
            formatted = f"{num_int:,}"
        return formatted

    # Float handling
    if locale == "fr":
        thousands_sep = "\u202f" if use_space_separator else ""
        decimal_sep = ","
    else:
        thousands_sep = ","
        decimal_sep = "."

    integer_part, fractional_part = divmod(abs(num), 1)
    integer_str = f"{int(integer_part):,}".replace(",", thousands_sep)
    fractional_str = f"{fractional_part:.{decimal_places}f}"[2:]  # strip "0."
    sign = "-" if num < 0 else ""

    return f"{sign}{integer_str}{decimal_sep}{fractional_str}"


def safe_merge(
    left: pd.DataFrame,
    right: pd.DataFrame,
    on: Union[str, Iterable[str]],
    how: Literal["inner", "left", "right", "outer"] = "inner",
    *,
    suffixes: tuple[str, str] = ("_x", "_y"),
    validate: Optional[Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]] = None,
) -> pd.DataFrame:
    """
    Perform a pandas ``merge`` with additional safety checks.

    The function validates that the merge keys exist in both DataFrames and,
    optionally, that the merge cardinality matches the expected ``validate``
    argument. Errors are raised with clear messages to aid debugging.

    Parameters
    ----------
    left, right:
        DataFrames to merge.
    on:
        Column name(s) to join on.
    how:
        Type of merge – ``"inner"``, ``"left"``, ``"right"``, ``"outer"``.
    suffixes:
        Suffixes to apply to overlapping column names.
    validate:
        Optional pandas ``validate`` argument to enforce merge cardinality.

    Returns
    -------
    pd.DataFrame
        Result of the merge operation.

    Raises
    ------
    KeyError
        If any of the ``on`` columns are missing in either DataFrame.
    ValueError
        If ``validate`` is provided and the merge does not satisfy the
        constraint.
    """
    logger = get_logger(__name__)

    missing_left = [col for col in pd.core.common.flatten(on) if col not in left.columns]
    missing_right = [col for col in pd.core.common.flatten(on) if col not in right.columns]

    if missing_left:
        logger.error("Missing columns in left DataFrame for merge: %s", missing_left)
        raise KeyError(f"Columns missing in left DataFrame: {missing_left}")
    if missing_right:
        logger.error("Missing columns in right DataFrame for merge: %s", missing_right)
        raise KeyError(f"Columns missing in right DataFrame: {missing_right}")

    try:
        merged = pd.merge(left, right, on=on, how=how, suffixes=suffixes, validate=validate)
    except ValueError as exc:
        logger.error("Merge validation failed: %s", exc)
        raise

    logger.debug(
        "Merged DataFrames: left=%s rows, right=%s rows, result=%s rows, how=%s",
        left.shape[0],
        right.shape[0],
        merged.shape[0],
        how,
    )
    return merged


def add_year_column(
    df: pd.DataFrame,
    date_column: str,
    new_column_name: str = "year",
    *,
    date_format: Optional[str] = None,
) -> pd.DataFrame:
    """
    Extract the year from a date column and store it in a new column.

    The function works with pandas ``datetime`` objects as well as strings that
    can be parsed by :func:`pandas.to_datetime`. The original DataFrame is not
    modified; a copy with the additional column is returned.

    Parameters
    ----------
    df:
        Input DataFrame.
    date_column:
        Name of the column containing date information.
    new_column_name:
        Name of the column that will hold the extracted year.
    date_format:
        Optional ``strftime`` format string to speed up parsing when the date
        format is known.

    Returns
    -------
    pd.DataFrame
        Copy of ``df`` with an extra ``new_column_name`` column.

    Raises
    ------
    KeyError
        If ``date_column`` does not exist.
    ValueError
        If the column cannot be parsed as dates.
    """
    logger = get_logger(__name__)

    if date_column not in df.columns:
        logger.error("Date column %s not found in DataFrame", date_column)
        raise KeyError(f"Date column '{date_column}' not found in DataFrame")

    df_copy = df.copy()

    try:
        if date_format:
            df_copy[date_column] = pd.to_datetime(df_copy[date_column], format=date_format, errors="raise")
        else:
            df_copy[date_column] = pd.to_datetime(df_copy[date_column], errors="raise")
    except Exception as exc:
        logger.error("Failed to parse dates in column %s: %s", date_column, exc)
        raise ValueError(f"Unable to parse dates in column '{date_column}'") from exc

    df_copy[new_column_name] = df_copy[date_column].dt.year
    logger.debug(
        "Added year column '%s' based on '%s'; resulting DataFrame has %d rows",
        new_column_name,
        date_column,
        df_copy.shape[0],
    )
    return df_copy


def to_numeric(
    df: pd.DataFrame,
    columns: Optional[Iterable[str]] = None,
    errors: Literal["raise", "ignore", "coerce"] = "coerce",
) -> pd.DataFrame:
    """
    Convert one or several columns of a DataFrame to numeric dtype.

    Parameters
    ----------
    df:
        Input DataFrame.
    columns:
        Iterable of column names to convert. If ``None``, all object‑type columns
        are considered.
    errors:
        How to handle conversion errors – ``'raise'``, ``'ignore'`` or
        ``'coerce'`` (default). ``'coerce'`` turns invalid parsing into ``NaN``.

    Returns
    -------
    pd.DataFrame
        A copy of ``df`` with the selected columns converted to numeric.
    """
    logger = get_logger(__name__)

    df_copy = df.copy()
    target_cols = list(columns) if columns is not None else df_copy.select_dtypes(include="object").columns.tolist()

    for col in target_cols:
        if col not in df_copy.columns:
            logger.warning("Column %s not found in DataFrame; skipping numeric conversion", col)
            continue
        try:
            df_copy[col] = pd.to_numeric(df_copy[col], errors=errors)
            logger.debug("Converted column %s to numeric", col)
        except Exception as exc:
            logger.error("Failed to convert column %s to numeric: %s", col, exc)
            raise

    return df_copy


class DataFetchError(Exception):
    """
    Custom exception raised when an HTTP request fails after the configured
    number of retries.
    """
    pass


def http_get(url: str, timeout: int = 10, retries: int = 3) -> requests.Response:
    """
    Perform an HTTP GET request with exponential back‑off retries.

    Parameters
    ----------
    url:
        The URL to request.
    timeout:
        Number of seconds to wait for a response from the server.
    retries:
        Number of additional attempts after the first failure. The wait time
        between attempts grows exponentially (1, 2, 4, … seconds) with a small
        random jitter.

    Returns
    -------
    requests.Response
        The successful response object.

   
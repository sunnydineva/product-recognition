"""Persistent, AI-owned global recognition configuration (no fallback cache)."""

import math
import os

import psycopg


class SettingsUnavailableError(Exception):
    """The persisted threshold could not be read or committed."""


def is_finite_number(value):
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )


def _settings_query(value=None):
    try:
        with psycopg.connect(
            os.environ["DATABASE_URL"],
            connect_timeout=3,
            options="-c statement_timeout=3000",
        ) as connection:
            with connection.cursor() as cursor:
                if value is None:
                    cursor.execute(
                        "SELECT min_similarity FROM recognition_settings WHERE id = 1"
                    )
                else:
                    cursor.execute(
                        "UPDATE recognition_settings SET min_similarity = %s "
                        "WHERE id = 1 RETURNING min_similarity",
                        (value,),
                    )
                row = cursor.fetchone()
                if row is None or not is_finite_number(row[0]) or not 0 <= row[0] <= 1:
                    raise SettingsUnavailableError("Missing or invalid recognition settings")
                result = float(row[0])
        # Return only after the connection context has committed successfully.
        return result
    except (psycopg.Error, KeyError) as error:
        raise SettingsUnavailableError("Recognition settings unavailable") from error


def get_min_similarity():
    return _settings_query()


def set_min_similarity(value):
    if not is_finite_number(value) or not 0 <= value <= 1:
        raise ValueError("minSimilarity must be a finite number between 0 and 1")
    return _settings_query(value)

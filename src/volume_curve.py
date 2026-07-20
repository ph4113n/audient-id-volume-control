import math


MUTE_DB = -128.0
CURVE_DB = 40.0


def percent_to_db(percent: int, ceiling_db: float) -> float:
    if percent <= 0:
        return MUTE_DB
    value = ceiling_db + CURVE_DB * math.log10(percent / 100.0)
    return max(MUTE_DB, min(ceiling_db, value))


def db_to_percent(db: float, ceiling_db: float) -> int:
    if db <= MUTE_DB + 0.01:
        return 0
    value = round(100.0 * 10 ** ((db - ceiling_db) / CURVE_DB))
    return max(0, min(100, value))

"""미국 거래일 (멈춤 판정용). 휴장일은 NYSE 공식 표 (us_holidays.csv)."""
import csv
import datetime as dt
import pathlib
from functools import lru_cache

HOLIDAYS_CSV = pathlib.Path(__file__).with_name("us_holidays.csv")
KST = dt.timezone(dt.timedelta(hours=9))


@lru_cache(maxsize=None)
def us_holidays() -> frozenset[dt.date]:
    with HOLIDAYS_CSV.open(encoding="utf-8") as f:
        return frozenset(dt.date.fromisoformat(row["date"]) for row in csv.DictReader(f))


def is_trading_day(day: dt.date) -> bool:
    return day.weekday() < 5 and day not in us_holidays()


def workday(start: dt.date, days: int) -> dt.date:
    """WORKDAY(start, days)와 같다. days가 0이면 start."""
    day, step, left = start, (1 if days > 0 else -1), abs(days)
    while left:
        day += dt.timedelta(days=step)
        if is_trading_day(day):
            left -= 1
    return day


def kst_today(now: dt.datetime | None = None) -> dt.date:
    """GitHub Actions는 UTC로 돈다. 판정은 한국 날짜로 한다."""
    now = now or dt.datetime.now(dt.timezone.utc)
    return now.astimezone(KST).date()


def holidays_cover(day: dt.date) -> bool:
    """휴장일 표가 그 해를 담고 있는가. 표가 끝나면 거래일 판정이 틀려지므로 알린다."""
    return any(h.year >= day.year for h in us_holidays())

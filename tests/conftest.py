"""시험용 가짜 출처. 네트워크를 쓰지 않는다."""
import datetime as dt

import pytest

from marketdata.calendar import is_trading_day


def trading_days(end: dt.date, count: int) -> list[dt.date]:
    days, day = [], end
    while len(days) < count:
        if is_trading_day(day):
            days.append(day)
        day -= dt.timedelta(days=1)
    return list(reversed(days))


def fred_csv(column: str, days: list[dt.date], start: float = 100.0, step: float = 0.1) -> str:
    rows = [f"{d.isoformat()},{start + i * step:.2f}" for i, d in enumerate(days)]
    return "\n".join([f"observation_date,{column}"] + rows) + "\n"


def cboe_csv(days: list[dt.date], value: float = 20.0) -> str:
    rows = [f"{d.strftime('%m/%d/%Y')},{value},{value},{value},{value}" for d in days]
    return "\n".join(["DATE,OPEN,HIGH,LOW,CLOSE"] + rows) + "\n"


def whit3rabbit_csv(days: list[dt.date], value: float = 30.0) -> str:
    return "\n".join(["Date,Fear Greed,Rating"] + [f"{d.isoformat()},{value},fear" for d in days]) + "\n"


def monthly_csv(end_month: dt.date, months: int = 300, start: float = 10.0) -> str:
    rows, y, m = [], end_month.year, end_month.month
    dates = []
    for _ in range(months):
        dates.append(dt.date(y, m, 1))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    for i, d in enumerate(reversed(dates)):
        rows.append(f"{d.isoformat()},{start * (1.005 ** i):.4f},0,0,0,0,0,0,0,0")
    return "\n".join(["Date,SP500,Dividend,Earnings,Consumer Price Index,Long Interest Rate,Real Price,"
                      "Real Dividend,Real Earnings,PE10"] + rows) + "\n"


class FakeWeb:
    """URL → 본문. 없는 URL이나 None은 받기 실패로 낸다."""

    def __init__(self, pages: dict[str, str | None]):
        self.pages = pages
        self.calls: list[str] = []

    def __call__(self, url: str, headers=None) -> str:
        self.calls.append(url)
        body = self.pages.get(url)
        if body is None:
            raise RuntimeError(f"받기 실패 {url}")
        return body


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """data/ 아래 파일을 임시 폴더로 바꾼다."""
    from marketdata import cli, sources

    data = tmp_path / "data"
    (data / "sources").mkdir(parents=True)
    monkeypatch.setattr(cli, "DATA", data)
    monkeypatch.setattr(cli, "STATE", data / "sources.json")
    monkeypatch.setattr(sources, "LAST_GOOD", data / "sources")
    monkeypatch.setattr(sources, "OWN_FEAR_GREED_FILE", data / "fear_greed.csv")
    return data

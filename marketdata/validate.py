"""받은 데이터 검사: 멈춤 판정과 값 검사 (잔잔한복리 구조 설계 D-19).

하나라도 걸리면 그 출처를 실패로 보고 다음 순위로 넘어간다.
"""
import datetime as dt
from dataclasses import dataclass

from marketdata.calendar import workday
from marketdata.series import Series


@dataclass(frozen=True)
class Rules:
    low: float
    high: float
    jump: float | None = None  # 하루(한 줄) 변동 한계
    jump_relative: bool = True  # True면 비율(0.25 = ±25%), False면 절대값
    max_ratio: float | None = None  # 다음 값 ÷ 이전 값 상한 (VIX 3배)


FEAR_GREED = Rules(low=0, high=100)
VIX = Rules(low=5, high=150, max_ratio=3.0)
INDEX = Rules(low=0.000001, high=1e7, jump=0.25)  # 일별: 하루 ±25% (1987-10-19 −20.5%보다 넓게)
INDEX_MONTHLY = Rules(low=0.000001, high=1e7, jump=0.75)  # 월평균: 한 달 ±75% (1932-08 +50%, 1929-11 −26.5%보다 넓게, 자릿수 오류는 잡음)


def problems(series: Series, rules: Rules, previous_rows: int | None = None) -> list[str]:
    found = []
    if not series:
        return ["값 없음"]
    dates = [d for d, _ in series]
    if any(b <= a for a, b in zip(dates, dates[1:])):
        found.append("날짜가 오름차순이 아니거나 중복")
    out_of_range = [d for d, v in series if not rules.low <= v <= rules.high]
    if out_of_range:
        found.append(f"범위 밖 값 {len(out_of_range)}개 (처음 {out_of_range[0]})")
    for (d0, v0), (d1, v1) in zip(series, series[1:]):
        if rules.jump is not None:
            change = abs(v1 / v0 - 1) if rules.jump_relative and v0 else abs(v1 - v0)
            if change > rules.jump:
                found.append(f"변동 한계 넘음 {d1} ({change:.3f})")
                break
        if rules.max_ratio is not None and v0 > 0 and not 1 / rules.max_ratio <= v1 / v0 <= rules.max_ratio:
            found.append(f"변동 한계 넘음 {d1} ({v1 / v0:.2f}배)")
            break
    if previous_rows is not None and len(series) < previous_rows:
        found.append(f"행 수가 줄었음 ({previous_rows} → {len(series)})")
    return found


def expected_latest_daily(today: dt.date, lag: int) -> dt.date:
    """오늘(한국 날짜) 기준 lag 거래일 전. 최신 날짜가 이보다 이르면 멈춘 것으로 본다."""
    return workday(today, -lag)


def expected_latest_month(today: dt.date, lag_months: int) -> dt.date:
    index = today.year * 12 + today.month - 1 - lag_months
    return dt.date(index // 12, index % 12 + 1, 1)


def is_fresh(series: Series, kind: str, today: dt.date, lag: int) -> tuple[bool, dt.date | None, dt.date]:
    """(최신인가, 최신 날짜, 기대 날짜)."""
    latest = series[-1][0] if series else None
    expected = expected_latest_daily(today, lag) if kind == "daily" else expected_latest_month(today, lag)
    return (latest is not None and latest >= expected), latest, expected


def agree(a: Series, b: Series, tolerance: float, relative: bool, last_n: int = 5) -> tuple[bool, float]:
    """겹치는 마지막 n일의 값이 허용 오차 안인가. (같은가, 가장 큰 차이)"""
    common = sorted(set(dict(a)) & set(dict(b)))[-last_n:]
    if not common:
        return True, 0.0
    da, db = dict(a), dict(b)
    diffs = [abs(da[d] / db[d] - 1) if relative else abs(da[d] - db[d]) for d in common]
    worst = max(diffs)
    return worst <= tolerance, worst

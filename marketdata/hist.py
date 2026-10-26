"""과거 비슷한 하락 뒤 기록 (잔잔한복리 구조 설계 D-08, 요구사항 FR-47).

월간 가격(월평균)으로 본다.
- 하락률 = 그달 가격 ÷ 최근 12개월(그달 포함) 가격 최고 − 1
- 사례 = 하락률이 −10%·−20%·−30% 이하로 처음 들어간 달. 구간마다 따로 센다.
  가격이 12개월 최고를 다시 넘기(하락률 0) 전까지 같은 구간의 사례는 한 번만 센다.
- 그 뒤 1년(12개월)·3년(36개월) 가격 수익률의 최저·중간·최고와 손실 사례 수. 배당은 넣지 않는다.
  1년·3년 뒤 값이 아직 없는 최근 사례는 그 통계에서 뺀다.
"""
import datetime as dt
import statistics
from dataclasses import dataclass

from marketdata.series import Series

BANDS = (("dd10", 0.10), ("dd20", 0.20), ("dd30", 0.30))
WINDOW_MONTHS = 12
HORIZONS = (("1y", 12), ("3y", 36))
EPS = 1e-9  # 정확히 −20%가 소수 오차로 −19.999…%가 되어 빠지지 않게


def drawdowns(monthly: Series) -> list[float]:
    values = [v for _, v in monthly]
    return [values[i] / max(values[max(0, i - WINDOW_MONTHS + 1): i + 1]) - 1 for i in range(len(values))]


def episodes(monthly: Series) -> dict[str, list[int]]:
    """구간마다 사례가 시작된 달의 위치 목록."""
    dd = drawdowns(monthly)
    found: dict[str, list[int]] = {name: [] for name, _ in BANDS}
    armed = {name: True for name, _ in BANDS}
    for i, d in enumerate(dd):
        if d >= 0:
            armed = {name: True for name, _ in BANDS}
        for name, threshold in BANDS:
            if armed[name] and d <= -threshold + EPS:
                found[name].append(i)
                armed[name] = False
    return found


@dataclass(frozen=True)
class BandStats:
    band: str
    n: int
    stats: dict[str, float | int | None]  # 1y_min … 3y_loss
    starts: list[dt.date]


def band_stats(monthly: Series) -> list[BandStats]:
    values = [v for _, v in monthly]
    out = []
    for name, starts in episodes(monthly).items():
        stats: dict[str, float | int | None] = {}
        for label, months in HORIZONS:
            returns = [values[i + months] / values[i] - 1 for i in starts if i + months < len(values)]
            stats[f"{label}_min"] = min(returns) if returns else None
            stats[f"{label}_med"] = statistics.median(returns) if returns else None
            stats[f"{label}_max"] = max(returns) if returns else None
            stats[f"{label}_loss"] = sum(1 for r in returns if r < 0)
        out.append(BandStats(name, len(starts), stats, [monthly[i][0] for i in starts]))
    return out


def current_band(drawdown_now: float) -> str:
    """지금 하락률이 해당하는 구간 (hist_*_now). −10%보다 얕으면 none."""
    for name, threshold in reversed(BANDS):
        if drawdown_now <= -threshold + EPS:
            return name
    return "none"

"""지표 정의 (잔잔한복리 구조 설계 D-05). 공용 지표 시트의 수식과 같은 정의를 쓴다.

- 하락률 = 종가 ÷ 최근 252거래일 종가 최고 − 1
- 200일선 대비 = 종가 ÷ 최근 200거래일 종가 평균 − 1
- RSI14 = Wilder 방식, 최근 250거래일로 계산 (앞 14개 변화의 단순 평균에서 시작해 평활)
- 10년 위치 = 최근 2,520거래일 일별 값의 분포. 백분위 경계값 101개(p0~p100)로 내보낸다
"""
from marketdata.series import Series

DD_WINDOW = 252
MA_WINDOW = 200
RSI_PERIOD = 14
RSI_WINDOW = 250
TEN_YEARS = 2520


def drawdown(closes: list[float]) -> float:
    window = closes[-DD_WINDOW:]
    return closes[-1] / max(window) - 1


def ma_ratio(closes: list[float]) -> float:
    window = closes[-MA_WINDOW:]
    return closes[-1] / (sum(window) / len(window)) - 1


def rsi_wilder(closes: list[float], period: int = RSI_PERIOD, window: int = RSI_WINDOW) -> float:
    prices = closes[-window:]
    changes = [b - a for a, b in zip(prices, prices[1:])]
    if len(changes) < period:
        raise ValueError(f"RSI에 변화 {period}개 이상 필요 (있는 것 {len(changes)})")
    gains = [max(c, 0.0) for c in changes]
    losses = [max(-c, 0.0) for c in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
    if avg_loss == 0:
        return 100.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def rolling(series: Series, fn, need: int) -> Series:
    """날마다 그날까지 need일의 종가로 fn을 계산한다. 앞쪽 need-1일은 계산하지 않는다(준비 구간)."""
    closes = [v for _, v in series]
    return [(series[i][0], fn(closes[i + 1 - need: i + 1])) for i in range(need - 1, len(series))]


def drawdown_series(series: Series) -> Series:
    return rolling(series, drawdown, DD_WINDOW)


def ma_ratio_series(series: Series) -> Series:
    return rolling(series, ma_ratio, MA_WINDOW)


def rsi_series(series: Series) -> Series:
    return rolling(series, rsi_wilder, RSI_WINDOW)


def breakpoints(values: list[float]) -> list[float]:
    """백분위 경계값 p0~p100. p_k = 정렬한 값의 round(k/100 × (n−1))번째.

    시트는 오늘 값을 MATCH(값, 경계값, 1) − 1로 찾아 "이하인 비율"(0~100%)로 쓴다.
    """
    if not values:
        raise ValueError("값 없음")
    ordered = sorted(values)
    n = len(ordered)
    return [ordered[round(k / 100 * (n - 1))] for k in range(101)]


def position(value: float, points: list[float]) -> int:
    """경계값 표에서 값의 위치(0~100). 시트의 MATCH(값, 경계값, 1) − 1과 같다. 가장 작은 값보다 작으면 0."""
    count = sum(1 for p in points if p <= value)
    return max(0, count - 1)


def last_ten_years(series: Series) -> Series:
    return series[-TEN_YEARS:]

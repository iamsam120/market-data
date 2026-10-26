"""거래일, 읽기, 검사, 지표, 과거 하락표."""
import datetime as dt

import pytest

from marketdata import hist, indicators as ind, series as S
from marketdata.calendar import kst_today, workday
from marketdata.validate import FEAR_GREED, INDEX, INDEX_MONTHLY, VIX, agree, is_fresh, problems

D = dt.date


# ---- 거래일 ----

def test_workday_skips_weekend_and_thanksgiving():
    assert workday(D(2026, 10, 26), -1) == D(2026, 10, 23)
    assert workday(D(2026, 11, 27), -2) == D(2026, 11, 24)


def test_kst_today():
    assert kst_today(dt.datetime(2026, 10, 25, 22, 0, tzinfo=dt.timezone.utc)) == D(2026, 10, 26)


# ---- 읽기 ----

def test_parsers():
    fred = "observation_date,SP500\n2026-10-20,7712.57\n2026-10-21,\n2026-10-22,7757.17\n"
    assert S.parse_fred(fred, "SP500") == [(D(2026, 10, 20), 7712.57), (D(2026, 10, 22), 7757.17)]
    cboe = "DATE,OPEN,HIGH,LOW,CLOSE\n10/23/2026,19.18,20.66,18.87,19.45\n"
    assert S.parse_cboe_vix(cboe) == [(D(2026, 10, 23), 19.45)]
    w = "Date,Fear Greed,Rating\n2026-10-23,20.9,extreme fear\n2026-10-23,21.0,extreme fear\n"
    assert S.parse_whit3rabbit(w) == [(D(2026, 10, 23), 21.0)]  # 같은 날짜는 마지막 값
    m = "Date,SP500,Dividend\n1871-01-01,4.44,0.26\n"
    assert S.parse_datasets_sp500(m) == [(D(1871, 1, 1), 4.44)]


def test_parser_rejects_changed_columns():
    with pytest.raises(ValueError, match="열 없음"):
        S.parse_fred("date,value\n2026-10-20,1\n", "SP500")


def test_monthly_average():
    daily = [(D(2026, 9, 29), 10.0), (D(2026, 9, 30), 20.0), (D(2026, 10, 1), 30.0)]
    assert S.monthly_average(daily) == [(D(2026, 9, 1), 15.0), (D(2026, 10, 1), 30.0)]


# ---- 값 검사 ----

def test_problems_detects_each_rule():
    good = [(D(2026, 10, 20), 20.0), (D(2026, 10, 21), 22.0)]
    assert problems(good, VIX) == []
    assert problems(list(reversed(good)), VIX) == ["날짜가 오름차순이 아니거나 중복"]
    assert "범위 밖" in problems([(D(2026, 10, 20), 101.0)], FEAR_GREED)[0]
    assert "변동 한계" in problems([(D(2026, 10, 20), 100.0), (D(2026, 10, 21), 70.0)], INDEX)[0]
    assert problems([(D(2026, 10, 20), 100.0), (D(2026, 10, 21), 150.0)], INDEX_MONTHLY) == []
    assert "변동 한계" in problems([(D(2026, 10, 20), 10.0), (D(2026, 10, 21), 40.0)], VIX)[0]
    assert "행 수가 줄었음" in problems(good, VIX, previous_rows=3)[0]
    assert problems([], VIX) == ["값 없음"]


def test_freshness_daily_and_monthly():
    today = D(2026, 10, 26)
    ok, latest, expected = is_fresh([(D(2026, 10, 22), 1.0)], "daily", today, 2)
    assert (ok, expected) == (True, D(2026, 10, 22))
    assert not is_fresh([(D(2026, 10, 21), 1.0)], "daily", today, 2)[0]
    assert is_fresh([(D(2026, 8, 1), 1.0)], "monthly", today, 2)[0]
    assert not is_fresh([(D(2026, 7, 1), 1.0)], "monthly", today, 2)[0]


def test_agree():
    a = [(D(2026, 10, 22), 19.44), (D(2026, 10, 23), 20.98)]
    assert agree(a, [(D(2026, 10, 23), 21.5)], 1.0, False)[0]
    assert not agree(a, [(D(2026, 10, 23), 25.0)], 1.0, False)[0]
    assert agree(a, [(D(2026, 1, 1), 1.0)], 1.0, False) == (True, 0.0)  # 겹치는 날 없음


# ---- 지표 (구조 설계 D-05) ----

def test_drawdown_and_ma():
    closes = [100.0] * 251 + [90.0]
    assert ind.drawdown(closes) == pytest.approx(-0.10)
    assert ind.ma_ratio([100.0] * 199 + [120.0]) == pytest.approx(120 / 100.1 - 1)


def test_rsi_extremes_and_hand_example():
    assert ind.rsi_wilder(list(range(1, 300))) == 100.0
    assert ind.rsi_wilder(list(range(300, 1, -1))) == 0.0
    # 변화 14개: +1 일곱 번, −1 일곱 번 → 평균 상승 = 평균 하락 → 50
    closes = [10.0]
    for i in range(14):
        closes.append(closes[-1] + (1 if i % 2 == 0 else -1))
    assert ind.rsi_wilder(closes, window=15) == pytest.approx(50.0)
    # 15번째 변화 +2: 평균 상승 (0.5×13+2)/14, 평균 하락 0.5×13/14
    closes.append(closes[-1] + 2)
    ag, al = (0.5 * 13 + 2) / 14, (0.5 * 13) / 14
    assert ind.rsi_wilder(closes, window=16) == pytest.approx(100 - 100 / (1 + ag / al))


def test_breakpoints_and_position():
    points = ind.breakpoints([float(v) for v in range(101)])
    assert points[0] == 0 and points[50] == 50 and points[100] == 100
    assert ind.position(37.5, points) == 37
    assert ind.position(-1, points) == 0
    assert ind.position(1000, points) == 100


def test_rolling_uses_exact_window():
    series = [(D(2026, 1, 1) + dt.timedelta(days=i), float(i + 1)) for i in range(300)]
    dd = ind.drawdown_series(series)
    assert len(dd) == 300 - ind.DD_WINDOW + 1
    assert all(v == 0.0 for _, v in dd)  # 계속 오르면 하락률 0


# ---- 과거 하락표 (구조 설계 D-08) ----

def _monthly(values):
    out, y, m = [], 2000, 1
    for v in values:
        out.append((D(y, m, 1), float(v)))
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    return out


def test_episodes_counted_once_until_new_high():
    # 100 → 85(−15%) → 75(−25%) → 60(−40%) → 다시 100 위로 → 88(−12%)
    values = [100] * 12 + [85, 75, 60, 70, 90, 101] + [101] * 11 + [88] + [95] * 40
    eps = hist.episodes(_monthly(values))
    assert eps["dd10"] == [12, 29]
    assert eps["dd20"] == [13]
    assert eps["dd30"] == [14]


def test_band_stats_forward_returns():
    values = [100] * 12 + [80] + [88] * 11 + [96] + [100] * 30
    monthly = _monthly(values)
    stats = {b.band: b for b in hist.band_stats(monthly)}
    dd20 = stats["dd20"]
    assert dd20.n == 1
    assert dd20.stats["1y_med"] == pytest.approx(96 / 80 - 1)  # 12개월 뒤
    assert dd20.stats["3y_med"] == pytest.approx(100 / 80 - 1)
    assert dd20.stats["1y_loss"] == 0
    assert stats["dd30"].n == 0 and stats["dd30"].stats["1y_min"] is None


def test_current_band():
    assert hist.current_band(-0.05) == "none"
    assert hist.current_band(-0.14) == "dd10"
    assert hist.current_band(-0.31) == "dd30"

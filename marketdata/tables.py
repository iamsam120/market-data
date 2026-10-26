"""월간 기준표 만들기: 10년 백분위 경계값, 과거 하락표, 검산값."""
import csv
import datetime as dt
import io
from dataclasses import dataclass

from marketdata import hist, indicators as ind
from marketdata.series import Series, monthly_average

PCT_HEADER = ["key", "as_of", "n"] + [f"p{k}" for k in range(101)]
HIST_HEADER = ["index", "band", "n", "1y_min", "1y_med", "1y_max", "1y_loss",
               "3y_min", "3y_med", "3y_max", "3y_loss", "since"]
CHECK_HEADER = ["key", "date", "value"]
WARMUP = max(ind.DD_WINDOW, ind.RSI_WINDOW, ind.MA_WINDOW)


@dataclass
class Tables:
    pct10y: list[list]
    hist: list[list]
    check: list[list]


def _recent(series: Series) -> Series:
    """10년 분포 + 준비 구간만 계산한다 (오래된 값은 쓰지 않음)."""
    return series[-(ind.TEN_YEARS + WARMUP):]


def _pct_row(key: str, values: Series) -> list:
    tail = ind.last_ten_years(values)
    points = ind.breakpoints([v for _, v in tail])
    return [key, tail[-1][0].isoformat(), len(tail)] + [round(p, 6) for p in points]


def _fmt(x):
    return "" if x is None else (round(x, 6) if isinstance(x, float) else x)


def build(vix: Series, spx_daily: Series, ndx_daily: Series, spx_monthly: Series) -> Tables:
    spx, ndx = _recent(spx_daily), _recent(ndx_daily)
    derived = {
        "dd_spx": ind.drawdown_series(spx), "dd_ndx": ind.drawdown_series(ndx),
        "rsi14_spx": ind.rsi_series(spx), "rsi14_ndx": ind.rsi_series(ndx),
    }
    pct = [_pct_row("vix", vix)] + [_pct_row(k, derived[k]) for k in ("dd_spx", "dd_ndx", "rsi14_spx", "rsi14_ndx")]

    hist_rows = []
    for name, monthly in (("spx", spx_monthly), ("ndx", monthly_average(ndx_daily))):
        for b in hist.band_stats(monthly):
            s = b.stats
            hist_rows.append([name, b.band, b.n] + [_fmt(s[k]) for k in HIST_HEADER[3:11]] + [monthly[0][0].isoformat()])

    check = []
    for name, series in (("spx", spx), ("ndx", ndx)):
        closes = [v for _, v in series]
        day = series[-1][0].isoformat()
        check += [[f"dd_{name}", day, round(ind.drawdown(closes), 6)],
                  [f"ma200_{name}", day, round(ind.ma_ratio(closes), 6)],
                  [f"rsi14_{name}", day, round(ind.rsi_wilder(closes), 4)]]
    return Tables(pct, hist_rows, check)


def to_csv(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()

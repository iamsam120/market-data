"""출처별 CSV를 (날짜, 값) 목록으로 읽는다."""
import csv
import datetime as dt
import io

Series = list[tuple[dt.date, float]]


def _rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))


def _require(rows: list[dict[str, str]], columns: list[str], name: str) -> None:
    if not rows:
        raise ValueError(f"{name}: 빈 파일")
    missing = [c for c in columns if c not in rows[0]]
    if missing:
        raise ValueError(f"{name}: 열 없음 {missing} (있는 열: {list(rows[0])})")


def parse_fred(text: str, column: str) -> Series:
    """FRED fredgraph.csv: observation_date,<시리즈>. 휴장일은 빈칸이라 뺀다."""
    rows = _rows(text)
    _require(rows, ["observation_date", column], "FRED")
    return [
        (dt.date.fromisoformat(r["observation_date"]), float(r[column]))
        for r in rows
        if r[column] not in ("", ".")
    ]


def parse_cboe_vix(text: str) -> Series:
    """CBOE VIX_History.csv: DATE(MM/DD/YYYY),OPEN,HIGH,LOW,CLOSE."""
    rows = _rows(text)
    _require(rows, ["DATE", "CLOSE"], "CBOE")
    return [(dt.datetime.strptime(r["DATE"], "%m/%d/%Y").date(), float(r["CLOSE"])) for r in rows]


def parse_whit3rabbit(text: str) -> Series:
    """whit3rabbit/fear-greed-data fear-greed.csv: Date,Fear Greed,Rating."""
    rows = _rows(text)
    _require(rows, ["Date", "Fear Greed"], "whit3rabbit")
    return dedupe([(dt.date.fromisoformat(r["Date"]), float(r["Fear Greed"])) for r in rows])


def parse_own_fear_greed(text: str) -> Series:
    """이 저장소 data/fear_greed.csv: date,score,rating."""
    rows = _rows(text)
    _require(rows, ["date", "score"], "fear_greed.csv")
    return [(dt.date.fromisoformat(r["date"]), float(r["score"])) for r in rows]


def parse_datasets_sp500(text: str) -> Series:
    """datasets/s-and-p-500 data/data.csv: Date(매달 1일),SP500(월평균) ... (Shiller 기반)."""
    rows = _rows(text)
    _require(rows, ["Date", "SP500"], "datasets/s-and-p-500")
    return [(dt.date.fromisoformat(r["Date"]), float(r["SP500"])) for r in rows if r["SP500"]]


def dedupe(series: Series) -> Series:
    """같은 날짜가 여러 번 있으면 마지막 값을 쓴다 (whit3rabbit의 일부 파일처럼)."""
    by_date: dict[dt.date, float] = {}
    for day, value in series:
        by_date[day] = value
    return sorted(by_date.items())


def monthly_average(daily: Series) -> Series:
    """일별 종가 → 달마다 평균 (날짜는 그달 1일). Shiller의 월간 S&P500과 같은 방식."""
    sums: dict[dt.date, list[float]] = {}
    for day, value in daily:
        sums.setdefault(day.replace(day=1), []).append(value)
    return sorted((month, sum(v) / len(v)) for month, v in sums.items())


def to_csv(series: Series, header: tuple[str, str]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows((d.isoformat(), f"{v:.6f}".rstrip("0").rstrip(".")) for d, v in series)
    return out.getvalue()

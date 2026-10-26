"""CNN Fear & Greed 예비 수집 (1순위는 whit3rabbit/fear-greed-data).

Apps Script로는 CNN이 418을 돌려줘 받을 수 없다. 브라우저 헤더를 넣은 HTTP 요청으로 받는다.
날짜: CNN 이력의 점은 그날 0시(UTC)와 그날 마감 시각에 찍힌다. 그래서 UTC 날짜를 그대로 쓴다.
미국 거래일만 남기고, 아직 장이 끝나지 않은 날(21:00 UTC 전)의 값은 장중 값이라 남기지 않는다.
"""
import csv
import datetime as dt
import io
import json
import pathlib

from marketdata.calendar import is_trading_day
from marketdata.fetch import BROWSER_HEADERS, Fetch

URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
HEADERS = {**BROWSER_HEADERS, "Referer": "https://www.cnn.com/"}
FIELDS = ["date", "score", "rating"]


CLOSE_UTC = dt.time(21, 0)  # 미국 장 마감 뒤 (EST 16:00 = 21:00 UTC, EDT는 20:00 UTC)


def parse(text: str) -> list[dict[str, str]]:
    """CNN JSON → 거래일마다 한 줄. 1년치 이력과 현재 값을 합치고, 같은 날짜는 나중 시각의 값으로."""
    data = json.loads(text)
    points: dict[dt.date, tuple[dt.datetime, float, str]] = {}

    def add(when: dt.datetime, score: float, rating: str) -> None:
        day = when.date()
        if not is_trading_day(day):
            return
        if day not in points or when >= points[day][0]:
            points[day] = (when, score, rating)

    for point in data["fear_and_greed_historical"]["data"]:
        add(dt.datetime.fromtimestamp(point["x"] / 1000, dt.timezone.utc), float(point["y"]), point.get("rating", ""))
    current = data["fear_and_greed"]
    add(dt.datetime.fromisoformat(current["timestamp"]).astimezone(dt.timezone.utc), float(current["score"]),
        current.get("rating", ""))
    rows = []
    for day, (when, score, rating) in sorted(points.items()):
        final = when.time() >= CLOSE_UTC or day < max(points)  # 마지막 날은 마감 뒤 값만
        if final:
            rows.append({"date": day.isoformat(), "score": f"{score:.4f}", "rating": rating})
    return rows


def fetch_rows(fetch: Fetch) -> list[dict[str, str]]:
    return parse(fetch(URL, HEADERS))


def merge(path: pathlib.Path, new_rows: list[dict[str, str]]) -> int:
    """파일에 없는 날짜만 더한다. 이미 있는 날짜는 건너뛴다 (하루 2번 실행해도 한 줄). 더한 줄 수를 돌려준다."""
    existing: dict[str, dict[str, str]] = {}
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            existing = {row["date"]: row for row in csv.DictReader(f)}
    added = 0
    for row in new_rows:
        if row["date"] not in existing:
            existing[row["date"]] = row
            added += 1
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(existing[d] for d in sorted(existing))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(out.getvalue(), encoding="utf-8")
    return added

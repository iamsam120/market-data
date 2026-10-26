"""출처 순위와 고르기 (README 출처 순위, 잔잔한복리 구조 설계 D-19).

실행할 때마다 순위대로 받아 보고, 멈췄거나 값 검사에 걸리면 다음 순위로 간다.
1순위가 회복되면 다음 실행에서 저절로 돌아온다. 무엇을 썼는지는 보고서(data/status/*.json)에 남는다.
"""
import datetime as dt
import pathlib
from dataclasses import dataclass, field
from typing import Callable

from marketdata import series as S
from marketdata.fetch import Fetch
from marketdata.validate import FEAR_GREED, INDEX, INDEX_MONTHLY, VIX, Rules, agree, is_fresh, problems

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAST_GOOD = ROOT / "data" / "sources"
OWN_FEAR_GREED_FILE = ROOT / "data" / "fear_greed.csv"

FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
CBOE_VIX = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
WHIT3RABBIT = "https://raw.githubusercontent.com/whit3rabbit/fear-greed-data/main/fear-greed.csv"
DATASETS_SP500 = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
OWN_FEAR_GREED = "https://raw.githubusercontent.com/iamsam120/market-data/main/data/fear_greed.csv"


@dataclass(frozen=True)
class Source:
    id: str
    url: str
    load: Callable[[Fetch], S.Series]
    kind: str  # daily / monthly
    lag: int  # daily: 거래일, monthly: 달


@dataclass(frozen=True)
class Dataset:
    name: str
    sources: list[Source]
    rules: Rules
    tolerance: float  # 두 출처가 모두 최신일 때 겹치는 날의 허용 차이
    relative: bool


@dataclass
class Choice:
    name: str
    used: str | None
    series: S.Series
    report: list[dict] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.used is not None


def choose(dataset: Dataset, fetch: Fetch, today: dt.date, previous_rows: dict[str, int] | None = None) -> Choice:
    """순위대로 받아 첫 번째로 통과한 출처를 쓴다. 뒤 순위도 받아 두어 값 비교와 보고에 쓴다."""
    previous_rows = previous_rows or {}
    choice = Choice(dataset.name, None, [])
    passed: list[tuple[Source, S.Series]] = []
    for rank, source in enumerate(dataset.sources, start=1):
        entry: dict = {"rank": rank, "id": source.id, "url": source.url}
        try:
            data = source.load(fetch)
        except Exception as error:  # 받기·읽기 실패도 그 출처의 실패로 본다
            # 공개 저장소에 올라가는 보고서라 실행한 컴퓨터의 경로는 지운다
            message = str(error).replace(str(ROOT), "").replace(str(ROOT).replace("\\", "\\\\"), "")
            entry.update(fresh=False, problems=[f"받기·읽기 실패: {message}"])
            choice.report.append(entry)
            continue
        fresh, latest, expected = is_fresh(data, source.kind, today, source.lag)
        found = problems(data, dataset.rules, previous_rows.get(source.id))
        if not fresh:
            found.insert(0, f"멈춤: 최신 {latest} < 기대 {expected}")
        entry.update(rows=len(data), latest=latest.isoformat() if latest else None,
                     expected=expected.isoformat(), fresh=fresh, problems=found)
        choice.report.append(entry)
        if not found:
            passed.append((source, data))
    if not passed:
        choice.alerts.append(f"{dataset.name}: 모든 출처 실패")
        return choice
    first, data = passed[0]
    choice.used, choice.series = first.id, data
    if first is not dataset.sources[0]:
        choice.alerts.append(f"{dataset.name}: 1순위 실패로 {first.id} 사용")
    if len(passed) > 1:
        same, worst = agree(passed[0][1], passed[1][1], dataset.tolerance, dataset.relative)
        if not same:
            choice.alerts.append(f"{dataset.name}: {passed[0][0].id}와 {passed[1][0].id}의 값이 다름 (최대 차이 {worst:.4f})")
    return choice


# ---- 출처 정의 ----

def _fred(series_id: str) -> Callable[[Fetch], S.Series]:
    return lambda fetch: S.parse_fred(fetch(FRED.format(series_id), None), series_id)


def _sp500_last_good_plus_fred(fetch: Fetch) -> S.Series:
    """2순위: 마지막 정상 사본 + 그 뒤 달은 FRED S&P500 일별 종가의 월평균으로 이어 붙인다."""
    copy = LAST_GOOD / "sp500_monthly.csv"
    base = S.parse_datasets_sp500(copy.read_text(encoding="utf-8"))
    daily = S.parse_fred(fetch(FRED.format("SP500"), None), "SP500")
    extra = [(m, v) for m, v in S.monthly_average(daily) if m > base[-1][0]]
    return base + extra


FEAR_GREED_SOURCES = Dataset(
    "fear_greed",
    [
        Source("whit3rabbit", WHIT3RABBIT, lambda f: S.parse_whit3rabbit(f(WHIT3RABBIT, None)), "daily", 2),
        # 예비 수집은 이 저장소의 파일을 바로 읽는다 (Actions에서는 방금 갱신한 파일)
        Source("own", OWN_FEAR_GREED, lambda f: S.parse_own_fear_greed(OWN_FEAR_GREED_FILE.read_text(encoding="utf-8")),
               "daily", 2),
    ],
    FEAR_GREED, tolerance=1.0, relative=False,
)

VIX_SOURCES = Dataset(
    "vix",
    [
        Source("cboe", CBOE_VIX, lambda f: S.parse_cboe_vix(f(CBOE_VIX, None)), "daily", 5),
        Source("fred_vixcls", FRED.format("VIXCLS"), _fred("VIXCLS"), "daily", 5),
    ],
    VIX, tolerance=0.02, relative=True,
)

SPX_DAILY_SOURCES = Dataset(
    "spx_daily", [Source("fred_sp500", FRED.format("SP500"), _fred("SP500"), "daily", 5)],
    INDEX, tolerance=0.005, relative=True,
)

NDX_DAILY_SOURCES = Dataset(
    "ndx_daily", [Source("fred_nasdaq100", FRED.format("NASDAQ100"), _fred("NASDAQ100"), "daily", 5)],
    INDEX, tolerance=0.005, relative=True,
)

SPX_MONTHLY_SOURCES = Dataset(
    "spx_monthly",
    [
        Source("datasets_sp500", DATASETS_SP500, lambda f: S.parse_datasets_sp500(f(DATASETS_SP500, None)),
               "monthly", 2),
        Source("last_good+fred", "data/sources/sp500_monthly.csv + FRED SP500", _sp500_last_good_plus_fred, "monthly", 2),
    ],
    INDEX_MONTHLY, tolerance=0.005, relative=True,
)

MONTHLY_DATASETS = [VIX_SOURCES, SPX_DAILY_SOURCES, NDX_DAILY_SOURCES, SPX_MONTHLY_SOURCES]

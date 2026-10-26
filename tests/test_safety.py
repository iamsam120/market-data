"""출처 안전장치: 1순위가 멈추거나 이상하면 2순위로 넘어가고 알림이 나간다 (구조 설계 D-19)."""
import datetime as dt
import json

from conftest import FakeWeb, cboe_csv, fred_csv, monthly_csv, trading_days, whit3rabbit_csv
from marketdata import cli, cnn, sources

TODAY = dt.date(2026, 10, 26)
DAYS = trading_days(dt.date(2026, 10, 23), 2700)


MONTHLY_START = 50 / 1.005 ** 299  # 월간 자료의 마지막 값이 FRED 일별(50)과 이어지게


def _pages(**override):
    pages = {
        sources.CBOE_VIX: cboe_csv(DAYS),
        sources.FRED.format("VIXCLS"): fred_csv("VIXCLS", DAYS, start=20, step=0),
        sources.FRED.format("SP500"): fred_csv("SP500", DAYS, start=50, step=0),
        sources.FRED.format("NASDAQ100"): fred_csv("NASDAQ100", DAYS),
        sources.DATASETS_SP500: monthly_csv(dt.date(2026, 9, 1), start=MONTHLY_START),
        sources.WHIT3RABBIT: whit3rabbit_csv(DAYS[-300:]),
    }
    pages.update(override)
    return pages


# ---- 고르기 ----

def test_primary_used_when_healthy():
    web = FakeWeb(_pages())
    choice = sources.choose(sources.VIX_SOURCES, web, TODAY)
    assert (choice.used, choice.alerts) == ("cboe", [])


def test_stale_primary_falls_back_with_alert():
    old = trading_days(dt.date(2026, 9, 23), 2700)  # datasets/finance-vix처럼 9/23에 멈춤
    web = FakeWeb(_pages(**{sources.CBOE_VIX: cboe_csv(old)}))
    choice = sources.choose(sources.VIX_SOURCES, web, TODAY)
    assert choice.used == "fred_vixcls"
    assert any("1순위 실패로 fred_vixcls 사용" in a for a in choice.alerts)
    assert "멈춤" in choice.report[0]["problems"][0]


def test_out_of_range_and_fetch_error_fall_back():
    bad = cboe_csv(DAYS, value=500)
    assert sources.choose(sources.VIX_SOURCES, FakeWeb(_pages(**{sources.CBOE_VIX: bad})), TODAY).used == "fred_vixcls"
    assert sources.choose(sources.VIX_SOURCES, FakeWeb(_pages(**{sources.CBOE_VIX: None})), TODAY).used == "fred_vixcls"


def test_truncated_file_falls_back():
    web = FakeWeb(_pages())
    choice = sources.choose(sources.VIX_SOURCES, web, TODAY, previous_rows={"cboe": 99_999})
    assert choice.used == "fred_vixcls"
    assert "행 수가 줄었음" in choice.report[0]["problems"][0]


def test_all_sources_fail():
    web = FakeWeb(_pages(**{sources.CBOE_VIX: None, sources.FRED.format("VIXCLS"): None}))
    choice = sources.choose(sources.VIX_SOURCES, web, TODAY)
    assert not choice.ok and choice.alerts == ["vix: 모든 출처 실패"]


def test_mismatch_alert_keeps_primary():
    web = FakeWeb(_pages(**{sources.FRED.format("VIXCLS"): fred_csv("VIXCLS", DAYS, start=30, step=0)}))
    choice = sources.choose(sources.VIX_SOURCES, web, TODAY)
    assert choice.used == "cboe"
    assert any("값이 다름" in a for a in choice.alerts)


# ---- 월간 기준표 (cli) ----

def test_monthly_builds_tables_and_last_good_copy(isolated):
    web = FakeWeb(_pages())
    assert cli.run_monthly(web, TODAY) == []
    for name in ("pct10y.csv", "hist_drawdown.csv", "check.csv"):
        assert (isolated / name).exists()
    assert (isolated / "sources" / "sp500_monthly.csv").exists()
    state = json.loads((isolated / "sources.json").read_text(encoding="utf-8"))
    assert state["tables"]["month"] == "2026-10"
    assert state["tables"]["used"]["spx_monthly"] == "datasets_sp500"
    assert cli.run_monthly(web, TODAY) == []  # 같은 달이면 다시 만들지 않음
    pct = (isolated / "pct10y.csv").read_text(encoding="utf-8").splitlines()
    assert [row.split(",")[0] for row in pct[1:]] == ["vix", "dd_spx", "dd_ndx", "rsi14_spx", "rsi14_ndx"]


def test_monthly_falls_back_to_last_good_copy_plus_fred(isolated):
    cli.run_monthly(FakeWeb(_pages()), TODAY)  # 정상 사본을 남긴다
    broken = FakeWeb(_pages(**{sources.DATASETS_SP500: monthly_csv(dt.date(2026, 5, 1), start=MONTHLY_START)}))  # 1순위가 5월에 멈춤
    alerts = cli.run_monthly(broken, TODAY, force=True)
    assert any("1순위 실패로 last_good+fred 사용" in a for a in alerts)
    state = json.loads((isolated / "sources.json").read_text(encoding="utf-8"))
    assert state["tables"]["used"]["spx_monthly"] == "last_good+fred"
    again = cli.run_monthly(broken, TODAY, force=True)
    assert not any("1순위 실패로" in a for a in again)  # 같은 전환은 한 번만 알린다


def test_monthly_keeps_old_tables_when_everything_fails(isolated):
    cli.run_monthly(FakeWeb(_pages()), TODAY)
    before = (isolated / "pct10y.csv").read_text(encoding="utf-8")
    dead = FakeWeb(_pages(**{sources.FRED.format("SP500"): None}))
    alerts = cli.run_monthly(dead, TODAY, force=True)
    assert any("지난달 표 유지" in a for a in alerts)
    assert (isolated / "pct10y.csv").read_text(encoding="utf-8") == before


# ---- CNN ----

def _cnn_json(points, current):
    return json.dumps({"fear_and_greed": current,
                       "fear_and_greed_historical": {"data": points}})


def _ms(text):
    return dt.datetime.fromisoformat(text).timestamp() * 1000


def test_cnn_parse_keeps_trading_day_closes_only():
    points = [
        {"x": _ms("2026-10-22T00:00:00+00:00"), "y": 19.0, "rating": "extreme fear"},
        {"x": _ms("2026-10-22T23:59:00+00:00"), "y": 19.44, "rating": "extreme fear"},  # 같은 날 나중 값
        {"x": _ms("2026-10-24T12:00:00+00:00"), "y": 25.0, "rating": "fear"},  # 토요일 → 뺌
    ]
    current = {"score": 21.0, "rating": "extreme fear", "timestamp": "2026-10-26T13:00:00+00:00"}  # 월요일 장중 → 뺌
    rows = cnn.parse(_cnn_json(points, current))
    assert rows == [{"date": "2026-10-22", "score": "19.4400", "rating": "extreme fear"}]


def test_cnn_merge_is_idempotent(tmp_path):
    path = tmp_path / "fear_greed.csv"
    rows = [{"date": "2026-10-22", "score": "19.4400", "rating": "extreme fear"}]
    assert cnn.merge(path, rows) == 1
    assert cnn.merge(path, rows) == 0
    assert path.read_text(encoding="utf-8").count("2026-10-22") == 1


def test_run_cnn_alerts_only_when_switching(isolated):
    own_rows = [{"date": d.isoformat(), "score": "30.0", "rating": "fear"} for d in DAYS[-300:]]
    cnn.merge(isolated / "fear_greed.csv", own_rows)
    cnn_page = _cnn_json([], {"score": 30.0, "rating": "fear", "timestamp": "2026-10-23T23:59:00+00:00"})
    healthy = FakeWeb(_pages(**{cnn.URL: cnn_page}))
    assert cli.run_cnn(healthy, TODAY) == []
    stale = FakeWeb(_pages(**{cnn.URL: cnn_page, sources.WHIT3RABBIT: whit3rabbit_csv(DAYS[-300:-20])}))
    assert any("1순위 실패로 own 사용" in a for a in cli.run_cnn(stale, TODAY))
    assert cli.run_cnn(stale, TODAY) == []  # 계속 2순위면 다시 알리지 않음
    back = cli.run_cnn(healthy, TODAY)
    assert any("돌아옴" in a for a in back)


def test_upstream_check(isolated):
    now = dt.datetime(2026, 10, 26, tzinfo=dt.timezone.utc)
    api = {
        "https://api.github.com/repos/whit3rabbit/fear-greed-data": json.dumps(
            {"pushed_at": "2026-10-24T01:20:29Z", "archived": False}),
        "https://api.github.com/repos/datasets/s-and-p-500": json.dumps(
            {"pushed_at": "2026-08-01T04:56:34Z", "archived": False}),
    }
    alerts = cli.run_upstream(FakeWeb(api), now)
    assert alerts == ["datasets/s-and-p-500: 85일째 갱신 없음"]  # 8/1 04:56 → 10/26 00:00
    api["https://api.github.com/repos/whit3rabbit/fear-greed-data"] = json.dumps(
        {"pushed_at": "2026-10-24T01:20:29Z", "archived": True})
    assert any("보관" in a for a in cli.run_upstream(FakeWeb(api), now))

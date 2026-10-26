"""명령:
    python -m marketdata.cli cnn                 # 예비 CNN 수집 + 공포탐욕 출처 점검
    python -m marketdata.cli monthly [--force]   # 이번 달 기준표가 없으면 만든다
    python -m marketdata.cli upstream            # 1순위 저장소가 멈췄거나 보관됐는지 본다

알림이 필요한 일(2순위로 넘어감, 모든 출처 실패, 값이 다름, 1순위 저장소 멈춤)이 있으면 종료 코드 1을 돌려준다.
GitHub Actions는 실패한 실행을 저장소 주인에게 메일로 알린다. 실패해도 이미 만든 파일은 커밋한다(워크플로 참고).
"""
import argparse
import datetime as dt
import json
import pathlib
import sys

from marketdata import cnn, sources, tables
from marketdata.calendar import holidays_cover, kst_today
from marketdata.fetch import http_get

ROOT = sources.ROOT
DATA = ROOT / "data"
STATE = DATA / "sources.json"
# 1순위 저장소와 멈춤으로 볼 날수. 매일 갱신하는 곳은 14일, 매달 1일에 갱신하는 곳은 45일.
UPSTREAM_REPOS = {"whit3rabbit/fear-greed-data": 14, "datasets/s-and-p-500": 45}


def _fetch(url, headers=None):
    return http_get(url, headers)


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"datasets": {}}


def save_state(state: dict) -> None:
    state["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _previous_rows(state: dict, name: str) -> dict[str, int]:
    entry = state.get("datasets", {}).get(name, {})
    return {c["id"]: c["rows"] for c in entry.get("candidates", []) if c.get("rows")}


def _record(state: dict, choice: sources.Choice, today: dt.date) -> list[str]:
    """보고를 남기고 알림 목록을 돌려준다. 같은 출처를 계속 쓰는 동안에는 전환 알림을 다시 보내지 않는다."""
    before = state.get("datasets", {}).get(choice.name, {}).get("used")
    state.setdefault("datasets", {})[choice.name] = {
        "used": choice.used, "checked": today.isoformat(), "candidates": choice.report, "alerts": choice.alerts,
    }
    alerts = [a for a in choice.alerts if "1순위 실패로" not in a or choice.used != before]
    if choice.used and before and choice.used != before and not choice.alerts:
        alerts.append(f"{choice.name}: 1순위 {choice.used}로 돌아옴")
    return alerts


def run_cnn(fetch=_fetch, today: dt.date | None = None) -> list[str]:
    today = today or kst_today()
    alerts = []
    try:
        added = cnn.merge(sources.OWN_FEAR_GREED_FILE, cnn.fetch_rows(fetch))
        print(f"예비 CNN 수집: {added}줄 더함")
    except Exception as error:
        alerts.append(f"예비 CNN 수집 실패: {error}")
    state = load_state()
    choice = sources.choose(sources.FEAR_GREED_SOURCES, fetch, today, _previous_rows(state, "fear_greed"))
    alerts += _record(state, choice, today)
    save_state(state)
    return alerts


def run_monthly(fetch=_fetch, today: dt.date | None = None, force: bool = False) -> list[str]:
    today = today or kst_today()
    state = load_state()
    month = today.strftime("%Y-%m")
    if not force and state.get("tables", {}).get("month") == month:
        print(f"{month} 기준표가 이미 있음")
        return []
    alerts = [] if holidays_cover(today) else [f"휴장일 표에 {today.year}년이 없음 (marketdata/us_holidays.csv)"]
    chosen = {}
    for dataset in sources.MONTHLY_DATASETS:
        choice = sources.choose(dataset, fetch, today, _previous_rows(state, dataset.name))
        alerts += _record(state, choice, today)
        chosen[dataset.name] = choice
    failed = [name for name, c in chosen.items() if not c.ok]
    if failed:
        alerts.append(f"기준표를 만들지 않음 (지난달 표 유지): {', '.join(failed)}")
        save_state(state)
        return alerts
    built = tables.build(chosen["vix"].series, chosen["spx_daily"].series, chosen["ndx_daily"].series,
                         chosen["spx_monthly"].series)
    (DATA / "pct10y.csv").write_text(tables.to_csv(tables.PCT_HEADER, built.pct10y), encoding="utf-8")
    (DATA / "hist_drawdown.csv").write_text(tables.to_csv(tables.HIST_HEADER, built.hist), encoding="utf-8")
    (DATA / "check.csv").write_text(tables.to_csv(tables.CHECK_HEADER, built.check), encoding="utf-8")
    if chosen["spx_monthly"].used == "datasets_sp500":
        # 1순위가 검사를 통과했을 때만 마지막 정상 사본을 바꾼다
        sources.LAST_GOOD.mkdir(parents=True, exist_ok=True)
        (sources.LAST_GOOD / "sp500_monthly.csv").write_text(
            fetch(sources.DATASETS_SP500, None), encoding="utf-8")
    state["tables"] = {"month": month, "built": today.isoformat(),
                       "used": {name: c.used for name, c in chosen.items()}}
    save_state(state)
    print(f"{month} 기준표를 만듦: " + ", ".join(f"{n}={c.used}" for n, c in chosen.items()))
    return alerts


def run_upstream(fetch=_fetch, now: dt.datetime | None = None) -> list[str]:
    now = now or dt.datetime.now(dt.timezone.utc)
    state = load_state()
    alerts, report = [], {}
    for repo, stale_days in UPSTREAM_REPOS.items():
        try:
            info = json.loads(fetch(f"https://api.github.com/repos/{repo}", {"Accept": "application/vnd.github+json"}))
        except Exception as error:
            alerts.append(f"{repo}: 확인 실패 ({error})")
            continue
        pushed = dt.datetime.fromisoformat(info["pushed_at"].replace("Z", "+00:00"))
        days = (now - pushed).days
        report[repo] = {"pushed_at": info["pushed_at"], "archived": info.get("archived", False), "days": days}
        if info.get("archived"):
            alerts.append(f"{repo}: 보관(archived)됨 → 출처 순위를 바꿀 때")
        elif days > stale_days:
            alerts.append(f"{repo}: {days}일째 갱신 없음")
    state["upstream"] = {"checked": now.isoformat(timespec="seconds"), "repos": report}
    save_state(state)
    return alerts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="시장 데이터 수집·기준표")
    parser.add_argument("command", choices=["cnn", "monthly", "upstream"])
    parser.add_argument("--force", action="store_true", help="이번 달 기준표가 있어도 다시 만든다")
    args = parser.parse_args(argv)
    if args.command == "cnn":
        alerts = run_cnn()
    elif args.command == "monthly":
        alerts = run_monthly(force=args.force)
    else:
        alerts = run_upstream()
    for alert in alerts:
        print(f"알림: {alert}")
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())

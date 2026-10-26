# market-data

공개 시장 데이터를 확인하고 정리해 CSV로 남기는 저장소입니다. 구글 시트가 로그인 없이 읽을 수 있도록 공개로 둡니다.

원 출처와 다른 분들이 운영하는 공개 저장소를 먼저 쓰고, 이 저장소의 수집은 예비로 둡니다. 출처마다 최신 날짜와 값을 검사해, 멈췄거나 값이 이상하면 다음 순위로 자동으로 넘어갑니다.

## 출처 순위
| 데이터 | 1순위 | 2순위 |
|---|---|---|
| CNN Fear & Greed (일별) | [whit3rabbit/fear-greed-data](https://github.com/whit3rabbit/fear-greed-data) | 이 저장소의 예비 수집 (`data/fear_greed.csv`) |
| S&P500 월간 장기 | [datasets/s-and-p-500](https://github.com/datasets/s-and-p-500) | 이 저장소의 마지막 정상 사본 + FRED 일별 종가 월평균 |
| VIX 일별 | [CBOE](https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv) | [FRED VIXCLS](https://fred.stlouisfed.org/series/VIXCLS) |
| S&P500·나스닥100 일별 | [FRED SP500](https://fred.stlouisfed.org/series/SP500)·[NASDAQ100](https://fred.stlouisfed.org/series/NASDAQ100) | — |

## 파일 (만드는 중)
| 파일 | 내용 | 갱신 |
|---|---|---|
| `data/fear_greed.csv` | CNN Fear & Greed 예비 수집 (날짜, 점수, 등급) | 매일 한국 시각 07:00·10:00 |
| `data/pct10y.csv` | VIX·지수 하락률·RSI의 최근 10년 분포 백분위 경계값 | 매월 첫 거래일 |
| `data/hist_drawdown.csv` | 고점 대비 −10%·−20%·−30%에 들었던 과거 사례와 그 뒤 1년·3년 가격 수익률 요약 | 매월 |
| `data/check.csv` | 같은 날짜의 하락률·200일선·RSI 검산값 | 매월 |
| `data/status/*.json` | 이번에 쓴 출처, 출처별 최신 날짜와 검사 결과 (`fear_greed`, `monthly`, `upstream`) | 실행마다 |
| `data/sources/` | 검사를 통과한 월간 원자료의 마지막 정상 사본 | 매월 |

## 알림
- 데이터는 출처의 값을 그대로 옮기거나 계산한 것이며, 정확성과 연속성을 보장하지 않습니다.
- 투자 권유나 조언이 아닙니다. 과거 수치는 앞으로의 결과를 뜻하지 않습니다.
- 개인 정보는 담지 않습니다.
- 출처 저장소를 만들고 운영하시는 분들께 감사드립니다.

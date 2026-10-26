# market-data

공개 시장 데이터를 정해진 시각에 받아 CSV로 남기는 저장소입니다. 구글 시트가 로그인 없이 읽을 수 있도록 공개로 둡니다.

## 파일 (만드는 중)
| 파일 | 내용 | 갱신 |
|---|---|---|
| `data/fear_greed.csv` | CNN Fear & Greed Index 일별 값 (날짜, 점수, 등급) | 매일 한국 시각 07:00·10:00 |
| `data/pct10y.csv` | VIX·S&P500·나스닥100 지표의 최근 10년 분포 백분위 경계값 | 매월 첫 거래일 |
| `data/hist_drawdown.csv` | 지수가 고점 대비 −10%·−20%·−30%에 들었던 과거 사례와 그 뒤 1년·3년 가격 수익률 요약 | 매월 첫 거래일 |
| `data/check.csv` | 같은 날짜의 하락률·200일선·RSI 검산값 | 매월 |

## 출처
- CNN Fear & Greed Index: https://www.cnn.com/markets/fear-and-greed
- CBOE VIX 이력: https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv
- FRED (S&P500, 나스닥100): https://fred.stlouisfed.org/
- Robert Shiller 데이터 (S&P500 월간): https://shillerdata.com/

## 알림
- 데이터는 출처의 값을 그대로 옮기거나 계산한 것이며, 정확성과 연속성을 보장하지 않습니다.
- 투자 권유나 조언이 아닙니다. 과거 수치는 앞으로의 결과를 뜻하지 않습니다.
- 개인 정보는 담지 않습니다.

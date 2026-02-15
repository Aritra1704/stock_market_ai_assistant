# stock_market_ai_assistant

FastAPI-based paper-trading backend using yfinance intraday OHLCV data.

The architecture separates:
- Data ingestion (`integrations/market_data`)
- Strategy + signals (`strategies`, `services/signal_service.py`)
- Risk controls (`services/risk_service.py`)
- Execution adapter (`integrations/brokers/paper.py`)
- Journaling/audit trail (`services/journal_service.py`)

## Features

- `GET /api/trend` for trend + indicators (SMA20, EMA20, RSI14, ATR14)
- `POST /api/watchlist` to create daily watchlists
- `POST /api/run` to execute intraday paper-trading workflow
- Daily INR 100 budget enforcement in paper mode
- DB logs for watchlist snapshots, market snapshots, trade plans, and transactions
- Swagger docs at `/docs`

## Run Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn src.app:app --reload --port 8003
```

Open:
- App docs: `http://127.0.0.1:8003/docs`
- Health: `http://127.0.0.1:8003/api/health`

## Example API Calls

### 1) Trend analysis

```bash
curl "http://127.0.0.1:8003/api/trend?symbol=RELIANCE.NS&interval=5m&period=5d"
```

### 2) Add watchlist

```bash
curl -X POST "http://127.0.0.1:8003/api/watchlist" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["RELIANCE.NS", "TCS.NS"],
    "reason": "manual"
  }'
```

### 3) Run strategy for daily watchlist

```bash
curl -X POST "http://127.0.0.1:8003/api/run" \
  -H "Content-Type: application/json" \
  -d '{
    "interval": "5m",
    "period": "5d"
  }'
```

## Notes

- yfinance intraday data availability depends on Yahoo limits/market hours.
- This project is paper-trading only.
- No API key is required for yfinance.

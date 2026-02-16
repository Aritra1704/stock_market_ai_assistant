# stock_market_ai_assistant

Broker-agnostic FastAPI trading lab with two paper-trading modes:
- `INTRADAY` (5m candles, daily budget INR 100)
- `SWING` (1d candles, allocation INR 1000, simulated GTT workflow)

This project is deterministic and rules-based. It does not predict markets.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn src.app:app --reload --port 8003
```

Open Swagger docs:
- `http://127.0.0.1:8003/docs`

## Main APIs

- `GET /api/health`
- `GET /api/trend` (intraday trend)
- `GET /api/swing/trend` (daily swing trend + readiness)
- `POST /api/watchlist` (supports mode `INTRADAY` or `SWING`)
- `POST /api/run` (supports mode `INTRADAY` or `SWING`)
- `GET /api/journal/swing/today`

## Example curl

### Intraday trend

```bash
curl "http://127.0.0.1:8003/api/trend?symbol=RELIANCE.NS&interval=5m&period=5d"
```

### Swing trend

```bash
curl "http://127.0.0.1:8003/api/swing/trend?symbol=TCS.NS&period=6mo&interval=1d"
```

### Add intraday watchlist

```bash
curl -X POST "http://127.0.0.1:8003/api/watchlist" \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["RELIANCE.NS", "TCS.NS"], "reason": "manual", "mode": "INTRADAY"}'
```

### Add swing watchlist

```bash
curl -X POST "http://127.0.0.1:8003/api/watchlist" \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["INFY.NS", "HDFCBANK.NS"], "reason": "manual", "mode": "SWING", "horizon_days": 20}'
```

### Run intraday

```bash
curl -X POST "http://127.0.0.1:8003/api/run" \
  -H "Content-Type: application/json" \
  -d '{"mode": "INTRADAY", "interval": "5m", "period": "5d"}'
```

### Run swing

```bash
curl -X POST "http://127.0.0.1:8003/api/run" \
  -H "Content-Type: application/json" \
  -d '{"mode": "SWING", "interval": "1d", "period": "6mo"}'
```

### Swing journal snapshot

```bash
curl "http://127.0.0.1:8003/api/journal/swing/today"
```

## PostgreSQL schema setup (non-public)

This app is configured to use a dedicated schema (default `stock_ai_lab`) and avoid writing to `public` or `prayana_sit`.

1. Ensure `.env` has:
```env
DATABASE_URL=postgresql+psycopg://postgres:<your_password>@localhost:5432/postgres
DB_SCHEMA=stock_ai_lab
```

2. Apply schema:
```bash
psql -h localhost -p 5432 -U postgres -d postgres -f schema.sql
```

3. Verify tables:
```sql
SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname = 'stock_ai_lab'
ORDER BY tablename;
```

## Paper GTT simulation assumptions

- `BUY_SETUP` creates `trade_plan` (`plan_type=GTT`) + pending BUY GTT.
- BUY GTT triggers when latest daily `high >= trigger_price`.
- Fill price in simulation = `trigger_price`.
- On entry trigger, a SELL protective GTT is created at trailing stop.
- On each swing run:
  - pending GTT triggers are evaluated
  - trailing stop is updated
  - time stop / take-profit / trailing-stop exits can close the position
- Every action logs rationale + features so runs are replayable.

## Notes

- yfinance requires no API key.
- Swing actions are intended to run once daily.
- PostgreSQL is the default database in `.env.example`.
- For quick local-only testing, you can switch to SQLite:
  - `DATABASE_URL=sqlite:///./stock_market_ai_assistant.db`

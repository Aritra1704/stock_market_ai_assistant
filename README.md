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
uvicorn src.app:app --reload --port 8004
```

Open Swagger docs:
- `http://127.0.0.1:8004/docs`
- Dashboard UI: `http://127.0.0.1:8004/`

## Core runtime config

- `MAX_STOCKS_PER_MODE=10`
  - hard cap for `INTRADAY` and `SWING` watchlists and run processing.
  - increase later by changing `.env`.

## Main APIs

- `GET /api/health`
- `GET /api/trend` (intraday trend)
- `GET /api/swing/trend` (daily swing trend + readiness)
- `POST /api/watchlist` (supports mode `INTRADAY` or `SWING`)
- `POST /api/run` (supports mode `INTRADAY` or `SWING`)
- `POST /api/audit/top-stocks/generate` (build/store top-100 audit snapshot)
- `GET /api/audit/top-stocks/today` (read today's stored top-100 snapshot)
- `GET /api/journal/swing/today`

## Example curl

### Intraday trend

```bash
curl "http://127.0.0.1:8004/api/trend?symbol=RELIANCE.NS&interval=5m&period=5d"
```

### Swing trend

```bash
curl "http://127.0.0.1:8004/api/swing/trend?symbol=TCS.NS&period=6mo&interval=1d"
```

### Add intraday watchlist

```bash
curl -X POST "http://127.0.0.1:8004/api/watchlist" \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["RELIANCE.NS", "TCS.NS"], "reason": "manual", "mode": "INTRADAY"}'
```

### Add swing watchlist

```bash
curl -X POST "http://127.0.0.1:8004/api/watchlist" \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["INFY.NS", "HDFCBANK.NS"], "reason": "manual", "mode": "SWING", "horizon_days": 20}'
```

### Run intraday

```bash
curl -X POST "http://127.0.0.1:8004/api/run" \
  -H "Content-Type: application/json" \
  -d '{"mode": "INTRADAY", "interval": "5m", "period": "5d"}'
```

### Run swing

```bash
curl -X POST "http://127.0.0.1:8004/api/run" \
  -H "Content-Type: application/json" \
  -d '{"mode": "SWING", "interval": "1d", "period": "6mo"}'
```

### Generate today's top-100 audit snapshots (both modes)

```bash
curl -X POST "http://127.0.0.1:8004/api/audit/top-stocks/generate" \
  -H "Content-Type: application/json" \
  -d '{"mode":"BOTH","force_refresh":true}'
```

### Read today's top-100 audit snapshots

```bash
curl "http://127.0.0.1:8004/api/audit/top-stocks/today"
```

### Swing journal snapshot

```bash
curl "http://127.0.0.1:8004/api/journal/swing/today"
```

## Today's analysis workflow

1. Add up to 10 intraday symbols for today:
```bash
curl -X POST "http://127.0.0.1:8004/api/watchlist" \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["RELIANCE.NS","TCS.NS","INFY.NS"], "reason": "today-scan", "mode": "INTRADAY"}'
```

2. Add up to 10 swing symbols for today:
```bash
curl -X POST "http://127.0.0.1:8004/api/watchlist" \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["HDFCBANK.NS","ITC.NS","SBIN.NS"], "reason": "today-scan", "mode": "SWING", "horizon_days": 20}'
```

3. Run intraday analysis/execution for today:
```bash
curl -X POST "http://127.0.0.1:8004/api/run" \
  -H "Content-Type: application/json" \
  -d '{"mode":"INTRADAY","interval":"5m","period":"5d"}'
```

4. Run swing analysis/execution for today:
```bash
curl -X POST "http://127.0.0.1:8004/api/run" \
  -H "Content-Type: application/json" \
  -d '{"mode":"SWING","interval":"1d","period":"6mo"}'
```

5. Check swing decisions and executed entries:
```bash
curl "http://127.0.0.1:8004/api/journal/swing/today"
```

All decisions are logged in `trade_plan` (including `HOLD`/`NO_TRADE` as cancelled plans), and executions are logged in `transactions`.

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

## Railway deployment

1. Push repo to GitHub and deploy from Railway.
2. Set these Railway environment variables:
```env
APP_DEBUG=false
DATABASE_URL=${{Postgres.DATABASE_URL}}
DB_SCHEMA=stock_ai_lab
INTRADAY_DAILY_BUDGET_INR=100
INTRADAY_MAX_OPEN_POSITIONS=1
SWING_ALLOCATION_INR=1000
SWING_MAX_OPEN_POSITIONS=2
SWING_DEFAULT_HORIZON_DAYS=20
MAX_STOCKS_PER_MODE=10
AUDIT_TOP_STOCKS_LIMIT=100
AUDIT_RETENTION_DAYS=15
AUDIT_CLEANUP_INTERVAL_MINUTES=360
AUDIT_CLEANUP_SCHEDULER_ENABLED=true
```
3. Deploy.

Notes:
- Startup automatically runs DB initialization (`init_db()`), creates `DB_SCHEMA` if missing, and creates all tables.
- Startup also runs retention cleanup for `top_stock_audit` and schedules recurring cleanup.
- No manual table creation step is required on Railway.
- `DATABASE_URL` from Railway is normalized in app code to `postgresql+psycopg://...` automatically.

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

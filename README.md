# Stock Market AI Assistant

An AI assistant connected to your trading data that analyzes stocks using real market data and reliable numerical computation.

## What You Build

You build an assistant that:
- Reads your holdings, positions, orders, and watchlists from broker APIs (starting with Zerodha).
- Pulls live and historical market data.
- Runs real calculations (returns, risk, exposure, trend stats) in Python/Pandas.
- Uses an LLM for explanation, insight synthesis, and Q&A over computed results.

## What You Learn

- How LLMs handle numerical tasks and where they fail.
- Why language reasoning should not directly replace deterministic math.
- How to combine AI reasoning with a computation engine for trustworthy outputs.

## Tech Stack

- Python
- Zerodha API (Kite Connect)
- Pandas (plus NumPy)
- MCP (Model Context Protocol) tools
- LLM
- FastAPI + Jinja2 web UI
- Mobile notification adapters (FCM/APNs + mock provider)

## Initial Draft (Now Implemented)

The repository now includes a runnable starter application with:
- Backend API (`FastAPI`) for portfolio, stock analysis, chat, and notifications.
- Web UI dashboard (`/`) for interacting with all core flows.
- Notification service for mobile apps:
  - Device registration endpoint
  - Notification send endpoint
  - Provider abstraction for Android (`FCM`) and iOS (`APNs`) with mock fallback

### Quickstart

1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. Create env file:
   ```bash
   cp .env.example .env
   ```
4. Run server:
   ```bash
   uvicorn src.app:app --host 127.0.0.1 --port 8000 --reload --reload-dir src --reload-exclude .venv
   ```
5. Open:
   - Web UI: `http://127.0.0.1:8000/`
   - API docs: `http://127.0.0.1:8000/docs`

### API Endpoints

- `GET /api/health`
- `GET /api/portfolio/summary`
- `GET /api/stocks/{symbol}/analysis`
- `POST /api/chat`
- `POST /api/notifications/register`
- `POST /api/notifications/send`

### Railway Deployment

This repo is configured for Railway with:
- `railway.json` (build/start/healthcheck)
- `nixpacks.toml` (pins Python runtime)
- `Procfile` fallback start command

Steps:
1. Push this repository to GitHub.
2. In Railway, create a new project from the GitHub repo.
3. Set environment variables in Railway:
   - `APP_NAME=Stock Market AI Assistant`
   - `APP_DEBUG=false`
   - `APP_HOST=0.0.0.0`
   - `APP_PORT=8000` (optional; Railway provides `PORT`)
   - `ZERODHA_API_KEY=demo_key` (or real key)
   - `ZERODHA_ACCESS_TOKEN=demo_token` (or real token)
   - `NOTIFICATION_PROVIDER=mock`
   - `FCM_SERVER_KEY=` (optional)
   - `APNS_AUTH_TOKEN=` (optional)
4. Deploy. Railway runs:
   - `uvicorn src.app:app --host 0.0.0.0 --port $PORT`
5. Validate after deploy:
   - `/api/health`
   - `/` (web UI)

## Architecture Overview

The system follows a hybrid pattern:
- `LLM` handles intent detection, reasoning, and natural language responses.
- `Python services` handle data fetching, transformations, and all math.
- `MCP tools` are the bridge the LLM uses to request trusted computations.

```text
User
  |
  v
Chat Interface / Client
  |
  v
LLM Orchestrator
  |                           +---------------------------+
  | tool call (MCP)           |  Observability            |
  +--------------------------> |  Logs, metrics, tracing   |
  |                           +---------------------------+
  v
MCP Server (Tool Layer)
  |
  +--> Market Data Service (quotes, candles, depth)
  |
  +--> Portfolio Service (holdings, positions, P&L)
  |
  +--> Analytics Engine (Pandas/NumPy calculations)
  |
  +--> Signal/Screening Engine (rules, factors, filters)
  |
  +--> Risk Engine (exposure, drawdown, VaR-lite, alerts)
  |
  +--> Cache/Store (Redis/Postgres/Parquet)
  |
  +--> Broker Adapter (Zerodha API now, extensible later)
```

## Core Components

### 1. LLM Orchestrator

Responsibilities:
- Understand user intent (`portfolio summary`, `stock analysis`, `what-if`, `risk check`).
- Select the right MCP tools.
- Ask follow-up questions when input is ambiguous.
- Generate final response using tool outputs only for numbers.

Design rules:
- Never let the LLM invent financial metrics.
- Every numeric claim must be backed by tool output.
- Surface assumptions in the response.

### 2. MCP Tool Layer

Expose explicit tools with strict schemas:
- `get_portfolio_snapshot()`
- `get_stock_quote(symbol)`
- `get_historical_candles(symbol, interval, from, to)`
- `compute_returns(series, window)`
- `compute_volatility(series, window)`
- `portfolio_exposure_by_sector()`
- `risk_summary(confidence, horizon)`
- `run_screen(criteria)`

Why MCP:
- Deterministic execution.
- Clear I/O contracts.
- Easy extension and testability.

### 3. Broker Adapter (Zerodha)

Responsibilities:
- Authentication (API key, access token lifecycle).
- Data normalization into internal schemas.
- Rate-limit handling and retries.
- Mapping broker-specific fields to canonical models.

### 4. Market Data Service

Responsibilities:
- Fetch live quotes and OHLCV candles.
- Validate time ranges and trading-session boundaries.
- Handle missing candles and corporate-action adjustments if used.

### 5. Portfolio Service

Responsibilities:
- Pull holdings, positions, and orders.
- Build unified portfolio state.
- Compute realized/unrealized P&L baselines.

### 6. Analytics Engine

Responsibilities:
- Time-series indicators and return calculations.
- Rolling statistics (volatility, drawdown, Sharpe-like metrics).
- Portfolio-level aggregation and attribution.

Implementation note:
- Use Pandas/NumPy for all computations.
- Keep functions pure and unit-testable.

### 7. Risk Engine

Responsibilities:
- Exposure by symbol/sector/theme.
- Concentration risk.
- Drawdown and volatility thresholds.
- Scenario what-if checks (e.g., `-3% market move`).

### 8. Cache and Persistence

Recommended:
- `Redis` for short-lived quote/cache data.
- `Postgres` (or Parquet) for snapshots, analytics results, and audit trails.

## End-to-End Request Flow

Example prompt: "Should I add more TCS based on my current portfolio risk?"

1. LLM parses intent: stock decision + portfolio risk context.
2. LLM calls `get_portfolio_snapshot()` via MCP.
3. LLM calls `get_stock_quote("TCS")` and optional historical data tools.
4. Analytics/Risk engines compute concentration and scenario impact.
5. Tool layer returns structured JSON results.
6. LLM generates explanation with:
   - Current risk state
   - Impact of adding TCS
   - Trade-offs and caveats
7. Response includes computed numbers and timestamp of data.

## Data Contracts (Canonical Models)

Define stable internal models:

- `Instrument`
  - `symbol`, `exchange`, `sector`, `lot_size`
- `Holding`
  - `symbol`, `qty`, `avg_price`, `ltp`, `market_value`, `pnl`
- `Position`
  - `symbol`, `product`, `qty`, `avg_price`, `mtm`
- `Candle`
  - `timestamp`, `open`, `high`, `low`, `close`, `volume`
- `RiskSnapshot`
  - `gross_exposure`, `net_exposure`, `top_5_concentration`, `portfolio_vol`

Keep broker-specific fields outside these canonical models.

## Reliability Rules

- Numerical truth comes from tools, never free-form LLM math.
- Every tool call is logged with input/output hash.
- Responses include "data as of" timestamp.
- Add fallback messaging when market/broker APIs fail.
- Cache aggressively but annotate staleness.

## Security and Compliance Basics

- Store credentials in environment variables or secret manager.
- Never log API tokens or personally identifiable data.
- Use read-only mode where possible for analysis use cases.
- Keep an audit log of tool calls and user-facing recommendations.
- Add clear disclaimer: educational support, not investment advice.

## Suggested Project Structure

```text
stock_market_ai_assistant/
  README.md
  src/
    app.py
    config.py
    orchestrator/
      agent.py
      prompts.py
      policies.py
    mcp_server/
      server.py
      schemas.py
      tools/
        portfolio_tools.py
        market_tools.py
        analytics_tools.py
        risk_tools.py
        screening_tools.py
    integrations/
      zerodha_client.py
      market_data_client.py
    services/
      portfolio_service.py
      market_service.py
      analytics_service.py
      risk_service.py
    models/
      instrument.py
      holding.py
      position.py
      candle.py
      risk_snapshot.py
    storage/
      cache.py
      repository.py
    utils/
      time_utils.py
      validation.py
  tests/
    unit/
    integration/
  .env.example
  requirements.txt
```

## Implementation Roadmap

1. Bootstrap project skeleton and config management.
2. Implement Zerodha adapter and canonical models.
3. Build portfolio + market MCP tools.
4. Add analytics engine and risk engine tools.
5. Add orchestrator policies (LLM must call tools for numbers).
6. Add caching, logging, and error handling.
7. Add test suite (unit + integration + contract tests).
8. Add monitoring dashboard and production hardening.

## Testing Strategy

- Unit tests:
  - Indicator calculations
  - Portfolio aggregation
  - Risk metrics
- Integration tests:
  - Zerodha adapter with mocked API responses
  - MCP tool contract and schema validation
- End-to-end tests:
  - Prompt -> tool chain -> final response
  - Failure scenarios (timeout, partial data, stale cache)

## Example User Prompts

- "Summarize my portfolio risk in 5 bullet points."
- "Compare INFY vs TCS using 6-month volatility and drawdown."
- "If NIFTY drops 2%, what could happen to my current holdings?"
- "Show top concentration risks and how to reduce them."

## Non-Goals (Initial Version)

- Autonomous order placement.
- High-frequency trading decisions.
- Fully automated buy/sell recommendations without user review.

## Disclaimer

This system is for analysis and educational assistance. It does not provide financial advice. All investment decisions should be reviewed independently.

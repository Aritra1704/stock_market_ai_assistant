from __future__ import annotations

from src.mcp_server.schemas import ToolRequest, ToolResponse
from src.mcp_server.tools.analytics_tools import compute_stock_metrics
from src.mcp_server.tools.market_tools import get_historical_candles, get_stock_quote
from src.mcp_server.tools.portfolio_tools import get_portfolio_snapshot
from src.mcp_server.tools.risk_tools import risk_summary


class MCPServer:
    def __init__(self) -> None:
        self.registry = {
            "get_portfolio_snapshot": lambda args: get_portfolio_snapshot(),
            "get_stock_quote": lambda args: get_stock_quote(args["symbol"]),
            "get_historical_candles": lambda args: get_historical_candles(args["symbol"], args.get("days", 180)),
            "compute_stock_metrics": lambda args: compute_stock_metrics(args["symbol"]),
            "risk_summary": lambda args: risk_summary(),
        }

    def execute(self, request: ToolRequest) -> ToolResponse:
        func = self.registry.get(request.tool)
        if not func:
            return ToolResponse(success=False, error=f"Unknown tool: {request.tool}")
        try:
            result = func(request.args)
            return ToolResponse(success=True, result=result)
        except Exception as exc:  # pragma: no cover
            return ToolResponse(success=False, error=str(exc))

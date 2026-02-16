from __future__ import annotations

import pandas as pd

from src.strategies.swing_v1 import generate_exit_signal, generate_signal


def test_breakout_buy_setup_signal() -> None:
    rows = 70
    data = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=rows, freq="D"),
            "open": [100 + i * 0.5 for i in range(rows)],
            "high": [101 + i * 0.5 for i in range(rows)],
            "low": [99 + i * 0.5 for i in range(rows)],
            "close": [100 + i * 0.5 for i in range(rows)],
            "volume": [100000] * rows,
        }
    )

    data.loc[rows - 1, "close"] = data.loc[rows - 2, "high"] + 2
    data.loc[rows - 1, "high"] = data.loc[rows - 1, "close"] + 1

    signal = generate_signal(data, entry_style="breakout", horizon_days=20)

    assert signal.action == "BUY_SETUP"
    assert signal.params["gtt_buy_trigger"] > 0
    assert signal.params["stop_loss"] < signal.params["gtt_buy_trigger"]
    assert signal.params["take_profit"] > signal.params["gtt_buy_trigger"]


def test_exit_logic_time_stop_and_trailing_stop() -> None:
    row = pd.Series({"close": 110.0, "atr14": 2.0})
    time_stop = generate_exit_signal(
        latest_row=row,
        entry_price=100.0,
        trailing_stop=95.0,
        take_profit=130.0,
        holding_days=25,
        horizon_days=20,
    )
    assert time_stop.action == "EXIT"
    assert "Time-stop" in time_stop.rationale

    breached = generate_exit_signal(
        latest_row=pd.Series({"close": 95.0, "atr14": 1.0}),
        entry_price=100.0,
        trailing_stop=96.0,
        take_profit=130.0,
        holding_days=5,
        horizon_days=20,
    )
    assert breached.action == "EXIT"
    assert "trailing stop" in breached.rationale.lower()

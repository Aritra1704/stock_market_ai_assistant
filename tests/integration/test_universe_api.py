from __future__ import annotations


def test_universe_seed_and_query_endpoints(test_ctx) -> None:
    client = test_ctx["client"]

    seed_resp = client.post("/api/universe/seed", json={"path": "data/nifty100.txt"})
    assert seed_resp.status_code == 200
    seed_payload = seed_resp.json()
    assert seed_payload["seeded"] >= 5
    assert seed_payload["invalid_lines"] == 0

    instruments_resp = client.get("/api/universe/instruments", params={"limit": 10})
    assert instruments_resp.status_code == 200
    instruments = instruments_resp.json()
    assert len(instruments) >= 5
    assert all(item["symbol"].endswith(".NS") for item in instruments)

    sectors_resp = client.get("/api/universe/sectors")
    assert sectors_resp.status_code == 200
    sectors_payload = sectors_resp.json()
    assert "counts" in sectors_payload
    assert any(item["trading_sector"] == "UNKNOWN" for item in sectors_payload["counts"])

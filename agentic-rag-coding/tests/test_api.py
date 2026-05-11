from __future__ import annotations

from fastapi.testclient import TestClient

def test_query_without_deepseek_key_returns_clear_contract_error(monkeypatch) -> None:
    from src import api

    class MissingKeyLlm:
        configured = False

    monkeypatch.setattr(api, "llm", MissingKeyLlm())
    client = TestClient(api.app)

    response = client.post("/api/query", json={"user_query": "请比较 IMU 方法", "top_k": 8, "language": "zh"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed_contract_validation"
    assert "DEEPSEEK_API_KEY" in payload["final_answer"]["answer_text"]

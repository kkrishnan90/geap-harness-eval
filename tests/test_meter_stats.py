import json

from geap_eval.analytics import pass_at_k, pass_hat_k
from geap_eval.meter import Meter, classify_error, parse_anthropic, parse_gemini
from geap_eval.runner import mark_retries, union_len, verify_thinking
from geap_eval.adapters.base import ResolvedRole


def test_gemini_sse_stream():
    chunks = [
        {"candidates": [{"content": {"parts": [{"text": "Hel"}]}}]},
        {"candidates": [{"content": {"parts": [{"functionCall": {"name": "bash", "args": {}}}]}, "finishReason": "STOP"}],
         "usageMetadata": {"promptTokenCount": 120, "cachedContentTokenCount": 100, "candidatesTokenCount": 7,
                           "thoughtsTokenCount": 30, "totalTokenCount": 157, "trafficType": "ON_DEMAND"},
         "modelVersion": "gemini-4-argon"},
    ]
    raw = "".join(f"data: {json.dumps(c)}\r\n\r\n" for c in chunks).encode()
    rec = {}
    parse_gemini(raw, rec)
    assert rec["tok_input"] == 20 and rec["tok_cache_read"] == 100 and rec["tok_output"] == 7
    assert rec["tok_thinking"] == 30 and rec["tool_calls_emitted"] == 1 and rec["traffic_type"] == "ON_DEMAND"
    assert rec["tok_input"] + rec["tok_cache_read"] + rec["tok_output"] + rec["tok_thinking"] == rec["tok_total"]


def test_gemini_json_array_stream():
    raw = json.dumps([{"candidates": [{"content": {"parts": [{"text": "ok?"}]}, "finishReason": "STOP"}],
                       "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2, "totalTokenCount": 7}}]).encode()
    rec = {}
    parse_gemini(raw, rec)
    assert rec["tok_input"] == 5 and rec["stop_reason"] == "STOP" and rec["text_tail"] == "ok?"


def test_anthropic_sse_with_cache_ttl_and_tools():
    evs = [
        {"type": "message_start", "message": {"model": "claude-opus-5-5", "usage": {"input_tokens": 12, "cache_read_input_tokens": 3000,
            "cache_creation_input_tokens": 500, "cache_creation": {"ephemeral_5m_input_tokens": 200, "ephemeral_1h_input_tokens": 300}, "output_tokens": 1}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "tool_use", "id": "tu_1", "name": "Bash"}},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 88}},
    ]
    raw = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in evs).encode()
    rec = {}
    parse_anthropic(raw, rec)
    assert (rec["tok_input"], rec["tok_cache_read"], rec["tok_cache_write_5m"], rec["tok_cache_write_1h"], rec["tok_output"]) == (12, 3000, 200, 300, 88)
    assert rec["tool_calls_emitted"] == 1 and rec["stop_reason"] == "tool_use" and rec["_tool_uses"] == [("tu_1", "Bash")]


def test_request_info_tool_results_and_thinking():
    m = Meter(lambda *a: None)
    body = json.dumps({"messages": [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu_1", "is_error": True}]}],
                       "tools": [{}, {}], "thinking": {"type": "adaptive"}, "output_config": {"effort": "high"}}).encode()
    info = m._request_info("v1/projects/test-project/locations/global/publishers/anthropic/models/claude-opus-5-5:streamRawPredict", body)
    assert info["provider"] == "anthropic" and info["stream"] and info["tools_defined"] == 2
    assert info["_tool_results"] == [{"call_id": "tu_1", "status": "error"}]
    assert '"effort": "high"' in info["thinking_requested"]


def test_classify_errors():
    assert classify_error(429, b'{"error":{"status":"RESOURCE_EXHAUSTED"}}') == "quota"
    assert classify_error(429, b"Quota exceeded for requests per day") == "quota_daily"
    assert classify_error(529, b"overloaded") == "overloaded"
    assert classify_error(403, b"") == "auth"


def test_pass_at_k():
    assert pass_at_k(5, 5, 3) == 1.0
    assert pass_at_k(5, 0, 3) == 0.0
    assert abs(pass_at_k(5, 2, 1) - 0.4) < 1e-9
    assert abs(pass_hat_k(5, 3, 2) - 0.3) < 1e-9  # C(3,2)/C(5,2)=3/10


def test_union_and_retries():
    assert union_len([(0, 2), (1, 3), (5, 6)]) == 4
    tools = [{"name": "bash", "status": "error", "args_hash": "a"}, {"name": "bash", "status": "ok", "args_hash": "a"},
             {"name": "edit", "status": "ok", "args_hash": "b"}]
    mark_retries(tools)
    assert [t["is_retry"] for t in tools] == [False, True, False]


def test_verify_thinking():
    roles = {"default": ResolvedRole("gemini-4-argon", "high", "global", "google")}
    assert verify_thinking([{"model": "gemini-4-argon", "provider": "google", "thinking_requested": '{"thinkingLevel": "HIGH"}'}], roles) == "match"
    assert verify_thinking([{"model": "gemini-4-argon", "provider": "google", "thinking_requested": '{"thinkingLevel": "LOW"}'}], roles) == "mismatch"
    assert verify_thinking([{"model": "gemini-4-argon", "provider": "google", "thinking_requested": None}], roles) == "absent"

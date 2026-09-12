"""对话代理接口测试（会真实调用模型接口，已限制 token 数）。

标记 upstream，可用 `pytest --no-upstream` 整体跳过。
"""

import json

import pytest

pytestmark = pytest.mark.upstream


def test_chat_returns_content(server, call, ip, tiny_payload, code):
    r = call(server, tiny_payload, access_code=code, ip=ip)
    assert r.status_code == 200, f"上游返回异常：{r.text[:200]}"
    data = r.json()
    assert data["choices"][0]["message"]["content"].strip() != ""
    assert data["model"]


def test_chat_stream_returns_sse(server, call, ip, code):
    """流式请求应以 SSE 格式分片返回，并以 data: [DONE] 结束。"""
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "只回复一个字：好"}],
        "max_tokens": 5,
        "stream": True,
    }
    r = call(server, payload, access_code=code, ip=ip, stream=True)
    assert r.status_code == 200, f"上游返回异常：{r.text[:200]}"
    assert "text/event-stream" in r.headers.get("Content-Type", "")

    chunks = []
    done_seen = False
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        body = line[len("data:"):].strip()
        if body == "[DONE]":
            done_seen = True
            break
        chunks.append(json.loads(body))

    assert chunks, "未收到任何数据分片"
    assert done_seen, "流式响应缺少 [DONE] 结束标记"


def test_invalid_model_is_rejected_by_upstream(server, call, ip, code):
    """非法模型名应被上游拒绝，且错误信息要透传到调用方。"""
    payload = {
        "model": "not-a-real-model",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5,
    }
    r = call(server, payload, access_code=code, ip=ip)
    assert r.status_code != 200
    assert r.text.strip() != ""


def test_empty_messages_is_rejected(server, call, ip, code):
    payload = {"model": "deepseek-chat", "messages": [], "max_tokens": 5}
    r = call(server, payload, access_code=code, ip=ip)
    assert r.status_code != 200

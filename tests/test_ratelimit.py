"""限流与配额测试。

用 stub_server（上游不可达）触发限流：请求在到达上游前就被拦下，
既能验证 429 链路，又不产生任何调用费用。
"""

import pytest

pytestmark = pytest.mark.ratelimit

# conftest 中该实例的 RATE_PER_MIN = 2
PER_MIN_LIMIT = 2


def test_rate_limit_triggered_after_limit(stub_server, call, ip, tiny_payload, code):
    """同一 IP 连续请求超过每分钟上限后，应返回 429。"""
    codes = []
    for _ in range(PER_MIN_LIMIT + 1):
        r = call(stub_server, tiny_payload, access_code=code, ip=ip)
        codes.append(r.status_code)

    assert codes[:PER_MIN_LIMIT] != [429] * PER_MIN_LIMIT, "前几次不应被限流"
    assert codes[-1] == 429, f"第 {PER_MIN_LIMIT + 1} 次应触发限流，实际：{codes}"
    assert "频繁" in r.json()["error"]


def test_rate_limit_isolated_by_ip(stub_server, call, tiny_payload, code):
    """限流按 IP 计数，一个 IP 被限不应影响其他 IP。"""
    busy_ip = "10.99.99.99"
    for _ in range(PER_MIN_LIMIT + 1):
        call(stub_server, tiny_payload, access_code=code, ip=busy_ip)

    fresh_ip = "10.88.88.88"
    r = call(stub_server, tiny_payload, access_code=code, ip=fresh_ip)
    assert r.status_code != 429, "新 IP 不应受其他 IP 限流影响"


def test_rate_limit_response_is_json(stub_server, call, tiny_payload, code):
    ip = "10.77.77.77"
    for _ in range(PER_MIN_LIMIT + 1):
        r = call(stub_server, tiny_payload, access_code=code, ip=ip)
    assert r.status_code == 429
    assert r.headers["Content-Type"].startswith("application/json")
    assert "error" in r.json()

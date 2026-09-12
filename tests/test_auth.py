"""访客口令鉴权测试。

为什么用 stub_server：口令校验发生在请求上游之前，
所以这些用例完全不会产生任何调用费用，跑一百遍也不花钱。
"""


def test_missing_code_returns_401(stub_server, call, ip, tiny_payload):
    r = call(stub_server, tiny_payload, access_code=None, ip=ip)
    assert r.status_code == 401, "未带口令应拒绝访问"
    assert "口令" in r.json()["error"]


def test_wrong_code_returns_401(stub_server, call, ip, tiny_payload):
    r = call(stub_server, tiny_payload, access_code="wrong-code", ip=ip)
    assert r.status_code == 401
    assert "口令" in r.json()["error"]


def test_correct_code_passes_auth(stub_server, call, ip, tiny_payload, code):
    """口令正确时不再返回 401。

    stub 环境下上游不可达，会得到 502 —— 这恰好说明请求已通过鉴权、
    进入转发阶段（若是 401 则鉴权逻辑有误）。
    """
    r = call(stub_server, tiny_payload, access_code=code, ip=ip)
    assert r.status_code != 401, "正确口令不应被鉴权拦截"
    assert r.status_code == 502


def test_upstream_failure_is_wrapped_as_502(stub_server, call, ip, tiny_payload, code):
    """上游异常必须被服务端兜住并转成可读的 502，而不是让前端超时。"""
    r = call(stub_server, tiny_payload, access_code=code, ip=ip)
    assert r.status_code == 502
    assert "上游" in r.json()["error"]


def test_error_body_is_json(stub_server, call, ip, tiny_payload):
    """异常响应也要返回结构化 JSON，便于前端统一解析提示。"""
    r = call(stub_server, tiny_payload, access_code=None, ip=ip)
    assert r.headers["Content-Type"].startswith("application/json")
    assert isinstance(r.json(), dict)
    assert set(r.json()) == {"error"}

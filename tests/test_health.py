"""健康检查接口测试。

/api/health 是给前端判断「后端在不在、要不要填口令」用的，
也是回归时最快的一次可用性验证。
"""

import requests


def test_health_returns_200(stub_server):
    r = requests.get(stub_server + "/api/health", timeout=5)
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("application/json")


def test_health_reports_need_code(stub_server):
    """服务端配置了口令时，前端据此显示口令输入框。"""
    data = requests.get(stub_server + "/api/health", timeout=5).json()
    assert data["ok"] is True
    assert data["needCode"] is True, "服务开启了口令校验，needCode 应为 True"


def test_health_reports_key_ready(stub_server):
    data = requests.get(stub_server + "/api/health", timeout=5).json()
    assert data["keyReady"] is True, "已注入 Key，keyReady 应为 True"


def test_health_does_not_require_code(stub_server):
    """健康检查不带口令也必须可用，否则前端无法初始化。"""
    r = requests.get(stub_server + "/api/health", timeout=5)
    assert r.status_code == 200

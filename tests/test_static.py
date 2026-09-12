"""静态服务测试。

同一个 Node 进程既做接口代理也做静态托管，这部分回归成本为零。
"""

import requests


def test_index_is_served(stub_server):
    r = requests.get(stub_server + "/", timeout=5)
    assert r.status_code == 200
    assert "text/html" in r.headers["Content-Type"]
    assert "html" in r.text.lower()


def test_missing_file_returns_404(stub_server):
    r = requests.get(stub_server + "/definitely-not-exist.html", timeout=5)
    assert r.status_code == 404


def test_secret_config_is_not_exposed(stub_server):
    """config.json 含密钥，绝不能被静态目录直接下载。"""
    r = requests.get(stub_server + "/config.json", timeout=5)
    assert r.status_code == 404, "含密钥的配置文件可被静态访问，存在泄露风险"

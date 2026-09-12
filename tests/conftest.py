"""接口测试公共夹具。

设计要点（面试可讲）：

1. **用例隔离**：限流按 IP 计数，所以每个用例都发一个专属 IP（X-Forwarded-For），
   用例之间互不干扰，可任意顺序、可重复执行。
2. **两种被测实例**：
   - `server`      —— 指向真实模型接口，验证正常链路（每次约几分钱，可用 `--no-upstream` 跳过）
   - `stub_server` —— 上游指向不可达地址，零成本验证鉴权、限流、异常兜底
3. **自带服务启停**：由 fixture 拉起 node 子进程并在结束后回收，不依赖人工先开服务。
"""

import json
import os
import random
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
SERVER_JS = ROOT / "server.js"
TEST_ACCESS_CODE = "test-pwd-2026"


def pytest_addoption(parser):
    parser.addoption(
        "--no-upstream",
        action="store_true",
        default=False,
        help="跳过会真实调用模型接口的用例",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--no-upstream"):
        skip = pytest.mark.skip(reason="已通过 --no-upstream 跳过真实调用")
        for item in items:
            if "upstream" in item.keywords:
                item.add_marker(skip)


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _node_bin():
    return os.getenv("NODE_BIN") or shutil.which("node")


def _api_key():
    """环境变量优先，其次读本地 config.json（该文件不在版本库里）。"""
    key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if key:
        return key
    cfg = ROOT / "config.json"
    if cfg.exists():
        try:
            return json.loads(cfg.read_text(encoding="utf-8")).get("apiKey", "").strip()
        except (ValueError, OSError):
            pass
    return ""


@pytest.fixture(scope="session")
def spawn_server():
    """启动一个被测服务实例，返回其 base url。"""
    procs = []
    node = _node_bin()

    def _start(**overrides):
        if not node:
            pytest.skip("未找到 node 可执行文件，请安装 Node.js 或设置 NODE_BIN 环境变量")
        port = _free_port()
        env = {
            **os.environ,
            "PORT": str(port),
            "ACCESS_CODE": TEST_ACCESS_CODE,
            "RATE_PER_MIN": "2",
            "RATE_PER_DAY": "5",
            "GLOBAL_QUOTA": "50",
            "DEEPSEEK_API_KEY": _api_key() or "fake-key-for-test",
        }
        env.update(overrides)

        proc = subprocess.Popen(
            [node, str(SERVER_JS)],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        procs.append(proc)

        base = f"http://127.0.0.1:{port}"
        deadline = time.time() + 15
        while time.time() < deadline:
            if proc.poll() is not None:
                pytest.fail("服务进程意外退出：" + (proc.stdout.read() or ""))
            try:
                if requests.get(base + "/api/health", timeout=1).status_code == 200:
                    return base
            except requests.RequestException:
                time.sleep(0.2)
        pytest.fail("服务 15 秒内未就绪")

    yield _start

    for proc in procs:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def server(spawn_server):
    """指向真实模型接口的服务实例。"""
    if not _api_key():
        pytest.skip("未配置 DEEPSEEK_API_KEY（环境变量或 config.json），跳过真实调用用例")
    return spawn_server()


@pytest.fixture(scope="session")
def stub_server(spawn_server):
    """上游不可达的服务实例：鉴权、限流、异常链路都能零成本验证。"""
    return spawn_server(UPSTREAM_URL="http://127.0.0.1:9/chat")


@pytest.fixture
def code():
    return TEST_ACCESS_CODE


@pytest.fixture
def ip():
    """每个用例一个专属 IP，隔离限流计数。"""
    return f"10.{random.randint(1, 250)}.{random.randint(1, 250)}.{random.randint(1, 250)}"


@pytest.fixture
def call():
    """统一封装 POST 请求。"""

    def _call(base, payload, path="/api/chat", access_code=TEST_ACCESS_CODE, ip=None, stream=False, timeout=60):
        headers = {"Content-Type": "application/json"}
        if access_code is not None:
            headers["x-access-code"] = access_code
        if ip:
            headers["X-Forwarded-For"] = ip
        return requests.post(base + path, json=payload, headers=headers, stream=stream, timeout=timeout)

    return _call


@pytest.fixture
def tiny_payload():
    """最小代价的请求体：限制生成长度，几乎不产生费用。"""
    return {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "只回复一个字：好"}],
        "max_tokens": 5,
        "stream": False,
    }

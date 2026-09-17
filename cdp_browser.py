# -*- coding: utf-8 -*-
"""浏览器自动化模块（基于 Chrome DevTools Protocol，无需第三方驱动）。

流程：
1. 找到本机 Edge 或 Chrome；
2. 以独立用户数据目录 + 远程调试端口启动（不影响日常浏览器，登录态可保留）；
3. 用 websocket 监听 Network 事件，自动捕获课表接口返回的 JSON。

仅依赖标准库 + requests + websocket-client（见 requirements.txt）。
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.parse

import requests

try:
    import websocket  # websocket-client
except ImportError:
    websocket = None


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def find_browser():
    """查找本机 Edge / Chrome 可执行文件。"""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


def launch_browser(exe, profile_dir, port, url):
    args = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


def _get_ws_url(port):
    end = time.time() + 20
    while time.time() < end:
        try:
            r = requests.get(f"http://127.0.0.1:{port}/json", timeout=2)
            pages = r.json()
            # 选一个普通 page 类型的标签
            for p in pages:
                if p.get("type") == "page" and p.get("webSocketDebuggerUrl"):
                    return p["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("无法连接浏览器调试端口")


class CDPClient:
    """极简 CDP 客户端：执行 JS 并监听网络响应体。"""

    def __init__(self, port):
        if websocket is None:
            raise RuntimeError("缺少 websocket-client，请先 pip install websocket-client")
        ws_url = _get_ws_url(port)
        self.ws = websocket.create_connection(ws_url, timeout=5)
        self._id = 0
        self._responses = {}   # requestId -> url
        self._enable_network()

    def _send(self, method, params=None):
        self._id += 1
        msg = {"id": self._id, "method": method}
        if params:
            msg["params"] = params
        self.ws.send(json.dumps(msg))
        return self._id

    def _enable_network(self):
        self._send("Network.enable")

    def eval(self, expression):
        mid = self._send("Runtime.evaluate", {
            "expression": expression, "returnByValue": True,
            "awaitPromise": True,
        })
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                return msg.get("result", {}).get("result", {}).get("value")

    def current_url(self):
        return self.eval("location.href") or ""

    def capture_schedule(self, keyword, json_hints, timeout=60):
        """监听网络，返回课表接口的 JSON。

        - keyword: URL 关键字
        - json_hints: 响应体字段特征
        超时抛出 TimeoutError。
        """
        end = time.time() + timeout
        self.ws.settimeout(1)
        buffered = []
        # 先处理可能已缓冲的消息
        while time.time() < end:
            try:
                raw = self.ws.recv()
            except Exception:
                continue
            msg = json.loads(raw)
            method = msg.get("method", "")
            params = msg.get("params", {})

            if method == "Network.responseReceived":
                url = params.get("response", {}).get("url", "")
                if keyword in url:
                    rid = params.get("requestId")
                    body = self._fetch_body(rid)
                    parsed = self._try_parse_schedule(body, json_hints)
                    if parsed is not None:
                        return parsed
        raise TimeoutError("监听课表接口超时")

    def _fetch_body(self, request_id):
        mid = self._send("Network.getResponseBody", {"requestId": request_id})
        # 读取直到拿到对应 id 的响应（期间的事件忽略）
        deadline = time.time() + 10
        self.ws.settimeout(2)
        while time.time() < deadline:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("id") == mid:
                result = msg.get("result", {})
                body = result.get("body", "")
                if result.get("base64Encoded"):
                    import base64
                    body = base64.b64decode(body).decode("utf-8", "ignore")
                return body
        return ""

    @staticmethod
    def _try_parse_schedule(body, hints):
        if not body:
            return None
        try:
            data = json.loads(body)
        except Exception:
            return None

        def has_hints(obj):
            if isinstance(obj, dict):
                hit = sum(1 for h in hints if h in obj)
                if hit >= 2:
                    return True
                for v in obj.values():
                    if has_hints(v):
                        return True
            elif isinstance(obj, list):
                return any(has_hints(v) for v in obj[:5])
            return False

        return data if has_hints(data) else None

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass



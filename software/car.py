"""小车控制层：把方向意图翻译成 ESP32 WebServer 的 HTTP 指令。"""
import time

import requests

from config import CAR_BASE, CMD_INTERVAL

TIMEOUT = 1.0


class Car:
    """对小车 WebServer 的轻量封装。每次调用都是独立 HTTP 请求。"""

    def __init__(self, base_url=CAR_BASE):
        self.base = base_url
        self.online = False
        self._last = {"kind": None, "t": 0.0}
        self._last_mode = None

    # ---------- 底层 ----------
    def _cmd(self, params: dict) -> bool:
        try:
            r = requests.get(self.base + "/cmd", params=params, timeout=TIMEOUT)
            self.online = r.status_code == 200
            return self.online
        except requests.RequestException:
            self.online = False
            return False

    def send_manual(self, direction: str):
        """手动操控：强制直接发送（绕过自动驾驶共用"去重缓存"），立即生效。

        用于 Web 键盘/按钮的手动控制，不走 _send 的自动节奏去重，
        保证"按一次就动一次"，方向持续按住时由上层重复调用本方法。
        """
        self.ensure_manual()
        return self._cmd({"go": direction})

    def _send(self, kind: str, params: dict, interval=CMD_INTERVAL):
        """带最小间隔的去重发送：同一动作在 interval 内不重复发，省流量。"""
        now = time.time()
        if self._last["kind"] == kind and (now - self._last["t"]) < interval:
            return
        self._last = {"kind": kind, "t": now}
        return self._cmd(params)

    # ---------- 语义动作 ----------
    def set_mode(self, mode: str):
        """mode: manual / trace / avoid"""
        ok = self._cmd({"mode": mode})
        if ok:
            self._last_mode = mode
        return ok

    def ensure_manual(self):
        """go 指令仅在 manual 模式下生效，前必须确保切到手动。"""
        if self._last_mode != "manual":
            self.set_mode("manual")

    def go(self, direction: str):
        """direction: f 前 / b 后 / l 左 / r 右 / s 停"""
        self.ensure_manual()
        if direction == "f":
            self._send("f", {"go": "f"})
        elif direction == "b":
            self._send("b", {"go": "b"})
        elif direction == "l":
            self._send("l", {"go": "l"})
        elif direction == "r":
            self._send("r", {"go": "r"})
        elif direction == "s":
            self._send("s", {"go": "s"}, interval=CMD_INTERVAL * 0.4)

    def stop_hold(self):
        """审查/危险期间反复重申停车。"""
        self.ensure_manual()
        self._cmd({"go": "s"})

    def stay_stopped_during_locate(self):
        """【定位阶段】保持停车：期间不发任何行驶指令，只保证小车不动。"""
        self.ensure_manual()
        self._cmd({"go": "s"})

    def stop(self):
        self.ensure_manual()
        self._cmd({"go": "s"})
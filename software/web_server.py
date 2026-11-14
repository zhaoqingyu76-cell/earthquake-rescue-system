"""Rescue Copilot Web 控制台 —— Flask 服务 + 后台摄像头线程。

界面布局参考指挥面板：
  左 2/3 │  空中全景摄像头(左上大窗, /video_feed) + AR 导航叠加 │
         │  小车图传(左下小窗, ESP32:81/stream)              │
  右 1/3 ──────────────────────────────────────────────────
         │  战术决策 + 坐标导航 (右上)                        │
         │  键盘控制 WASD (右下)                             │

本版工作方式（去掉"自动驾驶"）：
  - 小车完全由搜救人员 WASD 手动操控；电脑端绝不自动行驶。
  - 系统根据"锁定小车位置 + 车头朝向 yaw + 手动点选的目标区"实时算出
    建议转向角（右转 X° 后直行即可让开该区），并在画面空处叠加 AR 箭头/
    路径提示"怎么走"。
  - 无自动转向/自动行驶：转向与行驶完全由搜救人员 WASD 完成，系统只显示
    建议转向角与 AR 走向提示。

架构：一个常驻后台线程独占打开空中摄像头负责检测 + 计算导航；
      /video_feed 只把后台线程算好的最新标注帧以 MJPEG 推给浏览器。

运行：Pycharm 运行本文件；浏览器访问 http://<电脑IP>:5000
依赖：flask, opencv-python, numpy, requests
"""
import datetime
import math
import threading
import time

import cv2
import flask

import config
from car import Car
from decision import decide
from detection import (detect, detect_car_pose, draw_car, draw_warning_boxes,
                       reset_zone_tracker)

app = flask.Flask(__name__)
_LOCK = threading.Lock()
_CAR = Car()

# ============ 全局运行时状态（摄像头线程写，Flask路由读） ============
RTS = {
    "mode": "manual",             # manual(手动操控) / avoid(超声波避障)
    "car_loc": None,              # 实时检测到的小车位置 ((cx,cy), area)
    "car_locked": None,           # 人工确认后锁定的小车位置（锁定即固定，不再随帧改）
    "car_last_good": None,        # 最近一次面积达标的稳定小车位置(供确认兜底)
    "zones": [],                  # 实时 detect() 返回
    "zones_locked": [],           # 人工确认锁定的唯一目标区(导航用)
    "assessment": "",             # DeepSeek 对锁定地形的震后搜救风险研判
    "last_reason": "等待小车位置锁定…",
    "last_frame": None,           # 最新的 PROC 标注帧 (供 /video_feed 推送)
    "cmd_log": [],                # 近期的控制记录
    "car_yaw": None,              # ArUco 朝向角(度)，用于坐标导航
    "car_yaw_locked": None,       # 人工确认时锁定的朝向角（与 car_locked 同刻快照，锁定即固定）
    "nav": {"valid": False, "car": None, "yaw": None, "zone": None,
            "turn_deg": 0.0},     # 坐标导航建议（前端画 AR）
    "onboard_near": False,        # 车载图传近距兜底：检测到水/坑色块贴车
    "onboard_near_kind": "",      # 兜底识别到的地形类型: water / pit
    "hazard_stop": False,         # 刚进入危险区警戒框 / 定位丢失，系统已自动停车等人工研判
    "hazard_zone": "",            # 触发自动停车的地形类型: water / pit / collapse / ""
    "hazard_latched": False,      # 沿触发器：只在"刚进入"那一刻发一次停车
    }


def _log(msg):
    entry = f"{datetime.datetime.now().strftime('%H:%M:%S')} {msg}"
    RTS["cmd_log"].append(entry)
    if len(RTS["cmd_log"]) > 40:
        RTS["cmd_log"] = RTS["cmd_log"][-40:]
    print(msg, flush=True)


# ------------------- 坐标导航计算 -------------------
def _compute_nav(car_loc, target):
    """根据锁定小车位置 + 车头朝向 + 目标区，算出"右转几度后直行"的建议。

    car_loc: ((cx,cy), area) 参与推算的小车位置（用锁定值固定，不再随帧改）。
    target:  手动点选锁定的目标区 (kind,(cx,cy),area,bbox) 或 None。
    返回 dict 供前端画 AR 箭头/路径：
      valid: 是否可推算
      car:   小车中心 (cx,cy)
      yaw:   车头朝向角(度, 平面直角坐标系: 0=正右, 90=正上, 逆时针正)
      zone:  目标区中心 (zx,zy)
      turn_deg: 相对车头需转向的角度（正=右转，负=左转，上限 ±40°）
      fwd_px: 车到目标区的距离(px)
    原理：把车与区的横向偏差换算成转向角，让车头朝"从区侧边让开边距处擦过"
          的方向；角度有上限，避免车贴近时算出接近 90° 导致转向后打横/向后。
    """
    MAX_NAV_TURN = 40.0
    nav = {"valid": False, "car": None, "yaw": None, "zone": None,
           "turn_deg": 0.0, "fwd_px": 0.0}
    if car_loc is None or target is None:
        return nav
    (ccx, ccy), _area = car_loc
    zx, zy = target[1]
    bw = target[3][2]
    # 朝向角优先用锁定快照（car_locked 那刻的 car_yaw_locked），锁定后不随帧改、
    # 不随 ArUco 单帧闪失抖动（与 car_locked 同原则）。
    yaw = RTS["car_yaw_locked"] if RTS["car_yaw_locked"] is not None else RTS["car_yaw"]
    nav["car"] = (ccx, ccy)
    nav["yaw"] = yaw if yaw is not None else 0.0
    nav["zone"] = (zx, zy)
    if yaw is None:
        return nav
    # 车头朝向单位向量（平面直角坐标系: 0=正右, 90=正上；转入图像 y 向下则取 -sin）
    a = math.radians(yaw)
    hx, hy = math.cos(a), -math.sin(a)
    vx, vy = zx - ccx, zy - ccy
    fwd = vx * hx + vy * hy            # 目标在前方为正
    side = vx * (-hy) + vy * hx        # 目标在右侧为正
    dist = math.hypot(vx, vy)
    if abs(fwd) < 1e-6 or dist < 1e-6:
        return nav
    margin_px = config.AVOID_MARGIN_CM * config.PIXELS_PER_CM
    need_side = bw / 2.0 + margin_px   # 需横向让开的量
    # 在该让开量下，车头相对"正对目标区方向"还要偏一点，好从区侧边擦过
    base = math.degrees(math.atan(need_side / max(dist, 1.0)))
    # 目标在右 -> 右转；在左 -> 左转；再加少量指向目标的修正。
    # NAV_TURN_SIGN：转向方向可调（"说右却标左"时翻成 -1.0，现场标定，与 YAW_SIGN 同理）
    raw = (-math.degrees(math.atan2(side, fwd)) * 0.6
           + (base if side >= 0 else -base))
    turn_deg = config.NAV_TURN_SIGN * raw
    turn_deg = max(-MAX_NAV_TURN, min(MAX_NAV_TURN, turn_deg))
    nav["valid"] = True
    nav["turn_deg"] = round(turn_deg, 1)
    nav["fwd_px"] = round(dist, 0)
    return nav


def _summarize_zones(zones):
    """把锁定地形简单汇总成一句描述，供 DeepSeek 研判。"""
    if not zones:
        return "无"
    parts = []
    for kind, c, area, b in zones:
        name = {"water": "水源区", "pit": "坑洞", "collapse": "倒塌区"}.get(kind, kind)
        parts.append(f"{name}(x{int(c[0])},y{int(c[1])}) {int(area)}")
    return "; ".join(parts)


def _nearest_zone(zones, car_loc):
    """返回离小车最近的坑/水源区（仅辅助选目标，真正目标以手动点选为准）。"""
    if not zones or car_loc is None:
        return None
    (ccx, ccy), _a = car_loc
    best, best_d = None, None
    for z in zones:
        _k, (cx, cy), _area, _b = z
        d = (cx - ccx) ** 2 + (cy - ccy) ** 2
        if best is None or d < best_d:
            best, best_d = z, d
    if best_d > config.ZONE_NEAR_MAX_PX ** 2:
        return None
    return best


def _assess_zones_async(zones):
    """对给定的地形列表触发一次 DeepSeek 震后搜救风险研判（后台线程，不阻塞调用方）。"""
    if not zones:
        return
    summary = _summarize_zones(zones)
    with _LOCK:
        RTS["assessment"] = "正在调用 DeepSeek 研判…"

    def _run():
        try:
            from deepseek import call_zone_assessment
            res = call_zone_assessment(summary)
        except Exception:
            res = "DeepSeek研判失败，请人工判断。"
        with _LOCK:
            RTS["assessment"] = res

    threading.Thread(target=_run, daemon=True).start()


def _auto_assess():
    """对当前锁定地形触发一次 DeepSeek 震后搜救风险研判（异步，不阻塞请求线程）。"""
    with _LOCK:
        zl = list(RTS["zones_locked"])
    _assess_zones_async(zl)


# ------------------- 控制口令鉴权 -------------------
# 会动小车的接口（/api/cmd、/api/mode、/api/avoid、/api/confirm、
# /api/select_zone、/api/unlock）必须带对口令才执行；只读接口
# （/、/api/status、/video_feed）不用口令。
# 口令由环境变量 CONTROL_TOKEN 设定；没设 = 不设防（启动时会打印提醒）。
_CONTROL_PATHS = {"/api/cmd", "/api/mode", "/api/avoid", "/api/confirm",
                  "/api/select_zone", "/api/unlock"}


@app.before_request
def _check_control_token():
    if flask.request.path not in _CONTROL_PATHS:
        return None
    token = getattr(config, "CONTROL_TOKEN", "")
    if not token:
        return None
    if flask.request.args.get("token", "") != token:
        return flask.jsonify({"ok": False, "reason": "控制口令不对或没带口令"}), 403
    return None


# ------------------- Flask 路由 -------------------
_ONBOARD_URL_CACHE = []


@app.route("/")
def _route_index():
    return index()


def _probe_onboard_url():
    """自动检测小车图传可用地址。

    小车图传（GC2145）的 MJPEG 流服务有时不在监听：固件默认仅在 80 端口提供
    配置页 + /capture 单帧抓图，:81/stream 需点"Start Stream"后才起流；或流服务
    未启动。这里按候选顺序探测第一个能连通的对象：
        1) config.ONBOARD_STREAM_URL  (默认 :81/stream  真流，实时)
        2) http://<IP>/capture        (80 单帧抓图，无流时兜底，能看到画面但不连续)
    命中后缓存到 _ONBOARD_URL_CACHE，供 index()/onboard 线程读取。
    """
    import requests as _rq
    cand = [config.ONBOARD_STREAM_URL, f"http://{config.ONBOARD_IP}/capture"]
    for url in cand:
        try:
            r = _rq.get(url, stream=True, timeout=3.0)
            r.close()
            _ONBOARD_URL_CACHE.append(url)
            return url
        except Exception:
            continue
    return None


def index():
    import os
    with open(os.path.join(os.path.dirname(__file__), "web", "index.html"),
              encoding="utf-8") as f:
        html = f.read()
    onb = (_ONBOARD_URL_CACHE[0] if _ONBOARD_URL_CACHE
           else config.ONBOARD_STREAM_URL)
    html = html.replace("ENV_ONBOARD_URL", repr(onb))
    html = html.replace("ENV_CAR_IP", str(config.CAR_IP))
    html = html.replace("ENV_PROC_W", str(config.PROC_W))
    html = html.replace("ENV_PROC_H", str(config.PROC_H))
    return flask.Response(html, mimetype="text/html")


@app.route("/api/status")
def api_status():
    with _LOCK:
        z = RTS["zones"]
        zones_json = [
            {"kind": k, "area": round(a, 1), "cx": int(c[0]), "cy": int(c[1]),
             "bbox": [int(v) for v in b]}
            for k, c, a, b in z
        ]
        zl = [
            {"kind": k, "area": round(a, 1), "cx": int(c[0]), "cy": int(c[1]),
             "bbox": [int(v) for v in b]}
            for k, c, a, b in RTS["zones_locked"]
        ]
        nav = dict(RTS["nav"])
        return flask.jsonify({
            "mode": RTS["mode"],
            "car_loc": RTS["car_loc"],
            "car_locked": RTS["car_locked"],
            "zones": zones_json,
            "zones_locked": zl,
            "reason": RTS["last_reason"],
            "assessment": RTS["assessment"],
            "onboard_near": RTS["onboard_near"],
            "onboard_near_kind": RTS["onboard_near_kind"],
            "hazard_stop": RTS["hazard_stop"],
            "hazard_zone": RTS["hazard_zone"],
            "nav": nav,
            "collapse": config.COLLAPSE_SECTOR,
            "cmd_log": list(reversed(RTS["cmd_log"])),
        })


@app.route("/api/cmd")
def api_cmd():
    """手动操控：按键强制直发，完全由搜救人员控制小车。"""
    a = flask.request.args.get("a", "s")
    _CAR.ensure_manual()
    _dir_table = {"s": "⏹ 停车", "f": "↑ 前进",
                  "b": "↓ 后退", "l": "← 左转", "r": "→ 右转"}
    if a in _dir_table:
        _CAR.send_manual(a)
        _log(_dir_table[a])
    return flask.jsonify({"ok": True, "mode": "manual"})


@app.route("/api/confirm")
def api_confirm():
    """锁定小车位置：作为坐标导航推算的基准，锁定即固定，不再随帧改。

    换下一个目标区时也用同一锁定位置推算（用户可随时重新点确认更新）。
    不触发任何自动行驶——行驶由搜救人员 WASD 手动完成。
    """
    with _LOCK:
        cl = RTS["car_loc"] or RTS["car_last_good"]
        cy = RTS["car_yaw"]
    if cl is not None and cl[1] >= config.CAR_LOC_AREA_MIN:
        with _LOCK:
            RTS["car_locked"] = cl
            if cy is not None:
                RTS["car_yaw_locked"] = cy
        _log("🔒 已锁定小车位置（作为导航推算基准，锁定即固定）；"
             "请在左侧画面点选一个坑/水源区作为当前目标")
        return flask.jsonify({"ok": True, "locked": True})
    _log("⚠ 小车尚未被稳定识别，无法锁定")
    return flask.jsonify({"ok": False, "reason": "小车尚未被稳定识别"})


@app.route("/api/select_zone")
def api_select_zone():
    """手动点选左侧画面中的一个坑/水源区作为当前唯一目标（导航目标）。

    点击坐标换算成 PROC 帧坐标后传 x/y。只锁这一个是导航目标，
    其他区仍显示但仅作参考；换下一个目标重新点选即可。
    """
    try:
        px = int(flask.request.args.get("x", -1))
        py = int(flask.request.args.get("y", -1))
    except (TypeError, ValueError):
        return flask.jsonify({"ok": False, "reason": "坐标参数异常"})
    with _LOCK:
        zones = list(RTS["zones"])
    if not zones:
        return flask.jsonify({"ok": False, "reason": "当前未检测到坑/水源区"})
    if not (0 <= px <= config.PROC_W and 0 <= py <= config.PROC_H):
        return flask.jsonify({"ok": False, "reason": "点击位置超出画面范围"})
    best, best_d = None, float("inf")
    for z in zones:
        _k, (cx, cy), _a, b = z
        x0, y0, w, h = b
        if x0 <= px <= x0 + w and y0 <= py <= y0 + h:
            best, best_d = z, 0.0
            break
        d = (cx - px) ** 2 + (cy - py) ** 2
        if d < best_d:
            best, best_d = z, d
    if best is None:
        return flask.jsonify({"ok": False, "reason": "未命中任何区"})
    kind = best[0]
    zn = {"water": "水源区", "pit": "坑洞", "collapse": "倒塌区"}.get(kind, kind)
    with _LOCK:
        RTS["zones_locked"] = [best]
    _log(f"🎯 已点选当前目标：{zn} ({int(best[1][0])},{int(best[1][1])})；用于坐标导航")
    _auto_assess()
    return flask.jsonify({"ok": True, "kind": kind, "count": 1})


@app.route("/api/unlock")
def api_unlock():
    """清空当前目标区（保留小车锁定），允许用户点选下一个区。"""
    with _LOCK:
        RTS["zones_locked"] = []
        RTS["assessment"] = ""
        RTS["nav"] = {"valid": False, "car": None, "yaw": None,
                      "zone": None, "turn_deg": 0.0}
    _log("🔓 已清空当前目标区，可点选下一个")
    return flask.jsonify({"ok": True})


@app.route("/api/avoid")
def api_avoid():
    """切换到 ESP32 端超声波避障模式（车载近距避障）。"""
    _CAR.stop()
    ok = _CAR.set_mode("avoid")
    RTS["mode"] = "avoid"
    _log(f"🧭 切换为【超声波避障】模式 {'成功' if ok else '失败'}")
    return flask.jsonify({"ok": ok, "mode": "avoid"})


@app.route("/api/mode")
def api_mode():
    """切换工作模式：m=manual(手动操控) / avoid(超声波避障)。

    去掉"自动驾驶"：没有 auto，电脑端永远不自动行驶。
    """
    m = flask.request.args.get("m", "manual")
    if m == "avoid":
        _CAR.stop()
        ok = _CAR.set_mode("avoid")
        RTS["mode"] = "avoid"
        _log(f"🧭 已切换到【超声波避障】 {'成功' if ok else '失败'}")
        return flask.jsonify({"ok": ok, "mode": "avoid"})
    # manual：回到手动操控
    _CAR.stop()
    _CAR.ensure_manual()
    RTS["mode"] = "manual"
    _log("🎮 已切换到【手动操控】，按住 WASD 直接控制小车")
    return flask.jsonify({"ok": True, "mode": "manual"})


@app.route("/video_feed")
def video_feed():
    """空中全景摄像头 MJPEG 流 —— 只推送后台线程算好的最新标注帧。"""
    _interval = 1.0 / getattr(config, "STREAM_FPS", 14)
    _last_yield = {"t": 0.0}

    def gen():
        while True:
            with _LOCK:
                f = RTS["last_frame"]
            if f is None:
                time.sleep(0.02)
                continue
            now = time.time()
            wait = _interval - (now - _last_yield["t"])
            if wait > 0:
                time.sleep(wait)
            _last_yield["t"] = time.time()
            ok, jpg = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if not ok:
                time.sleep(0.02)
                continue
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                   + jpg.tobytes() + b"\r\n")
    return flask.Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


# ------------------- 后台摄像头线程（检测 + 导航） -------------------
def _camera_thread():
    cap = cv2.VideoCapture(config.CAMERA_ID)
    if not cap.isOpened():
        print("❌ 无法打开空中摄像头", config.CAMERA_ID)
        RTS["last_reason"] = "空中摄像头打开失败(可能被占用)，请关掉占用它的程序后重启"
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.PROC_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.PROC_H)

    _nav_tick = _make_nav_tick()
    frame_i = 0
    read_fail = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            # read 失败：摄像头被占/掉线，连续失败累计到阈值后释放重开，断面自愈
            read_fail += 1
            time.sleep(0.05)
            if read_fail >= 200:            # 累计 ~10s 读不到帧
                RTS["last_reason"] = "空中摄像头读帧失败，正在自动重连…"
                cap.release()
                time.sleep(0.5)
                cap = cv2.VideoCapture(config.CAMERA_ID)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.PROC_W)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.PROC_H)
                    read_fail = 0
                    RTS["last_reason"] = None
                    reset_zone_tracker()  # 断线前的旧区记忆清掉，避免"认领"新画面
                    print("🔄 空中摄像头已自动重连")
                continue
            continue
        read_fail = 0
        # 全景摄像头画面翻转（设备俯拍时传感器画面可能颠倒），最先做，
        # 使显示/区框/坐标/转向判断全部基于同一翻转后的帧
        if config.FLIP:
            frame = cv2.flip(frame, config.FLIP)
        frame_i += 1
        if frame_i % config.PROCESS_EVERY != 0:
            continue

        with _LOCK:
            car_pose = detect_car_pose(frame)
            if car_pose is None:
                car_loc, car_yaw = None, None
            else:
                car_loc = car_pose[:2]
                car_yaw = car_pose[2]
            RTS["car_loc"] = car_loc
            RTS["car_yaw"] = car_yaw
            if car_loc is not None and car_loc[1] >= config.CAR_LOC_AREA_MIN:
                RTS["car_last_good"] = car_loc
            # 检测坑/水源时排除小车自身区域，避免黄轮子/车体被误识别成"坑"
            zones, annotated = detect(frame, exclude_car=car_loc, annotate=False)
            RTS["zones"] = zones
            RTS["last_frame"] = annotated
        _nav_tick(car_loc, zones, annotated)

    cap.release()


def _make_nav_tick():
    """返回导航刷新回调（摄像头线程调用）：只检测 + 画框 + 算建议角度，
    绝不自动发行驶指令——行驶始终由人工 WASD 接管。"""

    def tick(car_loc, zones, annotated):
        with _LOCK:
            mode = RTS["mode"]
            # 锁定小车位置固定优先（锁定即基准，ArUco 单帧闪失也不替换）
            dcar = RTS["car_locked"] or car_loc
            zl = list(RTS["zones_locked"])

        # 目标区：手动点选锁定的唯一区；未点选则实时离车最近区作导航参考
        if zl:
            dnz = zl[0]
        else:
            dnz = _nearest_zone(zones, dcar) if dcar else None

        # 视频流里只画小车定位框；坑/水源框与 AR 统一由前端 canvas 画
        # （避免后端"色纸框+警戒框"与前端框叠影导致"一堆框"）
        if dcar is not None:
            draw_car(annotated, dcar)

        # 算坐标导航建议（供前端画 AR 箭头）
        nav = _compute_nav(dcar, dnz)
        with _LOCK:
            RTS["nav"] = nav
            if mode == "manual":
                if nav.get("valid"):
                    t = nav["turn_deg"]
                    d = "右" if t >= 0 else "左"
                    RTS["last_reason"] = (f"坐标导航：请{d}转 {abs(t):.0f}° 后直行让开目标区")
                elif dcar is not None and dnz is not None:
                    RTS["last_reason"] = "坐标导航：车头朝向未识别，先调整小车对准"
                else:
                    RTS["last_reason"] = ("等待锁定小车 + 点选目标区 → 出导航建议")

        # 安全停车（只在手动模式）：进入危险区警戒框 / 定位丢失 -> 停车等人工研判。
        # 边缘触发：只在"刚进入"那一刻发一次停车，不与人工操控抢指令；
        # 人工按住 W 开出警戒区后自动解除，下次再进入会重新触发。
        if mode == "manual":
            dec = decide(car_loc, zones)
            with _LOCK:
                latched = RTS["hazard_latched"]
            if dec.action == "s" and not latched:
                lost_only = dec.zone is None
                with _LOCK:
                    seen_before = RTS["car_last_good"] is not None
                with _LOCK:
                    RTS["hazard_latched"] = True
                if lost_only and not seen_before:
                    # 从没定位过小车：没什么可停的，只把沿触发器置位
                    pass
                else:
                    _CAR.stop_hold()
                    with _LOCK:
                        RTS["hazard_stop"] = True
                        RTS["hazard_zone"] = dec.zone[0] if dec.zone else ""
                    if dec.zone is not None:
                        zname = {"water": "水源区", "pit": "坑洞",
                                 "collapse": "倒塌区"}.get(dec.zone[0], dec.zone[0])
                        _log(f"⛔ 进入{zname}警戒区，已自动停车，等待人工研判")
                        _assess_zones_async([dec.zone])
                        with _LOCK:
                            RTS["last_reason"] = f"⛔ 已进入{zname}警戒区，自动停车，等待人工研判"
                    else:
                        _log("⛔ 小车定位丢失，已自动停车")
                        with _LOCK:
                            RTS["last_reason"] = "⛔ 小车定位丢失，已自动停车"
            elif dec.action == "f":
                with _LOCK:
                    RTS["hazard_latched"] = False
                    RTS["hazard_stop"] = False
                    RTS["hazard_zone"] = ""

    return tick


def _onboard_thread():
    """车载图传近距兜底线程：低分辨率隔帧 HSV 检测水/坑色块。

    空中俯视在小车贴近地面纸时是盲区，用图传作第二层提示：当水/坑色块
    占画面比 >= ONBOARD_NEAR_RATIO 时置 RTS["onboard_near"]=True，
    前端状态区提示"贴近"，提醒搜救人员减速/停止（不自动控制小车）。
    图传未开启/拉流失败静默跳过，不影响主流程。
    """
    import requests
    import numpy as np
    url = (_ONBOARD_URL_CACHE[0] if _ONBOARD_URL_CACHE
           else config.ONBOARD_STREAM_URL)
    try:
        r = requests.get(url, stream=True, timeout=3.0)
    except Exception:
        _log("⚠ 车载图传兜底线程：拉流失败，跳过（不影响主流程）")
        return
    bytes_buf = b""
    frame_i = 0
    try:
        for chunk in r.iter_content(chunk_size=2048):
            bytes_buf += chunk
            start = bytes_buf.find(b"\xff\xd8")
            end = bytes_buf.find(b"\xff\xd9")
            if start == -1 or end == -1 or end < start:
                if len(bytes_buf) > 1 << 20:
                    bytes_buf = b""
                continue
            jpg = bytes_buf[start:end + 2]
            bytes_buf = bytes_buf[end + 2:]
            frame_i += 1
            if frame_i % config.ONBOARD_PROCESS_EVERY != 0:
                continue
            img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                continue
            small = cv2.resize(img, (config.ONBOARD_PROC_W, config.ONBOARD_PROC_H))
            hsv = cv2.cvtColor(cv2.GaussianBlur(small, (5, 5), 0), cv2.COLOR_BGR2HSV)
            ratio, kind = 0.0, ""
            for k, low, high in [("water", config.WATER_LOW, config.WATER_HIGH),
                                 ("pit", config.PIT_LOW, config.PIT_HIGH)]:
                m = cv2.inRange(hsv, low, high)
                ratio = m.mean() / 255.0
                if ratio >= config.ONBOARD_NEAR_RATIO:
                    kind = k
                    break
            if kind:
                with _LOCK:
                    RTS["onboard_near"] = True
                    RTS["onboard_near_kind"] = kind
                _log(f"⚠ 车载兜底：前方{({'water':'水源','pit':'坑','collapse':'倒塌区'}.get(kind,kind))}"
                     f"占画面 {ratio*100:.0f}% —— 提醒减速/停止（人工操控）")
            else:
                with _LOCK:
                    RTS["onboard_near"] = False
                    RTS["onboard_near_kind"] = ""
    except Exception as e:
        _log(f"车载图传兜底线程结束: {e}")
    finally:
        try:
            r.close()
        except Exception:
            pass


if __name__ == "__main__":
    config.ask_deepseek_key()  # 没设环境变量时，启动问一次 Key（回车跳过）
    _CAR.ensure_manual()
    RTS["mode"] = "manual"            # 默认手动操控，未确认小车前小车绝不动
    t = threading.Thread(target=_camera_thread, daemon=True)
    t.start()
    if getattr(config, "ONBOARD_ENABLE", True) and config.ONBOARD_STREAM_URL:
        _onb_url = _probe_onboard_url()
        if _onb_url:
            print(f"✓ 自动检测到小车图传：(可连通) {_onb_url}")
            if _onb_url.endswith("/capture"):
                print("  ℹ 检测到的是单帧抓图(/capture)：图传 MJPEG 流(:81/stream)未运行，"
                      "到图传页 http://%s 点『Start Stream』可开启实时流" % config.ONBOARD_IP)
            else:
                # 仅真流(:81/stream)才启用车载近距兜底检测线程；capture 单帧会阻塞线程
                threading.Thread(target=_onboard_thread, daemon=True).start()
                print("车载图传近距兜底线程已启动（拉流", _onb_url, "）")
        else:
            print(f"⚠ 自动检测小车图传失败：{config.ONBOARD_STREAM_URL} 与 "
                  f"http://{config.ONBOARD_IP}/capture 均无法连通，请确认图传设备在线")
    try:
        import socket
        _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _s.connect(("8.8.8.8", 80))
        _local_ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        _local_ip = "127.0.0.1"
    print(f"[Rescue Copilot Web] 浏览器访问 http://{_local_ip}:{config.UI_PORT}")
    if not getattr(config, "CONTROL_TOKEN", ""):
        print("⚠ 未设置 CONTROL_TOKEN：同一局域网内任何人都能调用 /api/cmd 控制小车；"
              "演示前请设环境变量 CONTROL_TOKEN，并在网页口令框里填同一个口令")
    print("工作方式：确认小车位置→点选目标区→出坐标导航建议；"
          "WASD 手动操控，按建议转向角走")
    print("小车图传窗口地址:", config.ONBOARD_STREAM_URL,
          "(若图传未开，该窗口会一直转圈)")
    try:
        app.run(host=config.UI_HOST, port=config.UI_PORT,
                debug=False, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        _CAR.stop()
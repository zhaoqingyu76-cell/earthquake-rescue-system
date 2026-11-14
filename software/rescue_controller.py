"""备用控制器：OpenCV 窗口版（离线备用，不参与 Web 主流程）。

Web 主流程（web_server.py）始终人工在回路、零自动行驶；本文件只在
没浏览器 / 离线调试时用，保留早期的两阶段流程：

阶段一【定位小车】：摄像头识别小车（顶部贴 ArUco 码），只有小车被稳定
  识别后按空格确认才进入行驶，确认前绝不发送行驶指令。
阶段二【行驶】：识别水源(青蓝)/坑(红)，控制前进；遇前方水源/坑 ->
  小车暂停，接 DeepSeek 研判，由搜救人员按键选择后才继续。

键盘：
  阶段一：空格 = 确认小车位置并开始行驶
  阶段二：[1] 从旁边绕过去  [2] 直穿  [s] 停止不前进
  全程：q / ESC 退出
"""
import time

import cv2

import config
from car import Car
from deepseek import call_deepseek_tactical
from detection import detect, detect_car, draw_car, draw_warning_boxes
from decision import decide

WINDOW = "Rescue Copilot - 搜救决策"

STATE_LOCATE, STATE_DRIVE, STATE_HALTED = "locate", "drive", "halted"


def draw_bar(frame, status, color):
    h = frame.shape[0]
    cv2.rectangle(frame, (0, h - 46), (frame.shape[1], h), (10, 10, 10), -1)
    cv2.putText(frame, status, (12, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return frame


def main():
    config.ask_deepseek_key()  # 没设环境变量时，启动问一次 Key（回车跳过）
    car = Car()
    print(f"[初始化] 小车端点: {car.base}")
    car.set_mode("manual")
    time.sleep(0.3)

    cap = cv2.VideoCapture(config.CAMERA_ID,
                           cv2.CAP_DSHOW if _is_windows() else cv2.CAP_ANY)
    if not cap.isOpened():
        print(f"❌ 无法打开摄像头 {config.CAMERA_ID}，请检查 -- 换 USB 口或改 config.CAMERA_ID")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.PROC_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.PROC_H)

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    print("▶ 进入【定位】阶段：请确保小车上贴有 ArUco 码(id=%d)并置于画面内。" % config.ARUCO_MARKER_ID)

    state = STATE_LOCATE
    hazard_flag = False
    last_cmd_t = 0.0
    frame_idx = 0
    PROCESS_EVERY = 2

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            frame_idx += 1
            if frame_idx % PROCESS_EVERY != 0:
                if frame_idx % 10 == 0:
                    car.stop_hold() if state != STATE_DRIVE else None
                continue

            # 先定位小车，再排除小车自身区域检测坑/水源
            car_loc = detect_car(frame)
            zones, annotated = detect(frame, exclude_car=car_loc)
            draw_warning_boxes(annotated, zones)

            if state == STATE_LOCATE:
                car.stay_stopped_during_locate()
                draw_car(annotated, car_loc)
                if car_loc is None:
                    seek = "等待识别小车… 请把带码的平面置于画面内"
                else:
                    (cx, cy), area = car_loc
                    seek = f"已识别小车 ({int(cx)},{int(cy)}),area={int(area)} 按 空格 确认进入自动驾驶"
                annotated = draw_bar(annotated, seek, (0, 0, 255))
                cv2.imshow(WINDOW, annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == 32 and car_loc is not None and car_loc[1] >= config.CAR_LOC_AREA_MIN:
                    state = STATE_DRIVE
                    hazard_flag = False
                    car.go("f")
                    last_cmd_t = time.time()
                    print("▶ 已确认小车位置，进入【自动驾驶】：直行，遇水源/坑将暂停研判。")
                elif key in (27, ord("q")):
                    break
                continue

            decision = decide(car_loc, zones)
            ctx = ""
            status_color = (0, 0, 255) if decision.action == "s" else (0, 255, 0)

            if decision.action == "s" and not hazard_flag:
                hazard_flag = True
                car.stop_hold()
                kind, cx, cy, area, bbox = decision.zone
                zone_name = "水源区" if kind == "water" else "坑"
                obstacle = "前方坑洞" if kind == "pit" else "前方水源区"
                analysis = call_deepseek_tactical(
                    obstacle, f"小车距{zone_name}，已进入警戒区停止")
                ctx = (f"【暂停·{zone_name}】·已进入警戒区\n"
                       f"DeepSeek研判穿越后果：{analysis}\n"
                       f"请选择：[1]从旁边绕过去 [2]直穿 [s]停止")
                print(ctx)

            if not hazard_flag and state == STATE_DRIVE:
                if time.time() - last_cmd_t >= config.CMD_INTERVAL:
                    car.go(decision.action)
                    last_cmd_t = time.time()

            if not car.online:
                ctx = "⚠ 小车不可达，" + ctx if ctx else "⚠ 小车不可达"

            annotated = draw_bar(annotated, ctx or decision.reason, status_color)
            cv2.imshow(WINDOW, annotated)

            hold_ms = int(config.HOLD_CHECK_INTERVAL * 1000)
            key = cv2.waitKey(hold_ms if hazard_flag else 1) & 0xFF

            if hazard_flag:
                if key == ord("1"):
                    print("▶ 批准：从旁边绕过去")
                    _round_around(car, decision.zone[1] if decision.zone else config.CENTER_X)
                    hazard_flag = False
                elif key == ord("2"):
                    print("▶ 批准直穿")
                    car.stop_hold()
                    car.go("f")
                    hazard_flag = False
                elif key == ord("s"):
                    print("⏹ 停止不前进，转为人工遥控")
                    car.stop()
                    hazard_flag = False
                    state = STATE_HALTED
                else:
                    car.stop_hold()

            if state == STATE_HALTED:
                car.stop()
                annotated = draw_bar(annotated, "已人工停止。按空格返回自动驾驶 / ESC退出", (0, 255, 255))
                cv2.imshow(WINDOW, annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == 32:
                    state = STATE_DRIVE
                    hazard_flag = False
                    car.go("f")
                    last_cmd_t = time.time()
                elif key in (27, ord("q")):
                    break
                continue

            if key in (27, ord("q")):
                break

    finally:
        car.stop()
        cap.release()
        cv2.destroyAllWindows()
        print("已退出：小车已停车。")


def _round_around(car, cx):
    car.stop_hold()
    turn = "r" if cx < config.CENTER_X else "l"   # 反方向让开
    car.go(turn)
    time.sleep(config.ROUND_TURN_S)
    car.go("f")
    time.sleep(config.ROUND_FWD_S)
    car.go("f")


def _is_windows():
    import os
    return os.name == "nt"


if __name__ == "__main__":
    main()

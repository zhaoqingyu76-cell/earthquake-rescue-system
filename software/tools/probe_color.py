"""HSV 颜色标定工具（可视化版）—— 用它找出倒塌区/建筑(紫)真正的 HSV 范围。

为什么需要：画面里的紫色建筑如果没被框出"倒塌区"框，就是 config.COLLAPSE_LOW/HIGH
阈值没匹配上现场纸颜色。本工具把【当前阈值圈出的区域】实时画成绿色叠在画面上，
你改 LOW/HIGH 直到整块紫色建筑都稳定变绿，就说明阈值覆盖完整了。

用法：
  1. 运行本脚本，打开预览窗口；
  2. 画面里把当前被圈中的区域涂成半透明绿色（目标=紫色建筑全变绿）；
  3. 左键点击紫色纸/建筑：终端打印该点 H/S/V + 附近邻域的 H/S/V 范围；
  4. 若没全变绿/时好时坏：改本文件底部 LOW / HIGH 两个值（优先级高于 config）：
       LOW  = (H低, S低, V低)     # 小于该值的被丢弃
       HIGH = (H高, S高, V高)
  5. 按 q 退出，把最终范围写回 config.py 的 COLLAPSE_LOW / COLLAPSE_HIGH。
"""
import cv2
import numpy as np
import config

# ---- 现场标定的阈值（优先改这里试，找到后再写回 config.py）----
# 检测目标：紫色纸(建筑/倒塌区)。H 120~170 为紫/紫红。
LOW = (120, 60, 45)        # 初始取 config.COLLAPSE_LOW
HIGH = (170, 255, 255)     # 初始取 config.COLLAPSE_HIGH
# -------------------------------------------------------------

_anchor = (-1, -1)
_last_printed = (-99, -99)


def on_mouse(event, x, y, flags, param):
    global _anchor
    if event == cv2.EVENT_LBUTTONDOWN or (
            event == cv2.EVENT_MOUSEMOVE and flags & cv2.EVENT_FLAG_LBUTTON):
        _anchor = (x, y)


def sample_region(hsv, x, y, r=4):
    """统计以 (x,y) 为中心、边长为 2r+1 的邻域内 H/S/V 的 min/max。"""
    x0, y0 = max(0, x - r), max(0, y - r)
    x1, y1 = min(hsv.shape[1] - 1, x + r), min(hsv.shape[0] - 1, y + r)
    reg = hsv[y0:y1 + 1, x0:x1 + 1]
    h, s, v = reg[:, :, 0], reg[:, :, 1], reg[:, :, 2]
    return (int(h.min()), int(s.min()), int(v.min())), (int(h.max()), int(s.max()), int(v.max()))


def main():
    cap = cv2.VideoCapture(config.CAMERA_ID)
    if not cap.isOpened():
        print(f"无法打开摄像头 CAMERA_ID={config.CAMERA_ID}。请先用 probe_camera.py 确认编号。")
        return
    cv2.namedWindow("HSV_probe")
    cv2.setMouseCallback("HSV_probe", on_mouse)

    print("=" * 62)
    print("可视化 HSV 标定：绿色 = 当前阈值圈住的部分，目标=紫色建筑全变绿。")
    print(f"试调 LOW ={LOW}")
    print(f"试调 HIGH={HIGH}")
    print("左键点击紫纸 -> 打印该点 + 邻域 H/S/V 范围")
    print("按 q 退出，把最终范围写回 config.py 的 COLLAPSE_LOW / COLLAPSE_HIGH")
    print("=" * 62)

    global _anchor, _last_printed
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if config.FLIP:
            frame = cv2.flip(frame, config.FLIP)
        small = cv2.resize(frame, (960, 540))
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)

        # 实时 mask 叠加：把当前 LOW/HIGH 圈出的区域涂成绿色
        mask = cv2.inRange(hsv, np.array(LOW, dtype=np.uint8), np.array(HIGH, dtype=np.uint8))
        green = np.zeros_like(small)
        green[:, :] = (0, 255, 0)
        small = cv2.addWeighted(cv2.bitwise_and(small, small, mask=mask), 0.65,
                                cv2.bitwise_and(green, green, mask=mask), 0.35, 0)

        x, y = _anchor
        if x >= 0 and y >= 0 and (x, y) != _last_printed:
            c = hsv[y, x]
            (lmin, smin, vmin), (lmax, smax, vmax) = sample_region(hsv, x, y)
            print(f"[点选] ({x},{y}) 中心 H={int(c[0])} S={int(c[1])} V={int(c[2])}"
                  f" | 邻域范围 H={lmin}-{lmax} S={smin}-{smax} V={vmin}-{vmax}")
            print(f"   -> 建议写回 config: COLLAPSE_LOW=({lmin},{smin},{vmin}) "
                  f"COLLAPSE_HIGH=({lmax},{smax},{vmax})")
            _last_printed = (x, y)
        if x >= 0 and y >= 0:
            cv2.circle(small, (x, y), 6, (0, 0, 255), -1)

        cv2.imshow("HSV_probe", small)
        k = cv2.waitKey(10) & 0xFF
        if k == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()
    print("把最终范围写回 config.py 的 COLLAPSE_LOW / COLLAPSE_HIGH，再重启 web_server。")


if __name__ == "__main__":
    main()
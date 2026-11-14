"""检测层：复用全景摄像头.txt 的颜色分割思路，识别水源(青蓝)/坑(黄)轮廓；
另提供 ArUco 定位小车（第一步"识别小车在哪"）。"""
import cv2
import numpy as np

import config

WATER_LOW, WATER_HIGH = config.WATER_LOW, config.WATER_HIGH
PIT_LOW, PIT_HIGH = config.PIT_LOW, config.PIT_HIGH
MIN_ZONE_AREA = config.MIN_ZONE_AREA

# ---- ArUco 初始化（懒加载，避免 OpenCV 版本差异报错）----
_aruco_dict = None


def _get_aruco_dict():
    global _aruco_dict
    if _aruco_dict is None:
        _aruco_dict = cv2.aruco.getPredefinedDictionary(
            getattr(cv2.aruco, config.ARUCO_DICT))
    return _aruco_dict


def detect_car(frame):
    """识别小车（ArUco 码）在画面中的位置（仅位置，无朝向）。

    frame: 原始帧（内部会缩到 PROC 分辨率，坐标基于 PROC 坐标系）。
    返回: ((cx, cy), area) 或 None（本帧未识别到目标 id）。
    """
    pose = _detect_marker(frame)
    if pose is None:
        return None
    return pose[:2]


def detect_car_pose(frame):
    """识别小车（ArUco 码）位置 + 车头朝向角。

    返回: ((cx, cy), area, yaw_deg) 或 None。
    yaw_deg: ArUco 码朝向角（度，平面直角坐标系，区间 [-180°,180°]：
             0°=车头朝画面正右，90°=朝正上，±180°=朝正左，-90°=朝正下）。
             供"按坐标计算转向角"使用。
    """
    return _detect_marker(frame)


def _detect_marker(frame):
    """ArUco 码识别公共实现：返回 ((cx,cy), area, yaw_deg) 或 None。"""
    import math
    small = cv2.resize(frame, (config.PROC_W, config.PROC_H))
    try:
        params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(_get_aruco_dict(), params)
        corners, ids, _ = detector.detectMarkers(small)
    except (AttributeError, cv2.error):
        # 老版本 OpenCV 兼容
        corners, ids, _ = cv2.aruco.detectMarkers(
            small, _get_aruco_dict())
        params = None

    if ids is None:
        return None

    for i, m_id in enumerate(ids.flatten()):
        if m_id == config.ARUCO_MARKER_ID:
            c = corners[i][0]          # shape (4,2): 左上,右上,右下,左下
            cx = float(c[:, 0].mean())
            cy = float(c[:, 1].mean())
            area = cv2.contourArea(c)
            # 车头朝向：取 ArUco 码"顶边"(右上-左上)方向作为车头方向向量。
            # 输出为【平面直角坐标系】角度（用户约定，区间 [-180°,180°]）：
            #   0°=车头朝画面正右，90°=车头朝画面正上，±180°=朝正左，-90°=朝正下。
            # 图像坐标 y 向下（显示为 y 向上），故用 -up[1] 转回直角坐标。
            up = (c[1] - c[0])          # 右上 - 左上 = 码顶边方向
            yaw_raw = math.degrees(math.atan2(-up[1], up[0]))   # [-180,180]
            # 允许按码贴向做符号与基准校正（config 现场标定）：
            #   方向反了 -> YAW_SIGN=-1；码贴向整体偏 N° -> YAW_HEAD_OFF=N
            # 校正后仍 wrap 回 [-180°,180°]，避免出现 270° 这类越界值
            yaw = yaw_raw * config.YAW_SIGN + config.YAW_HEAD_OFF
            yaw_deg = (yaw + 180.0) % 360.0 - 180.0
            return (cx, cy), area, yaw_deg
    return None


def draw_car(frame, car_loc):
    """在 annot 帧上画出小车定位框。car_loc: 检测层画 in place。"""
    if car_loc is None:
        return
    (cx, cy), area = car_loc
    r = int(np.sqrt(area) * 0.8)
    cv2.rectangle(frame, (int(cx) - r, int(cy) - r),
                  (int(cx) + r, int(cy) + r), (0, 255, 255), 2)
    cv2.putText(frame, f"CAR ({int(cx)},{int(cy)})", (int(cx) - 40, int(cy) - r - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)


def draw_warning_boxes(frame, zones, radius_px=None):
    """画出每张色纸的边缘框 + 向外扩的 5cm 警戒框，便于现场判断触发时机。

    - 色纸边缘框：water 用青蓝色、pit 用黄色（黄纸示意）；警戒触发框为红色
    - 警戒框：在色纸 bbox 基础上向外扩 radius_px 像素的矩形
    坐标基于 PROC。
    """
    r = radius_px or config.DANGER_RADIUS_PX
    for z in zones:
        kind, _cxcy, _area, bbox = z[0], z[1], z[2], z[3]
        x, y, w, h = bbox
        color = config.WATER_FILL if kind == "water" else config.PIT_FILL
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)        # 色纸本身
        cv2.rectangle(frame, (x - r, y - r), (x + w + r, y + h + r),
                      (0, 0, 255), 2)                                 # 警戒框红
        label = "water警戒" if kind == "water" else "pit警戒"
        cv2.putText(frame, label, (x - r, y - r - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    return frame


def detect(frame, exclude_car=None, annotate=True):
    """返回 (zones, annotated)

    内部先把帧降到 PROC 分辨率再处理（省 CPU、更流畅），
    zones/annotated 坐标均基于 PROC 坐标系。

    zones: [(type, (cx, cy), area, bbox)]  type='water'|'pit'
    annotated: annotate=True 时叠加轮廓框的帧（OpenCV 窗口版用）；
               annotate=False 时返回干净底帧（Web 版用——区框交前端 canvas 画，
               避免与前端锁定后"只画一框"的叠加层叠影成"一堆框"）。
    exclude_car: ((cx,cy),area) 小车 ArUco 定位。非空时把以小车为中心的
                 CAR_EXCLUDE_RADIUS 圆形区域从坑/水源 detection 中扣除，
                 避免小车自身（黄色轮子/车身）被误识别成"坑"。
    """
    small = cv2.resize(frame, (config.PROC_W, config.PROC_H))
    hsv = cv2.cvtColor(cv2.GaussianBlur(small, (5, 5), 0), cv2.COLOR_BGR2HSV)

    zones = []
    for kind, low, high, color in [
        ("water", WATER_LOW, WATER_HIGH, (200, 140, 40)),   # BGR 填充色
        ("pit", PIT_LOW, PIT_HIGH, (0, 200, 255)),
        ("collapse", config.COLLAPSE_LOW, config.COLLAPSE_HIGH, config.COLLAPSE_FILL),
    ]:
        mask = cv2.inRange(hsv, low, high)
        # 扣除小车自身区域：小车黄轮子/车体不得识别为坑（否则车永远"贴着坑"）
        if exclude_car is not None:
            (ecx, ecy), _area = exclude_car
            r = config.CAR_EXCLUDE_RADIUS
            cv2.circle(mask, (int(ecx), int(ecy)), r, 0, -1)
        # 开运算去碎点 + 闭运算补洞（核随分辨率适当缩小）
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            area = cv2.contourArea(c)
            if area < MIN_ZONE_AREA:
                continue
            x, y, w, h = cv2.boundingRect(c)
            cx, cy = x + w // 2, y + h // 2
            zones.append((kind, (cx, cy), area, (x, y, w, h)))

    annotated = small.copy()
    if annotate:
        for kind, (cx, cy), area, (x, y, w, h) in zones:
            color = config.WATER_FILL if kind == "water" else (
                config.PIT_FILL if kind == "pit" else config.COLLAPSE_FILL)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            cv2.putText(annotated, f"{kind} {area}", (x, y - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return zones, annotated
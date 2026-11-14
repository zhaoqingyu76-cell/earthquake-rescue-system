"""检测层：空中全景画面的语义地形识别 + ArUco 小车定位。

识别三类地形——水源（青蓝）/ 坑（红）/ 建筑倒塌区（紫），
以及小车顶部的 ArUco 码（位置 + 车头朝向角），供坐标导航与危险判定使用。

流水线（每帧）：
    降分辨率 -> 高斯模糊 -> HSV 颜色分割 -> 形态学去碎点
    -> 找轮廓 -> 面积过滤 -> 形状过滤 -> 同类合并 -> 每类取大 -> 跨帧稳定

去噪设计（USB 摄像头一接上就"什么都测到"时，先看这里）：
    1. 面积门槛：小于 MIN_ZONE_AREA 的碎点直接丢掉；
    2. 形状过滤：细长条（线缆、桌边反光）和空心框不是纸，直接丢掉；
    3. 同类合并：光照不均把一张纸劈成几块时，挨着的框合并成一个区；
    4. 每类上限：每种颜色只留面积最大的几个区，画面不会被框淹没；
    5. 跨帧稳定：连续多帧都出现的区才算数，单帧闪现的斑点不要；
    6. 场地 ROI：相机拍到场地外（地面、墙边杂物）时，把场地框进来就干净了。
    前 5 项是默认开启的；第 6 项按需在 config.py 里填 ROI。
"""
import math

import cv2
import numpy as np

import config

# 颜色约定（HSV，同 config.py；这里只取别名，数值以 config.py 为准）
_ZONE_DEFS = [
    ("water", config.WATER_LOW, config.WATER_HIGH),
    ("pit", config.PIT_LOW, config.PIT_HIGH),
    ("collapse", config.COLLAPSE_LOW, config.COLLAPSE_HIGH),
]

# 画框样式：种类 -> （框颜色 BGR，中文名）
_ZONE_STYLE = {
    "water": (config.WATER_FILL, "水源区"),
    "pit": (config.PIT_FILL, "坑"),
    "collapse": (config.COLLAPSE_FILL, "倒塌区"),
}

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
    """画出每张色纸的边缘框 + 向外扩的 2cm 警戒框，便于现场判断触发时机。

    - 色纸边缘框：按种类取 _ZONE_STYLE 的颜色；
    - 警戒框：在色纸 bbox 基础上向外扩 radius_px 像素的红色矩形。
    坐标基于 PROC。
    """
    r = radius_px or config.DANGER_RADIUS_PX
    for z in zones:
        kind, _cxcy, _area, bbox = z[0], z[1], z[2], z[3]
        x, y, w, h = bbox
        color, name = _ZONE_STYLE.get(kind, ((0, 0, 255), kind))
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)        # 色纸本身
        cv2.rectangle(frame, (x - r, y - r), (x + w + r, y + h + r),
                      (0, 0, 255), 2)                                 # 警戒框红
        cv2.putText(frame, f"{name}警戒", (x - r, y - r - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    return frame


# ---------------------------------------------------------------------------
# 区域后处理：把"颜色分割出来的轮廓"变成"值得信任的地形区"
# ---------------------------------------------------------------------------

def _bbox_gap(b1, b2):
    """两个外接矩形之间的空隙（像素）：边对边的最短距离，0 = 相交或相接。

    水平和竖直方向各算一个空隙，取大的那个——只有两个方向都贴得
    足够近，才算"同一张纸被劈开了"。
    """
    x1, y1, w1, h1 = b1
    x2, y2, w2, h2 = b2
    dx = max(x2 - (x1 + w1), x1 - (x2 + w2), 0)
    dy = max(y2 - (y1 + h1), y1 - (y2 + h2), 0)
    return max(dx, dy)


def _merge_zones(zones, gap_px):
    """合并同种颜色、框挨着的区（光照不均 / 阴影把一张纸劈成几块时）。

    输入输出都是 [(kind, (cx, cy), area, bbox)]；合并后 area 相加，
    bbox 取并集，中心取并集 bbox 的中心。按面积从大到小处理，
    大纸优先"吃掉"旁边属于它的小碎块。
    """
    kept = []
    for z in sorted(zones, key=lambda t: t[2], reverse=True):
        kind, _c, area, bbox = z
        for k in kept:
            if k[0] != kind:
                continue
            if _bbox_gap(k[3], bbox) <= gap_px:
                x = min(k[3][0], bbox[0])
                y = min(k[3][1], bbox[1])
                x2 = max(k[3][0] + k[3][2], bbox[0] + bbox[2])
                y2 = max(k[3][1] + k[3][3], bbox[1] + bbox[3])
                k[2] += area
                k[3] = (x, y, x2 - x, y2 - y)
                k[1] = (x + (x2 - x) // 2, y + (y2 - y) // 2)
                break
        else:
            kept.append([kind, (bbox[0] + bbox[2] // 2, bbox[1] + bbox[3] // 2),
                         area, bbox])
    return [(k[0], k[1], k[2], k[3]) for k in kept]


def _shape_ok(bbox, area):
    """形状过滤：纸是实心的方块，线缆 / 桌边反光不是。

    - 长宽比：细长条（w/h 或 h/w 过大）直接丢掉；
    - 实心度：轮廓面积 / 外接矩形面积，空心、碎散的框不要。
    阈值见 config.ZONE_MAX_ASPECT / ZONE_MIN_SOLIDITY。
    """
    _x, _y, w, h = bbox
    if w <= 0 or h <= 0:
        return False
    if max(w, h) / min(w, h) > config.ZONE_MAX_ASPECT:
        return False
    if area / (w * h) < config.ZONE_MIN_SOLIDITY:
        return False
    return True


class ZoneTracker:
    """跨帧稳定：只有连续多帧都出现的区才算数。

    单帧闪现的斑点（反光一闪、阴影一抖）直接丢掉；区在画面里
    轻微移动时按中心距离匹配，算同一个区。摄像头断线重连后
    请调 reset()，避免拿断线前的旧区去"认领"新画面。
    """

    def __init__(self):
        self._prev = []  # [(kind, cx, cy, seen)] seen=连续出现帧数

    def reset(self):
        self._prev = []

    def update(self, zones):
        """输入本帧的区，返回"已稳定"的区（连续出现满 ZONE_PERSIST_FRAMES 帧）。"""
        cur = []
        confirmed = []
        for kind, (cx, cy), area, bbox in zones:
            seen = 1
            for pk, px, py, ps in self._prev:
                if pk != kind:
                    continue
                if (cx - px) ** 2 + (cy - py) ** 2 <= config.ZONE_TRACK_DIST_PX ** 2:
                    seen = ps + 1
                    break
            cur.append((kind, cx, cy, seen))
            if seen >= config.ZONE_PERSIST_FRAMES:
                confirmed.append((kind, (cx, cy), area, bbox))
        self._prev = cur
        return confirmed


_TRACKER = ZoneTracker()


def reset_zone_tracker():
    """清空跨帧稳定器的记忆（摄像头重连、换场地时调用）。"""
    _TRACKER.reset()


def _roi_mask():
    """场地 ROI 掩码（PROC 坐标）：只扫场地，场地外的地面、墙边杂物不进检测。

    config.ROI = None 时返回 None（全画面都扫）；否则返回 (x, y, w, h) 的掩码。
    """
    roi = getattr(config, "ROI", None)
    if not roi:
        return None
    mask = np.zeros((config.PROC_H, config.PROC_W), dtype=np.uint8)
    x, y, w, h = roi
    cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
    return mask


def detect(frame, exclude_car=None, annotate=True):
    """返回 (zones, annotated)。

    内部先把帧降到 PROC 分辨率再处理（省 CPU、更流畅），
    zones/annotated 坐标均基于 PROC 坐标系。

    zones: [(type, (cx, cy), area, bbox)]  type='water'|'pit'|'collapse'，
           只含"已稳定"的区（见 ZoneTracker）；
    annotated: annotate=True 时叠加轮廓框的帧（OpenCV 窗口版用）；
               annotate=False 时返回干净底帧（Web 版用——区框交前端 canvas 画，
               避免与前端锁定后"只画一框"的叠加层叠影成"一堆框"）。
    exclude_car: ((cx,cy),area) 小车 ArUco 定位。非空时把以小车为中心的
                 CAR_EXCLUDE_RADIUS 圆形区域从坑/水源 detection 中扣除，
                 避免小车自身（黄色轮子/车体）被误识别成"坑"。
    """
    small = cv2.resize(frame, (config.PROC_W, config.PROC_H))
    hsv = cv2.cvtColor(cv2.GaussianBlur(small, (5, 5), 0), cv2.COLOR_BGR2HSV)
    roi = _roi_mask()

    raw = []  # 本帧所有候选区（未经过合并 / 上限 / 跨帧稳定）
    for kind, low, high in _ZONE_DEFS:
        mask = cv2.inRange(hsv, low, high)
        if roi is not None:
            mask = cv2.bitwise_and(mask, roi)
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
            if area < config.MIN_ZONE_AREA:
                continue  # 碎点 / 反光：面积不够，不配当一个区
            x, y, w, h = cv2.boundingRect(c)
            if not _shape_ok((x, y, w, h), area):
                continue  # 细长条 / 空心框：形状不像纸
            raw.append((kind, (x + w // 2, y + h // 2), area, (x, y, w, h)))

    # 同类合并：被光照劈开的纸拼回一个区
    merged = []
    for kind, _low, _high in _ZONE_DEFS:
        merged += _merge_zones([z for z in raw if z[0] == kind],
                               config.ZONE_MERGE_PX)

    # 每类上限：只留面积最大的几个区，再多只会让画面变乱
    capped = []
    for kind, _low, _high in _ZONE_DEFS:
        same = sorted((z for z in merged if z[0] == kind),
                      key=lambda t: t[2], reverse=True)
        capped += same[:config.ZONE_MAX_PER_KIND]

    # 跨帧稳定：单帧闪现的不要
    zones = _TRACKER.update(capped)

    annotated = small.copy()
    if annotate:
        for kind, (cx, cy), area, (x, y, w, h) in zones:
            color, _name = _ZONE_STYLE.get(kind, ((0, 0, 255), kind))
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            cv2.putText(annotated, f"{kind} {int(area)}", (x, y - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return zones, annotated

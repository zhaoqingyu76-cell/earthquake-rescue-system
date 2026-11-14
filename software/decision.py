"""决策层：判断小车是否驶入某张色纸的警戒范围，并决定动作。

动作语义（与 ESP32 对应）：
  f  前进（不在任何纸警戒圈内 -> 直行）
  s  停车等待（小车进入某色纸向外扩 2cm 的警戒框 -> 人工研判，或小车定位丢失）
不再根据"固定画面区域"判定，而是根据"小车与色纸的像素距离"判定。
"""
import config


class Decision:
    def __init__(self, action="f", reason="", zone=None):
        self.action = action          # f / s（本版主流程只用这两个）
        self.reason = reason
        self.zone = zone              # 触发的危险地形 (kind, cx, cy, area, bbox)


def _point_to_paper_edge_dist(cx, cy, bbox):
    """小车中心 (cx,cy) 到色纸矩形边界的最短像素距离（在矩形内返回负值）。"""
    x, y, w, h = bbox
    left, right = x, x + w
    top, bottom = y, y + h
    if left <= cx <= right and top <= cy <= bottom:
        return -1.0                       # 中心已进入纸内
    dx = max(left - cx, 0, cx - right)
    dy = max(top - cy, 0, cy - bottom)
    return float((dx * dx + dy * dy) ** 0.5)


def decide(car_loc, zones, radius_px=None):
    """根据小车位置与色纸位置决定动作。

    car_loc: ((cx,cy), area) 或 None（本帧未识别到小车）
    zones:   [(kind,(cx,cy),area,bbox,...)]  来自 detect()
    radius_px: 警戒框外扩像素（默认取 config.DANGER_RADIUS_PX）

    返回:
      - 小车进入任一色纸 2cm 警戒框 -> s(停车+研判)，zone=该纸
      - 小车定位丢失 -> s(停车等待重新识别)，zone=None
      - 否则 -> f(直行)
    """
    radius = radius_px or config.DANGER_RADIUS_PX

    if car_loc is None:
        # 看不清小车时为了安全：没有位置就无法判断离危险区多远，保守停车，
        # 等 ArUco 重新识别到再说；绝不能在"不知道车在哪"时继续往前开。
        return Decision("s", "小车定位丢失，停车等待重新识别", None)

    (car_cx, car_cy), _ = car_loc

    # 选出离小车最近的一张纸
    best = None      # (dist, kind, cx, cy, area, bbox)
    for z in zones:
        kind, (cx, cy), area, bbox = z[0], z[1], z[2], z[3]
        dist = _point_to_paper_edge_dist(car_cx, car_cy, bbox)
        if best is None or dist < best[0]:
            best = (dist, kind, cx, cy, area, bbox)

    if best is None:
        return Decision("f", "前方未检测到水源/坑，直行", None)

    dist, kind, cx, cy, area, bbox = best
    if dist <= radius:
        zname = {"water": "水源区", "pit": "坑", "collapse": "倒塌区"}.get(kind, kind)
        return Decision("s", f"小车距{zname}约"
                        f"{max(0, int(dist/config.PIXELS_PER_CM))}cm，进入2cm警戒区，停车研判",
                        (kind, cx, cy, area, bbox))

    return Decision("f", "前方水源/坑尚远，直行", None)
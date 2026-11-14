"""检测层单测：用合成画面验证去噪逻辑（不用真摄像头）。

跑法（仓库根目录）：
    python -m pytest software/tests -q

画面是 PROC 分辨率（480x270）的纯色色块，BGR 取值落在 config.py 的
HSV 范围内：水源 (200,140,40)、坑 (0,0,255)、倒塌区 (128,0,255)。
"""
import cv2
import numpy as np
import pytest

import config
import detection
from detection import detect, reset_zone_tracker

W, H = config.PROC_W, config.PROC_H

WATER_BGR = (200, 140, 40)      # 青蓝 -> 水源区
PIT_BGR = (0, 0, 255)           # 红 -> 坑
COLLAPSE_BGR = (128, 0, 255)    # 紫 -> 倒塌区


@pytest.fixture(autouse=True)
def _fresh_tracker():
    """每个用例都从干净的跨帧记忆开始，避免互相干扰。"""
    reset_zone_tracker()
    yield
    reset_zone_tracker()


def _frame():
    return np.zeros((H, W, 3), dtype=np.uint8)


def _rect(frame, x, y, w, h, color):
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, -1)
    return frame


def _detect_twice(frame):
    """跨帧稳定要求连续出现 2 帧：同一画面连测两次，取第二次的结果。"""
    detect(frame)
    zones, _ = detect(frame)
    return zones


def _kinds(zones):
    return sorted(z[0] for z in zones)


def test_three_real_papers_detected():
    """三张正常大小的色纸：三种都要认出来，各一个区。"""
    f = _frame()
    _rect(f, 30, 30, 80, 60, WATER_BGR)
    _rect(f, 200, 40, 80, 60, PIT_BGR)
    _rect(f, 350, 30, 80, 60, COLLAPSE_BGR)
    zones = _detect_twice(f)
    assert _kinds(zones) == ["collapse", "pit", "water"]


def test_small_speckle_ignored():
    """8x8 的小斑点（反光、碎点）：面积不够，直接丢掉。"""
    f = _frame()
    _rect(f, 100, 100, 8, 8, PIT_BGR)
    _rect(f, 300, 100, 8, 8, WATER_BGR)
    assert _detect_twice(f) == []


def test_thin_line_rejected():
    """200x6 的细长红条（线缆、桌边反光）：面积够但长宽比离谱，不要。"""
    f = _frame()
    _rect(f, 50, 100, 200, 6, PIT_BGR)
    assert _detect_twice(f) == []


def test_split_paper_merged():
    """一张纸被光照劈成两块（中间 10px 缝）：合并成一个区。"""
    f = _frame()
    _rect(f, 100, 80, 60, 60, PIT_BGR)
    _rect(f, 170, 80, 60, 60, PIT_BGR)
    zones = _detect_twice(f)
    assert len(zones) == 1 and zones[0][0] == "pit"


def test_per_kind_cap():
    """8 张分散的水源纸（两行，每张之间隔 80px，不触发合并）：每种颜色只留面积最大的 6 个。"""
    f = _frame()
    for row, y in enumerate((30, 130)):
        for col, x in enumerate((10, 130, 250, 370)):
            _rect(f, x, y, 40, 40, WATER_BGR)
    zones = _detect_twice(f)
    assert len(zones) == config.ZONE_MAX_PER_KIND
    assert all(z[0] == "water" for z in zones)


def test_single_frame_flicker_ignored():
    """只出现一帧的斑点：跨帧稳定把它拦下来，第一帧不算数。"""
    f = _frame()
    _rect(f, 100, 80, 80, 60, PIT_BGR)
    zones_first, _ = detect(f)
    assert zones_first == []
    zones_second, _ = detect(f)
    assert len(zones_second) == 1


def test_roi_excludes_outside():
    """ROI 只框左半边：右半边的纸不进检测；ROI 撤掉后又能测到。"""
    f = _frame()
    _rect(f, 350, 80, 80, 60, PIT_BGR)
    config.ROI = (0, 0, 200, H)
    try:
        assert _detect_twice(f) == []
    finally:
        config.ROI = None
    assert len(_detect_twice(f)) == 1


def test_car_exclusion_zone():
    """小车自身区域（黄轮子）被扣掉：车身处的红色不算坑。"""
    f = _frame()
    _rect(f, 200, 100, 90, 90, PIT_BGR)  # 一大片红，正好盖住小车位置
    car_loc = ((245, 145), 500)
    zones, _ = detect(f, exclude_car=car_loc)
    zones, _ = detect(f, exclude_car=car_loc)
    assert zones == []

"""决策层单测：验证"停车研判"的触发条件。

规则（见 decision.py）：
- 小车进入任一色纸 2cm 警戒框 -> s（停车研判）；
- 小车定位丢失 -> s（停车等待重新识别）；
- 否则 -> f（直行）。
"""
from decision import decide

_ZONE_PIT = ("pit", (100, 100), 500, (80, 80, 40, 40))
_ZONE_COLLAPSE = ("collapse", (300, 100), 900, (270, 70, 60, 60))


def test_car_inside_danger_zone_stops():
    """小车中心已进入坑的警戒框：停车。"""
    d = decide(((100, 100), 500), [_ZONE_PIT])
    assert d.action == "s"
    assert d.zone[0] == "pit"


def test_car_far_away_goes():
    """小车离坑很远：直行。"""
    d = decide(((300, 300), 500), [_ZONE_PIT])
    assert d.action == "f"


def test_no_zones_goes():
    """画面里没有危险区：直行。"""
    assert decide(((100, 100), 500), []).action == "f"


def test_lost_car_stops():
    """定位丢失：不知道车在哪，保守停车（绝不能盲开）。"""
    d = decide(None, [_ZONE_PIT])
    assert d.action == "s"
    assert d.zone is None


def test_collapse_zone_named_correctly():
    """倒塌区触发时，原因文案里必须是"倒塌区"（不是"水源区"）。"""
    d = decide(((300, 100), 900), [_ZONE_COLLAPSE])
    assert d.action == "s"
    assert "倒塌区" in d.reason

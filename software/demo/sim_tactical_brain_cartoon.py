import heapq
import os
import threading
import time
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# 0. 窗口全局配置与 DeepSeek API
# ==========================================
WINDOW_NAME = "Rescue Copilot - Tactical Command Center"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")  # 只从环境变量读取，绝不写进代码/仓库  # 你的 Key
DEEPSEEK_BASE_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

LLM_ANALYSIS_TEXT = "战术参谋就绪：等待空地协同指令..."
IS_WAITING_HUMAN = False
HUMAN_PROMPT_MSG = ""
IS_FULLSCREEN = True


def call_deepseek_tactical(zone_name, hazard_desc):
    global LLM_ANALYSIS_TEXT
    if not DEEPSEEK_API_KEY:
        time.sleep(0.4)
        fallbacks = {
            "暗坑区": "战术参谋研判：暗坑深部存在未知空洞。建议：选方案1绕行；若选方案2直穿务必开启探照强攻。",
            "危墙区": "物理计算：危墙高3.5m，倒塌方向指向左下，致死圈<4.5m。强烈建议：批准8米外安全走廊！",
            "泥泞积水": "语义研判：水深未知，淤泥附着极差，直穿存在底盘受困打滑风险。建议走方案1稳健绕行！",
        }
        for k, v in fallbacks.items():
            if k in zone_name:
                LLM_ANALYSIS_TEXT = v
                return
        LLM_ANALYSIS_TEXT = (
            f"战术参谋研判：已规避{zone_name}风险面，航线受控推进。"
        )
        return

    try:
        import requests

        prompt = (
            f"你是一名特种搜救战术参谋。微观工兵即将处置【{zone_name}】。"
            f"现场灾情：{hazard_desc}。"
            f"请以极简练军用口吻提报通行风险研判（35字以内，不要提具体数字速度，讲清楚可能遇到的未知地质风险与方案推荐）。"
        )
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "你是特种搜救战术参谋，重点做语义地质风险研判，不编造机械数字。",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 80,
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            DEEPSEEK_BASE_URL, headers=headers, json=payload, timeout=3.0
        )
        data = resp.json()
        LLM_ANALYSIS_TEXT = data["choices"][0]["message"]["content"].strip()
    except Exception:
        LLM_ANALYSIS_TEXT = (
            f"参谋离线研判：规避[{zone_name}]核心致死面，建议执行稳健方案。"
        )


# ==========================================
# 1. 字体缓存引擎与专属工兵渲染器
# ==========================================
FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
if not os.path.exists(FONT_PATH):
    FONT_PATH = "C:/Windows/Fonts/simhei.ttf"

GLOBAL_FONTS = {}
for size in [12, 13, 14, 15, 16, 18, 20, 22]:
    try:
        GLOBAL_FONTS[size] = ImageFont.truetype(FONT_PATH, size)
    except Exception:
        GLOBAL_FONTS[size] = ImageFont.load_default()


def draw_text_cn(img, text, pos, font_size=18, color=(255, 255, 255)):
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    font = GLOBAL_FONTS.get(font_size, GLOBAL_FONTS[18])
    draw.text(pos, text, font=font, fill=(color[2], color[1], color[0]))
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def draw_text_multiline_cn(
    img, text, pos, max_width=390, font_size=15, color=(0, 255, 255)
):
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    font = GLOBAL_FONTS.get(font_size, GLOBAL_FONTS[15])

    final_lines = []
    paragraphs = str(text).split("\n")
    for para in paragraphs:
        line = ""
        for char in para:
            if draw.textlength(line + char, font=font) <= max_width:
                line += char
            else:
                final_lines.append(line)
                line = char
        if line:
            final_lines.append(line)

    x, y = pos
    for l in final_lines:
        draw.text((x, y), l, font=font, fill=(color[2], color[1], color[0]))
        y += font_size + 6
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def draw_car_badge_text(img, text, pos, color=(0, 0, 255)):
    """精致自适应黑底战术标牌，绝不压在车顶"""
    x, y = pos
    # 画紧凑黑底框
    cv2.rectangle(img, (x - 6, y - 4), (x + 340, y + 24), (20, 20, 20), -1)
    cv2.rectangle(img, (x - 6, y - 4), (x + 340, y + 24), color, 1)
    return draw_text_cn(img, text, (x, y), 13, color)


def draw_scout_car(
    img,
    car_pos,
    is_waiting=False,
    is_alert=False,
    is_wading=False,
    is_tunnel=False,
    is_damaged=False,
    is_traditional=False,
):
    cx, cy = int(car_pos[0]), int(car_pos[1])

    # 1. 穿暗坑模式：车头强光探照
    if is_tunnel:
        light_pts = np.array(
            [[cx, cy], [cx + 35, cy - 15], [cx + 45, cy + 20]], np.int32
        )
        overlay = img.copy()
        cv2.fillPoly(overlay, [light_pts], (100, 255, 255))
        cv2.addWeighted(overlay, 0.4, img, 0.6, 0, img)
        img = draw_text_cn(
            img, "[坑道直穿探照中]", (cx - 45, cy - 35), 12, (0, 255, 255)
        )

    # 2. 涉水模式（只显示水花涟漪与语义状态，不提具体速度）
    if is_wading:
        cv2.circle(img, (cx, cy), 22, (255, 180, 50), 2, cv2.LINE_AA)
        if not is_traditional:
            cv2.rectangle(
                img, (cx - 55, cy - 38), (cx + 55, cy - 18), (20, 20, 20), -1
            )
            cv2.rectangle(
                img, (cx - 55, cy - 38), (cx + 55, cy - 18), (0, 200, 255), 1
            )
            img = draw_text_cn(
                img, "泥泞涉水行进中", (cx - 42, cy - 36), 12, (255, 255, 255)
            )

    # 3. 传统车受损冒烟
    if is_damaged:
        cv2.circle(img, (cx - 10, cy - 15), 6, (80, 80, 80), -1)
        cv2.circle(img, (cx - 16, cy - 22), 9, (120, 120, 120), -1)

    if is_alert or is_damaged:
        beacon_color = (0, 0, 255)
    elif is_waiting:
        beacon_color = (0, 255, 255)
    else:
        beacon_color = (255, 200, 0)

    cv2.circle(img, (cx, cy), 18, beacon_color, 2)
    cv2.rectangle(
        img, (cx - 14, cy - 14), (cx + 14, cy + 14), (255, 255, 255), -1
    )
    cv2.rectangle(img, (cx - 12, cy - 12), (cx + 12, cy + 12), (0, 0, 0), -1)
    center_color = (0, 0, 255) if (is_alert or is_damaged) else (0, 255, 0)
    cv2.rectangle(
        img, (cx - 6, cy - 6), (cx + 6, cy + 6), center_color, -1
    )

    if is_waiting:
        cv2.drawMarker(
            img, (cx, cy), (0, 255, 255), cv2.MARKER_CROSS, 36, 1, cv2.LINE_AA
        )
        img = draw_text_cn(
            img, "[工兵定格待命]", (cx - 45, cy - 35), 13, (0, 255, 255)
        )
    return img


# ==========================================
# 2. 空间布局与物理倒塌模型
# ==========================================
WALL_CENTER = (380, 210)
RADIUS_LETHAL = 65
RADIUS_SAFE = 135


def create_base_environment(width=800, height=600):
    img = np.ones((height, width, 3), dtype=np.uint8) * 240
    cv2.circle(img, (200, 155), 45, (10, 10, 10), -1)
    wall_pts = np.array(
        [[340, 160], [420, 150], [440, 240], [360, 250]], np.int32
    )
    cv2.fillPoly(img, [wall_pts], (20, 210, 240))
    water_pts = np.array(
        [[520, 390], [620, 360], [650, 460], [550, 480]], np.int32
    )
    cv2.fillPoly(img, [water_pts], (220, 150, 30))
    return img


def advanced_risk_partitioning(img):
    h, w, _ = img.shape
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    cost_map = np.ones((h, w), dtype=np.float32)

    mask_black = cv2.inRange(hsv, (0, 0, 0), (180, 255, 60))
    cost_map[mask_black > 0] = 9999.0

    mask_blue = cv2.inRange(hsv, (95, 100, 80), (130, 255, 255))
    cost_map[mask_blue > 0] = 8.0

    cv2.circle(cost_map, WALL_CENTER, RADIUS_LETHAL, 9999.0, -1)
    buf_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(buf_mask, WALL_CENTER, RADIUS_SAFE, 1, -1)
    cost_map[(buf_mask > 0) & (cost_map < 9999)] = 60.0

    cost_map[0:150, 260:500] = 9999.0
    return cost_map


def astar_planner(cost_map, start, goal, scale=5):
    h, w = cost_map.shape
    sh, sw = h // scale, w // scale
    small_cost = cv2.resize(
        cost_map, (sw, sh), interpolation=cv2.INTER_NEAREST
    )
    sx, sy = int(start[0] // scale), int(start[1] // scale)
    gx, gy = int(goal[0] // scale), int(goal[1] // scale)

    sx, sy = max(0, min(sw - 1, sx)), max(0, min(sh - 1, sy))
    gx, gy = max(0, min(sw - 1, gx)), max(0, min(sh - 1, gy))
    small_cost[sy, sx] = 1.0

    open_set = []
    heapq.heappush(open_set, (0, sx, sy))
    came_from = {}
    g_score = {(sx, sy): 0}
    dirs = [
        (1, 0),
        (-1, 0),
        (0, 1),
        (0, -1),
        (1, 1),
        (-1, 1),
        (1, -1),
        (-1, -1),
    ]

    while open_set:
        _, cx, cy = heapq.heappop(open_set)
        if (cx, cy) == (gx, gy):
            break
        for dx, dy in dirs:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < sw and 0 <= ny < sh:
                c = small_cost[ny, nx]
                if c >= 9999:
                    continue
                step = 1.414 if (dx != 0 and dy != 0) else 1.0
                tentative_g = g_score[(cx, cy)] + step * c
                if (nx, ny) not in g_score or tentative_g < g_score[(nx, ny)]:
                    g_score[(nx, ny)] = tentative_g
                    h_val = np.hypot(nx - gx, ny - gy)
                    heapq.heappush(open_set, (tentative_g + h_val, nx, ny))
                    came_from[(nx, ny)] = (cx, cy)

    if (gx, gy) not in came_from:
        return np.array([start, goal], dtype=np.int32)

    curr = (gx, gy)
    path = []
    while curr in came_from:
        path.append([curr[0] * scale, curr[1] * scale])
        curr = came_from[curr]
    path.append([start[0], start[1]])
    path.reverse()
    return np.array(path, dtype=np.int32)


# ==========================================
# 3. 战术大屏 HUD（⭐ 彻底删除右上角巡航速度）
# ==========================================
def render_chinese_hud(
    stage_title,
    status_text,
    status_color,
    current_sector,
    is_alert=False,
    is_traditional=False,
):
    panel = np.zeros((600, 440, 3), dtype=np.uint8)
    if is_alert:
        cv2.rectangle(panel, (0, 0), (439, 599), (0, 0, 255), 6)

    # 顶栏
    panel = draw_text_cn(panel, stage_title, (20, 15), 18, (0, 255, 120))
    cv2.line(panel, (20, 45), (420, 45), (60, 60, 60), 1)

    # ⭐ 彻底清除巡航速度！只保留核心态势与区域研判
    panel = draw_text_cn(
        panel, f"系统状态: {status_text}", (20, 65), 16, status_color
    )

    cv2.line(panel, (20, 105), (420, 105), (60, 60, 60), 1)
    panel = draw_text_cn(
        panel, "【当前战术责任分析区】", (20, 120), 16, (180, 180, 180)
    )
    panel = draw_text_cn(panel, f"目标区域: {current_sector}", (25, 155), 15, (0, 200, 255))

    cv2.line(panel, (20, 195), (420, 195), (60, 60, 60), 1)
    panel = draw_text_cn(
        panel, "【战术参谋研判报告】", (20, 210), 16, (0, 255, 255)
    )
    panel = draw_text_multiline_cn(
        panel,
        LLM_ANALYSIS_TEXT,
        (20, 240),
        max_width=400,
        font_size=15,
        color=(0, 255, 255),
    )

    cv2.line(panel, (20, 360), (420, 360), (60, 60, 60), 1)

    # 底部控制流状态
    if is_traditional:
        panel = draw_text_cn(
            panel, "【传统控制流架构缺陷】", (20, 375), 16, (180, 180, 180)
        )
        panel = draw_text_cn(
            panel, "● 纯几何开环运行，无战术参谋", (25, 415), 14, (160, 160, 160)
        )
        panel = draw_text_cn(
            panel, "● 零人工决策介入", (25, 445), 14, (0, 150, 255)
        )
        panel = draw_text_cn(
            panel, "● 致命缺陷：缺乏语义感知，盲目前进", (25, 475), 13, (0, 0, 255)
        )
    else:
        panel = draw_text_cn(
            panel, "【指挥官决策介入】", (20, 375), 16, (0, 180, 255)
        )
        if IS_WAITING_HUMAN:
            cv2.rectangle(panel, (15, 405), (425, 535), (0, 140, 255), 2)
            panel = draw_text_multiline_cn(
                panel,
                HUMAN_PROMPT_MSG,
                (25, 415),
                max_width=390,
                font_size=13,
                color=(0, 255, 0),
            )
            panel = draw_text_cn(
                panel,
                "[系统定格待命] 请指挥官按键授权...",
                (25, 510),
                13,
                (0, 165, 255),
            )
        else:
            panel = draw_text_cn(
                panel,
                "● 指挥官已下发授权，工兵推进中",
                (25, 430),
                14,
                (0, 255, 0),
            )
            panel = draw_text_cn(
                panel,
                "● 运行模式：人机协同闭环 (AI研判 -> 人决策)",
                (25, 460),
                13,
                (160, 160, 160),
            )

    panel = draw_text_cn(
        panel,
        "[F键:切换全屏/窗口 | R键:重播 | ESC:退出]",
        (20, 565),
        12,
        (120, 120, 120),
    )
    return panel


# ==========================================
# 4. 全流程实战仿真
# ==========================================
def run_full_pipeline():
    global LLM_ANALYSIS_TEXT, IS_WAITING_HUMAN, HUMAN_PROMPT_MSG, IS_FULLSCREEN, DEEPSEEK_API_KEY
    if not DEEPSEEK_API_KEY:  # 没设环境变量时，启动问一次 Key（回车跳过）
        try:
            DEEPSEEK_API_KEY = input("请输入 DeepSeek Key（直接回车跳过，不用在线研判）: ").strip()
        except (EOFError, KeyboardInterrupt):
            DEEPSEEK_API_KEY = ""
    start_pos = (50, 50)
    goal_pos = (740, 530)

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    if IS_FULLSCREEN:
        cv2.setWindowProperty(
            WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN
        )

    base_map = create_base_environment()
    cost_map = advanced_risk_partitioning(base_map)

    # 1. 传统最短路
    steps = 140
    red_path = np.array(
        [
            [
                int(start_pos[0] + (goal_pos[0] - start_pos[0]) * i / steps),
                int(start_pos[1] + (goal_pos[1] - start_pos[1]) * i / steps),
            ]
            for i in range(steps + 1)
        ],
        dtype=np.int32,
    )

    # 2. 本系统绿线
    green_path = astar_planner(cost_map, start_pos, goal_pos)

    # ------------------------------------------------------------------
    # 阶段一：传统纯直线盲目硬闯
    # ------------------------------------------------------------------
    LLM_ANALYSIS_TEXT = (
        "传统系统告警：纯欧式几何直线寻路，无视一切灾害地形！"
    )
    IS_WAITING_HUMAN = False
    is_red_damaged = False
    is_red_wading = False

    for idx, pos in enumerate(red_path):
        frame = base_map.copy()
        cv2.polylines(
            frame,
            [red_path],
            False,
            (0, 0, 220),
            3,
            cv2.LINE_AA,
        )

        dist_to_pit = np.hypot(pos[0] - 200, pos[1] - 155)
        if dist_to_pit < 45:
            LLM_ANALYSIS_TEXT = "传统红车告警：直接碾压穿入关卡1塌陷暗坑！强行硬闯！"

        dist_to_wall = np.hypot(pos[0] - WALL_CENTER[0], pos[1] - WALL_CENTER[1])
        if dist_to_wall < RADIUS_LETHAL and not is_red_damaged:
            is_red_damaged = True
            LLM_ANALYSIS_TEXT = "余震爆发！危墙向左下倒塌！传统红车处于4.5米致死圈内被砸中！车体受损冒烟！"

            for collapse_step in range(18):
                c_frame = frame.copy()
                debris_poly = np.array(
                    [
                        [340, 160],
                        [420, 150],
                        [pos[0] + 25, pos[1] - 15],
                        [pos[0] - 25, pos[1] + 25],
                    ],
                    np.int32,
                )
                cv2.fillPoly(c_frame, [debris_poly], (15, 160, 200))
                cv2.circle(
                    c_frame,
                    (pos[0], pos[1]),
                    25 + collapse_step * 2,
                    (100, 100, 100),
                    2,
                )
                c_frame = draw_text_cn(
                    c_frame,
                    "💥 闯入4.5米致死圈被砸！",
                    (pos[0] - 100, pos[1] - 40),
                    16,
                    (0, 0, 255),
                )
                c_frame = draw_scout_car(
                    c_frame, pos, is_damaged=True, is_traditional=True
                )
                hud_fail = render_chinese_hud(
                    "【阶段一：传统纯直线盲目硬闯】",
                    "【被砸中！强行硬抗】",
                    (0, 0, 255),
                    "关卡2: 危墙倒塌砸毁车体",
                    is_alert=True,
                    is_traditional=True,
                )
                cv2.imshow(
                    WINDOW_NAME, np.hstack((c_frame, hud_fail))
                )
                cv2.waitKey(30)

            time.sleep(0.4)

        dist_to_water = np.hypot(pos[0] - 580, pos[1] - 420)
        if dist_to_water < 55:
            is_red_wading = True
            LLM_ANALYSIS_TEXT = "告警：无视附着力直接涉水冲切！打滑推进！"
        else:
            is_red_wading = False

        frame = draw_scout_car(
            frame,
            pos,
            is_damaged=is_red_damaged,
            is_wading=is_red_wading,
            is_traditional=True,
        )

        status_msg = "纯直线硬抗行进中" if not is_red_damaged else "带伤冒烟强行开向终点"
        hud = render_chinese_hud(
            "【阶段一：传统纯直线盲目硬闯】",
            status_msg,
            (0, 150, 255) if not is_red_damaged else (0, 0, 255),
            "直线穿坑 -> 被砸受损 -> 涉水直冲",
            is_traditional=True,
        )
        cv2.imshow(
            WINDOW_NAME, np.hstack((frame, hud))
        )

        k = cv2.waitKey(20) & 0xFF
        if k == 27:
            return
        elif k == ord("f") or k == ord("F"):
            IS_FULLSCREEN = not IS_FULLSCREEN
            cv2.setWindowProperty(
                WINDOW_NAME,
                cv2.WND_PROP_FULLSCREEN,
                cv2.WINDOW_FULLSCREEN if IS_FULLSCREEN else cv2.WINDOW_NORMAL,
            )

    # 阶段一结束定格，等待 Enter
    LLM_ANALYSIS_TEXT = "阶段一演练完毕：一路踩坑、挨砸受损。请指挥官按【Enter】切入阶段二！"

    while True:
        end_frame = base_map.copy()
        cv2.polylines(
            end_frame,
            [red_path],
            False,
            (0, 0, 220),
            3,
            cv2.LINE_AA,
        )
        end_frame = draw_scout_car(
            end_frame,
            goal_pos,
            is_damaged=True,
            is_wading=False,
            is_traditional=True,
        )

        cv2.rectangle(
            end_frame, (120, 220), (680, 360), (15, 15, 15), -1
        )
        cv2.rectangle(
            end_frame, (120, 220), (680, 360), (0, 215, 255), 2
        )
        end_frame = draw_text_cn(
            end_frame,
            "【阶段一：传统算法演练结束】",
            (240, 235),
            18,
            (0, 215, 255),
        )
        end_frame = draw_text_cn(
            end_frame,
            "● 穿透暗坑底盘受损  ● 闯入4.5m致死圈被砸  ● 涉水打滑陷车",
            (145, 275),
            14,
            (200, 200, 200),
        )
        end_frame = draw_text_cn(
            end_frame,
            "● 请现场指挥官按下键盘【Enter 回车键】切换阶段二演示...",
            (145, 315),
            15,
            (0, 255, 120),
        )

        hud_end = render_chinese_hud(
            "【阶段一：演练结束】",
            "【等待指挥官敲回车】",
            (0, 215, 255),
            "传统对比测试完成",
            is_traditional=True,
        )
        cv2.imshow(
            WINDOW_NAME, np.hstack((end_frame, hud_end))
        )

        k = cv2.waitKey(50) & 0xFF
        if k == 13:
            break
        elif k == 27:
            return
        elif k == ord("f") or k == ord("F"):
            IS_FULLSCREEN = not IS_FULLSCREEN
            cv2.setWindowProperty(
                WINDOW_NAME,
                cv2.WND_PROP_FULLSCREEN,
                cv2.WINDOW_FULLSCREEN if IS_FULLSCREEN else cv2.WINDOW_NORMAL,
            )

    # ------------------------------------------------------------------
    # 阶段二：本系统接管
    # ------------------------------------------------------------------
    active_path = green_path.tolist()
    car_pos = list(start_pos)
    car_idx = 0
    current_sector_name = "起步出航区"

    is_wading_mode = False
    is_tunnel_mode = False

    decision_zone1_done = False
    decision_zone2_done = False
    decision_zone3_done = False

    while True:
        frame = base_map.copy()

        frame = draw_text_cn(
            frame, "【分析区1: 塌陷暗坑】", (90, 105), 14, (100, 100, 100)
        )
        frame = draw_text_cn(
            frame, "【分析区2: 倾斜危墙】", (330, 45), 14, (0, 140, 255)
        )
        frame = draw_text_cn(
            frame, "【分析区3: 泥泞积水】", (520, 310), 14, (255, 150, 0)
        )

        overlay = frame.copy()
        cv2.circle(overlay, WALL_CENTER, RADIUS_SAFE, (0, 200, 255), -1)
        cv2.circle(overlay, WALL_CENTER, RADIUS_LETHAL, (0, 0, 255), -1)
        cv2.addWeighted(overlay, 0.28, frame, 0.72, 0, frame)

        cv2.circle(frame, WALL_CENTER, RADIUS_LETHAL, (0, 0, 255), 2, cv2.LINE_AA)
        cv2.circle(frame, WALL_CENTER, RADIUS_SAFE, (0, 255, 120), 2, cv2.LINE_AA)

        cv2.arrowedLine(
            frame,
            WALL_CENTER,
            (WALL_CENTER[0] - 65, WALL_CENTER[1] + 65),
            (0, 0, 255),
            3,
            tipLength=0.25,
        )
        frame = draw_text_cn(
            frame, "倒塌方向", (WALL_CENTER[0] - 110, WALL_CENTER[1] + 25), 13, (0, 0, 255)
        )
        frame = draw_text_cn(
            frame,
            "● <4.5米: 倒塌致死圈(禁行)",
            (WALL_CENTER[0] - 90, WALL_CENTER[1] + 80),
            12,
            (0, 0, 255),
        )
        frame = draw_text_cn(
            frame,
            "● >8.0米: 二次飞溅安全圈(绿色航线)",
            (WALL_CENTER[0] - 120, WALL_CENTER[1] + 120),
            13,
            (0, 220, 0),
        )

        cv2.polylines(frame, [red_path], False, (0, 0, 160), 1, cv2.LINE_AA)

        if not IS_WAITING_HUMAN and len(active_path) > 1:
            cv2.polylines(
                frame,
                [np.array(active_path, dtype=np.int32)],
                False,
                (0, 240, 0),
                4,
                cv2.LINE_AA,
            )

        # 关卡 1：暗坑区
        if not decision_zone1_done and car_pos[0] >= 105:
            call_deepseek_tactical("暗坑区", "地表塌陷暗坑，土壤松散脆弱")
            current_sector_name = "1号暗坑决策点"

            cost_z1_safe = cost_map.copy()
            cv2.circle(cost_z1_safe, (200, 155), 70, 9999.0, -1)
            path_z1_safe = astar_planner(cost_z1_safe, car_pos, goal_pos)

            cost_z1_tunnel = cost_map.copy()
            cv2.circle(cost_z1_tunnel, (200, 155), 50, 1.0, -1)
            path_z1_tunnel = astar_planner(cost_z1_tunnel, car_pos, goal_pos)

            IS_WAITING_HUMAN = True
            HUMAN_PROMPT_MSG = (
                "【暗坑区·决策选项呈递】：\n"
                "• 按键 [1] 或 [空格]：方案1 (绿色外围大弧度避险,安全推荐)\n"
                "• 按键 [2]：方案2 (橙色直接进入地下坑道穿切,冒险省时)"
            )

            while True:
                p_frame = frame.copy()
                p_frame = draw_scout_car(
                    p_frame, car_pos, is_waiting=True, is_traditional=False
                )

                cv2.polylines(
                    p_frame,
                    [path_z1_tunnel],
                    False,
                    (0, 165, 255),
                    3,
                    cv2.LINE_AA,
                )
                cv2.polylines(
                    p_frame,
                    [path_z1_safe],
                    False,
                    (0, 240, 0),
                    3,
                    cv2.LINE_AA,
                )
                p_frame = draw_car_badge_text(
                    p_frame,
                    "方案1(绿:大避让) vs 方案2(橙:直穿坑道)",
                    (car_pos[0] + 15, car_pos[1] - 30),
                    color=(0, 0, 255),
                )

                hud_pause = render_chinese_hud(
                    "【人在回路·第1关暗坑研判】",
                    "【等待指挥官批复】",
                    (0, 180, 255),
                    current_sector_name,
                    is_traditional=False,
                )
                cv2.imshow(
                    WINDOW_NAME, np.hstack((p_frame, hud_pause))
                )

                k = cv2.waitKey(50) & 0xFF
                if k == ord("1") or k == 32:
                    active_path = path_z1_safe.tolist()
                    car_idx = 0
                    decision_zone1_done = True
                    is_tunnel_mode = False
                    IS_WAITING_HUMAN = False
                    LLM_ANALYSIS_TEXT = (
                        "指挥中心批准方案1：外围大弧度避险！绕开地表坍塌区！"
                    )
                    break
                elif k == ord("2"):
                    active_path = path_z1_tunnel.tolist()
                    car_idx = 0
                    decision_zone1_done = True
                    is_tunnel_mode = True
                    IS_WAITING_HUMAN = False
                    LLM_ANALYSIS_TEXT = (
                        "指挥中心批准方案2：直接进入坑道穿行！开启探照灯强攻推进！"
                    )
                    break
                elif k == 27:
                    return
                elif k == ord("f") or k == ord("F"):
                    IS_FULLSCREEN = not IS_FULLSCREEN
                    cv2.setWindowProperty(
                        WINDOW_NAME,
                        cv2.WND_PROP_FULLSCREEN,
                        cv2.WINDOW_FULLSCREEN
                        if IS_FULLSCREEN
                        else cv2.WINDOW_NORMAL,
                    )

        # 关卡 2：危墙区
        if (
            decision_zone1_done
            and not decision_zone2_done
            and car_pos[0] >= 195
        ):
            call_deepseek_tactical("危墙区", "危墙高3.5米，倒塌方向指向左下，致死圈4.5米")
            current_sector_name = "2号危墙决策点"

            cost_z2_safe = cost_map.copy()
            path_z2_safe = astar_planner(cost_z2_safe, car_pos, goal_pos)

            cost_z2_risky = np.ones_like(cost_map)
            cv2.circle(cost_z2_risky, WALL_CENTER, RADIUS_LETHAL, 9999.0, -1)
            cost_z2_risky[320:600, 0:500] = 50.0
            path_z2_risky = astar_planner(cost_z2_risky, car_pos, goal_pos)

            IS_WAITING_HUMAN = True
            HUMAN_PROMPT_MSG = (
                "【危墙物理量化·决策呈递】：\n"
                "• 按键 [1] 或 [空格]：方案1 (绿色绕出8.0m圆外,绝对安全,推荐)\n"
                "• 按键 [2]：方案2 (红色切入4.5m~8.0m内冒险贴墙走)"
            )

            while True:
                p_frame = frame.copy()
                p_frame = draw_scout_car(
                    p_frame, car_pos, is_waiting=True, is_traditional=False
                )

                cv2.polylines(
                    p_frame,
                    [path_z2_risky],
                    False,
                    (0, 0, 255),
                    3,
                    cv2.LINE_AA,
                )
                cv2.polylines(
                    p_frame,
                    [path_z2_safe],
                    False,
                    (0, 240, 0),
                    3,
                    cv2.LINE_AA,
                )
                p_frame = draw_car_badge_text(
                    p_frame,
                    "方案1(绿:8米外安全圈) vs 方案2(红:贴墙冒进)",
                    (car_pos[0] + 15, car_pos[1] - 30),
                    color=(0, 0, 255),
                )

                hud_pause = render_chinese_hud(
                    "【人在回路·第2关危墙研判】",
                    "【等待指挥官批复】",
                    (0, 180, 255),
                    current_sector_name,
                    is_traditional=False,
                )
                cv2.imshow(
                    WINDOW_NAME, np.hstack((p_frame, hud_pause))
                )

                k = cv2.waitKey(50) & 0xFF
                if k == ord("1") or k == 32:
                    active_path = path_z2_safe.tolist()
                    car_idx = 0
                    decision_zone2_done = True
                    is_tunnel_mode = False
                    IS_WAITING_HUMAN = False
                    LLM_ANALYSIS_TEXT = (
                        "指挥中心批准方案1：沿8.0米安全线绕行！确保安全净空！"
                    )
                    break
                elif k == ord("2"):
                    active_path = path_z2_risky.tolist()
                    car_idx = 0
                    decision_zone2_done = True
                    is_tunnel_mode = False
                    IS_WAITING_HUMAN = False
                    LLM_ANALYSIS_TEXT = (
                        "指挥中心批准方案2：切入外缘冒进！注意墙体形变！"
                    )
                    break
                elif k == 27:
                    return
                elif k == ord("f") or k == ord("F"):
                    IS_FULLSCREEN = not IS_FULLSCREEN
                    cv2.setWindowProperty(
                        WINDOW_NAME,
                        cv2.WND_PROP_FULLSCREEN,
                        cv2.WINDOW_FULLSCREEN
                        if IS_FULLSCREEN
                        else cv2.WINDOW_NORMAL,
                    )

        # ==============================================================
        # ⭐ 关卡 3：泥泞积水区（基于语义与未知风险的研判，彻底移除假数字）
        # ==============================================================
        if (
            decision_zone2_done
            and not decision_zone3_done
            and car_pos[0] >= 470
        ):
            call_deepseek_tactical("泥泞积水", "内涝积水深浅未知，地质附着力极低，存在陷车断电风险")
            current_sector_name = "3号积水决策点"

            cost_z3_safe = cost_map.copy()
            cv2.circle(cost_z3_safe, (580, 420), 85, 9999.0, -1)
            path_z3_safe = astar_planner(cost_z3_safe, car_pos, goal_pos)

            cost_z3_wading = cost_map.copy()
            cost_z3_wading[cost_z3_wading == 8.0] = 1.0
            path_z3_wading = astar_planner(
                cost_z3_wading, car_pos, goal_pos
            )

            IS_WAITING_HUMAN = True
            # ⭐ 核心修正：文字基于“未知地质风险”，不再编造假速度，字框绝不遮挡小车！
            HUMAN_PROMPT_MSG = (
                "【积水地质研判·决策呈递】：\n"
                "• 按键 [1] 或 [空格]：方案1 (绿色绕水大走廊,规避未知深水,推荐)\n"
                "• 按键 [2]：方案2 (蓝色强行涉水直穿,有打滑受困未知风险)"
            )

            while True:
                p_frame = frame.copy()
                p_frame = draw_scout_car(
                    p_frame, car_pos, is_waiting=True, is_traditional=False
                )

                cv2.polylines(
                    p_frame,
                    [path_z3_wading],
                    False,
                    (255, 100, 0),
                    3,
                    cv2.LINE_AA,
                )
                cv2.polylines(
                    p_frame,
                    [path_z3_safe],
                    False,
                    (0, 240, 0),
                    3,
                    cv2.LINE_AA,
                )

                # ⭐ 位置调整至小车上方偏左，绝不遮盖小车身形！
                p_frame = draw_car_badge_text(
                    p_frame,
                    "方案1(绿:外缘绕水·避险) vs 方案2(蓝:强行涉水·有风险)",
                    (car_pos[0] - 160, car_pos[1] - 40),
                    color=(0, 0, 255),
                )

                hud_pause = render_chinese_hud(
                    "【人在回路·第3关积水研判】",
                    "【等待指挥官批复】",
                    (0, 180, 255),
                    current_sector_name,
                    is_traditional=False,
                )
                cv2.imshow(
                    WINDOW_NAME, np.hstack((p_frame, hud_pause))
                )

                k = cv2.waitKey(50) & 0xFF
                if k == ord("1") or k == 32:
                    active_path = path_z3_safe.tolist()
                    car_idx = 0
                    decision_zone3_done = True
                    IS_WAITING_HUMAN = False
                    is_wading_mode = False
                    LLM_ANALYSIS_TEXT = (
                        "指挥中心批准方案1：沿外圈干地绕行！避开深水未知区域！"
                    )
                    break
                elif k == ord("2"):
                    active_path = path_z3_wading.tolist()
                    car_idx = 0
                    decision_zone3_done = True
                    IS_WAITING_HUMAN = False
                    is_wading_mode = True
                    LLM_ANALYSIS_TEXT = "指挥中心批准方案2：强行涉水直切！注意底盘受损与打滑风险！"
                    break
                elif k == 27:
                    return
                elif k == ord("f") or k == ord("F"):
                    IS_FULLSCREEN = not IS_FULLSCREEN
                    cv2.setWindowProperty(
                        WINDOW_NAME,
                        cv2.WND_PROP_FULLSCREEN,
                        cv2.WINDOW_FULLSCREEN
                        if IS_FULLSCREEN
                        else cv2.WINDOW_NORMAL,
                    )

        # 状态控制
        status_text = (
            "深水泥泞涉水中" if is_wading_mode else "语义生命线巡航中"
        )
        status_color = (0, 200, 255) if is_wading_mode else (0, 255, 0)

        # 移动步进（涉水通过延长帧延时形成阻力感，不涉及数字速度）
        if car_idx < len(active_path):
            car_pos = active_path[car_idx]
            car_idx += 1
        elif car_idx >= len(active_path):
            status_text = "任务圆满完成"
            status_color = (0, 255, 0)
            current_sector_name = "安全终点"
            LLM_ANALYSIS_TEXT = "指挥中心最高通报：工兵已安全抵达受困人员坐标，空地人机协同任务达成！"

            # 纯净的绿色生命同心圆光环
            cv2.circle(frame, goal_pos, 26, (0, 255, 120), 2, cv2.LINE_AA)
            frame = draw_text_cn(
                frame,
                "[受困人员已获救]",
                (goal_pos[0] - 130, goal_pos[1] - 30),
                14,
                (0, 255, 120),
            )

        frame = draw_scout_car(
            frame,
            car_pos,
            is_waiting=False,
            is_wading=is_wading_mode,
            is_tunnel=is_tunnel_mode,
            is_traditional=False,
        )

        hud = render_chinese_hud(
            "【阶段二：人在回路研判】",
            status_text,
            status_color,
            current_sector_name,
            is_traditional=False,
        )
        cv2.imshow(
            WINDOW_NAME, np.hstack((frame, hud))
        )

        # 涉水时慢动作模拟泥浆阻力，正常时快速巡航
        frame_delay = 55 if is_wading_mode else 22
        key = cv2.waitKey(frame_delay) & 0xFF
        if key == 27:
            break
        elif key == ord("r") or key == ord("R"):
            return run_full_pipeline()
        elif key == ord("f") or key == ord("F"):
            IS_FULLSCREEN = not IS_FULLSCREEN
            cv2.setWindowProperty(
                WINDOW_NAME,
                cv2.WND_PROP_FULLSCREEN,
                cv2.WINDOW_FULLSCREEN if IS_FULLSCREEN else cv2.WINDOW_NORMAL,
            )

    cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        run_full_pipeline()
    except Exception as e:
        print(f"\n❌ 程序发生异常: {e}")
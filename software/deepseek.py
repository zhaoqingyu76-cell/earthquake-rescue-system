"""DeepSeek 战术研判层（复用概念性演示代码.txt 的思路）。"""
import time

import config


def call_deepseek_tactical(zone_name, hazard_desc):
    """接入 DeepSeek 做战术研判，返回给搜救人员看的中文建议。

    zone_name:  如 "前方坑洞" / "前方水源区"（决定研判侧重）
    hazard_desc: 现场附加说明
    无 Key / 断网 / 超时 -> 返回本地降级文案（不影响控制主流程）。
    """
    fallback = (
        f"参谋离线研判：规避[{zone_name}]核心风险面，建议执行稳健绕行。"
    )
    if not config.DEEPSEEK_API_KEY:
        time.sleep(0.4)
        return fallback

    try:
        import requests
        prompt = (
            f"你是一名特种搜救战术参谋。前方出现【{zone_name}】，"
            f"现场情报：{hazard_desc}。"
            f"请研判：如果小车直行穿过该障碍，具体会遇到什么危险；"
            f"以及应该直行还是转弯绕过，选哪个更稳妥。"
            f"用极简练军用口吻(50字内)回答，"
            f"第一句讲直行后果，第二句给出建议(直行或转弯绕过)。"
        )
        payload = {
            "model": config.DEEPSEEK_MODEL,
            "messages": [
                {"role": "system",
                 "content": "你是特种搜救战术参谋，做语义地质风险研判，不编造机械数字。"},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 100,
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        resp = requests.post(config.DEEPSEEK_BASE_URL, headers=headers,
                             json=payload, timeout=6.0)
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return fallback


def call_zone_assessment(zone_summary):
    """针对【锁定地形】做震后搜救风险研判（常驻显示在研判区）。

    zone_summary: 如 "坑洞(x192,y177) 1处; 水源区(x80,y300) 1处"
    返回一段中文分析：震后搜救经过该地形可能遇到什么问题、该直行还是绕行。
    """
    fallback = (
        "参谋离线研判：该区域震后结构不稳定，建议谨慎，必要时从锁定区域边缘绕行。"
    )
    if not config.DEEPSEEK_API_KEY:
        time.sleep(0.3)
        return fallback
    try:
        import requests
        prompt = (
            f"你是一名震后搜救战术参谋。前方锁定地形情报：{zone_summary}。"
            f"请研判：搜救小车直行通过这段地形，在震后环境下可能遇到什么问题；"
            f"以及应直行通过还是从锁定地形边缘绕行，哪个更稳妥。"
            f"用简洁军用口吻(60字内)回答：第一句讲直行风险，第二句给出建议(直行或边缘绕行)。"
        )
        payload = {
            "model": config.DEEPSEEK_MODEL,
            "messages": [
                {"role": "system",
                 "content": "你是震后特种搜救战术参谋，做语义地质风险研判。"},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 120,
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        resp = requests.post(config.DEEPSEEK_BASE_URL, headers=headers,
                             json=payload, timeout=6.0)
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return fallback

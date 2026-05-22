"""
健康监测规则引擎
评估传感器数据和对话内容，返回严重等级及建议动作

用法:
    from tools.health_monitor import evaluate_heart_rate, evaluate_bp, evaluate_fall, evaluate_keywords, monitor_all

    result = monitor_all(heart_rate=115, bp_systolic=145, bp_diastolic=92)
    # → { "level": "orange", "actions": [...], "should_push": False }

    result = evaluate_keywords("我感觉有点头晕和胸闷")
    # → { "level": "red", "actions": [...], "should_push": True }
"""

import json
from pathlib import Path
from datetime import datetime, timedelta

# 加载规则
_rules_path = Path(__file__).parent / "health_rules.json"
with open(_rules_path) as f:
    RULES = json.load(f)


# ── 严重等级 ⚡ ──────────────────────────────

LEVELS = {
    "green":  {"name": "正常",  "emoji": "🟢", "score": 0},
    "yellow": {"name": "关注",  "emoji": "🟡", "score": 1},
    "orange": {"name": "预警",  "emoji": "🟠", "score": 2},
    "red":    {"name": "紧急",  "emoji": "🔴", "score": 3},
}

SUMMARY_NAMES = {v["name"]: k for k, v in LEVELS.items()}
SUMMARY_HEADERS = ["green","yellow","orange","red"]


# ── 评估函数 ─────────────────────────────────

def _pick_level(level: str):
    """返回等级元信息"""
    result = dict(LEVELS.get(level, LEVELS["green"]))
    result["level"] = level  # 保留等级标识
    return result


def evaluate_heart_rate(hr: float, sustained_minutes: int = 0) -> dict:
    """
    评估心率数据
    Args:
        hr: 心率值 (bpm)
        sustained_minutes: 持续时长

    Returns: { level, name, emoji, actions, details }
    """
    rules = RULES["heart_rate"]

    if hr < rules["warning_low"]["max"]:
        return {
            **_pick_level(rules["warning_low"]["level"]),
            "actions": [rules["warning_low"]["action"]],
            "details": f"心率偏慢: {hr}bpm",
        }

    if hr >= rules["emergency_high"]["min"] and sustained_minutes >= rules["emergency_high"]["duration_minutes"]:
        msg = f"心率{hr}bpm，持续{sustained_minutes}分钟"
        return {
            **_pick_level(rules["emergency_high"]["level"]),
            "actions": [rules["emergency_high"]["action"]],
            "details": msg,
        }

    if hr >= rules["warning"]["min"] and sustained_minutes >= rules["warning"]["duration_minutes"]:
        msg = f"心率{hr}bpm，持续{sustained_minutes}分钟"
        return {
            **_pick_level(rules["warning"]["level"]),
            "actions": [rules["warning"]["action"]],
            "details": msg,
        }

    if hr >= rules["watch"]["min"] and hr <= rules["watch"]["max"]:
        return {
            **_pick_level(rules["watch"]["level"]),
            "actions": [rules["watch"]["action"]],
            "details": f"心率略高: {hr}bpm",
        }

    if rules["normal"]["min"] <= hr <= rules["normal"]["max"]:
        return {
            **_pick_level("green"),
            "actions": [],
            "details": f"心率正常: {hr}bpm",
        }

    # 未知范围
    return {
        **_pick_level("yellow"),
        "actions": ["数据异常，建议重新测量"],
        "details": f"心率: {hr}bpm",
    }


def evaluate_bp(systolic: float, diastolic: float) -> dict:
    """
    评估血压数据
    Args:
        systolic: 收缩压
        diastolic: 舒张压

    Returns: { level, name, emoji, actions, details }
    """
    bp_rules = RULES["blood_pressure"]
    findings = []

    def _check_single(value, ruleset, label):
        """检查单边血压值"""
        if value >= ruleset["emergency_high"]["min"]:
            findings.append(("red", ruleset["emergency_high"]["action"]))
        elif value >= ruleset["warning"]["min"]:
            findings.append(("orange", ruleset["warning"]["action"]))
        elif value >= ruleset["watch"]["min"]:
            findings.append(("yellow", ruleset["watch"]["action"]))
        elif value <= ruleset["emergency_low"]["max"]:
            findings.append(("red", ruleset["emergency_low"]["action"]))

    _check_single(systolic, bp_rules["systolic"], "收缩压")
    _check_single(diastolic, bp_rules["diastolic"], "舒张压")

    if not findings:
        return {
            **_pick_level("green"),
            "actions": [],
            "details": f"血压正常: {systolic}/{diastolic}",
        }

    # 取最高等级
    levels_order = ["red", "orange", "yellow"]
    top_level = "yellow"
    all_actions = []
    for lv in levels_order:
        actions_for_lv = [a for l, a in findings if l == lv]
        if actions_for_lv:
            top_level = lv
            all_actions = actions_for_lv
            break

    return {
        **_pick_level(top_level),
        "actions": all_actions,
        "details": f"血压: {systolic}/{diastolic}",
    }


def evaluate_fall(sensor_detected: bool = False, keywords: list = None) -> dict:
    """
    评估摔倒风险
    Args:
        sensor_detected: 传感器是否检测到摔倒
        keywords: 对话中检测到的关键词列表

    Returns: { level, name, emoji, actions }
    """
    fall_rules = RULES["fall_detection"]

    if sensor_detected:
        return {
            **_pick_level(fall_rules["sensor_fall"]["level"]),
            "actions": [fall_rules["sensor_fall"]["action"]],
            "details": "传感器检测到摔倒",
        }

    if keywords:
        text = " ".join(keywords).lower()

        # 紧急摔倒关键词
        for kw in fall_rules["keyword_said_fell"]["keywords"]:
            if kw in text:
                return {
                    **_pick_level(fall_rules["keyword_said_fell"]["level"]),
                    "actions": [fall_rules["keyword_said_fell"]["action"]],
                    "details": f"老人提到: {kw}",
                }

        # 差点摔倒
        for kw in fall_rules["keyword_nearly_fell"]["keywords"]:
            if kw in text:
                return {
                    **_pick_level(fall_rules["keyword_nearly_fell"]["level"]),
                    "actions": [fall_rules["keyword_nearly_fell"]["action"]],
                    "details": f"老人提到: {kw}",
                }

    return {
        **_pick_level("green"),
        "actions": [],
        "details": "无摔倒风险",
    }


def evaluate_keywords(text: str) -> dict:
    """
    评估对话中的关键词
    Args:
        text: 老人说的话

    Returns: { level, name, emoji, actions, matched_keywords }
    """
    kw_rules = RULES["keywords"]
    text_lower = text.lower()
    matched = []

    def _scan(category_key, rule_group):
        for kw in rule_group["keywords"]:
            if kw in text_lower:
                matched.append({
                    "keyword": kw,
                    "level": rule_group["level"],
                    "action": rule_group["action"],
                    "category": category_key,
                })

    _scan("emergency", kw_rules["emergency"])
    _scan("warning", kw_rules["warning"])
    _scan("watch", kw_rules["watch"])

    if not matched:
        return {
            **_pick_level("green"),
            "actions": [],
            "details": "无预警关键词",
            "matched_keywords": [],
        }

    # 取最高等级
    level_order = {"red": 0, "orange": 1, "yellow": 2}
    worst = min(matched, key=lambda m: level_order.get(m["level"], 99))
    worst_level = worst["level"]
    all_actions = list(set(m["action"] for m in matched if m["level"] == worst_level))
    details = "检测到关键词: " + ", ".join(m["keyword"] for m in matched)

    return {
        **_pick_level(worst_level),
        "actions": all_actions,
        "details": details,
        "matched_keywords": [m["keyword"] for m in matched],
    }


# ── 综合评估 ─────────────────────────────────

def monitor_all(
    heart_rate: float = None,
    hr_sustained_minutes: int = 0,
    bp_systolic: float = None,
    bp_diastolic: float = None,
    conversation_text: str = None,
    fall_sensor: bool = False,
    fall_keywords: list = None,
) -> dict:
    """
    综合评估所有健康数据，返回最高等级及所有建议动作

    Returns: {
        level, name, emoji,
        actions: [建议动作列表],
        details: "详细说明",
        should_push: bool,        # True = 需要 Push 通知子女
        should_notify: bool,      # True = 需要微信通知子女
        should_comfort: bool,     # True = 需要安抚老人
        evaluation: [各单项评估结果]
    }
    """
    evaluations = []

    # 心率
    if heart_rate is not None:
        evaluations.append(("心率", evaluate_heart_rate(heart_rate, hr_sustained_minutes)))

    # 血压
    if bp_systolic is not None and bp_diastolic is not None:
        evaluations.append(("血压", evaluate_bp(bp_systolic, bp_diastolic)))

    # 摔倒
    if fall_sensor or fall_keywords:
        evaluations.append(("摔倒", evaluate_fall(fall_sensor, fall_keywords)))

    # 关键词
    if conversation_text:
        evaluations.append(("对话", evaluate_keywords(conversation_text)))

    if not evaluations:
        return {
            **_pick_level("green"),
            "actions": [],
            "details": "无数据可评估",
            "should_push": False,
            "should_notify": False,
            "should_comfort": False,
            "evaluation": [],
        }

    # 取最高等级
    score_order = {"red": 3, "orange": 2, "yellow": 1, "green": 0}
    worst = max(evaluations, key=lambda e: score_order.get(e[1]["score"], 0))

    # 收集所有动作
    all_actions = []
    for name, result in evaluations:
        if result["score"] >= score_order.get(worst[1].get("level", "green"), 0):
            all_actions.extend(result["actions"])

    worst_level = worst[1]["level"]
    worst_name = worst[1]["name"]
    worst_emoji = worst[1]["emoji"]

    # 判断通知等级
    should_push = worst_level == "red"
    should_notify = worst_level in ("orange", "red")
    should_comfort = worst_level in ("yellow", "orange", "red")

    # 构建详情
    parts = []
    for name, result in evaluations:
        parts.append(f"[{name}] {result['details']}")
    details = " | ".join(parts)

    return {
        "level": worst_level,
        "name": worst_name,
        "emoji": worst_emoji,
        "actions": list(set(all_actions)),
        "details": details,
        "should_push": should_push,
        "should_notify": should_notify,
        "should_comfort": should_comfort,
        "evaluations": [(n, r["level"], r["details"]) for n, r in evaluations],
    }


# ── 命令行测试 ───────────────────────────────

if __name__ == "__main__":
    import sys

    print("=" * 50)
    print("🏠 健康监测规则引擎 v1.0 测试")
    print("=" * 50)

    # 测试用例
    tests = [
        {"label": "正常心率", "heart_rate": 75},
        {"label": "心率偏高关注", "heart_rate": 105},
        {"label": "心率预警", "heart_rate": 115, "hr_sustained_minutes": 6},
        {"label": "心率紧急", "heart_rate": 125, "hr_sustained_minutes": 10},
        {"label": "血压偏高", "bp_systolic": 145, "bp_diastolic": 92},
        {"label": "血压正常", "bp_systolic": 120, "bp_diastolic": 80},
        {"label": "胸闷紧急关键词", "conversation_text": "我感觉有点胸闷，喘不过气"},
        {"label": "头晕预警", "conversation_text": "今天头有点晕"},
        {"label": "摔倒了", "fall_keywords": ["摔倒了"]},
        {"label": "综合：心率偏高+头晕", "heart_rate": 108, "conversation_text": "今天有点头晕"},
        {"label": "综合：紧急", "heart_rate": 128, "hr_sustained_minutes": 12, "conversation_text": "胸闷"},
    ]

    for t in tests:
        label = t.pop("label")
        result = monitor_all(**t)
        print(f"\n[{label}]")
        print(f"  等级: {result['emoji']} {result['name']}")
        print(f"  动作: {', '.join(result['actions']) if result['actions'] else '无'}")
        if result["should_push"]:
            print(f"  📱 Push通知子女")
        if result["should_notify"] and not result["should_push"]:
            print(f"  💬 微信通知子女")
        print(f"  详情: {result['details']}")

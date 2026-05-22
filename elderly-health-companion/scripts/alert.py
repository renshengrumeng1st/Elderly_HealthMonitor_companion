"""
健康预警通知模块
通过 Spug Push 向子女发送健康预警消息

用法:
    from tools.alert import send_alert, send_emergency_alert

    # 普通预警
    send_alert("老爸的心率略高（105次/分钟），已安抚并提醒休息")

    # 紧急预警
    send_emergency_alert(
        "心率异常",
        "心率持续高于120次/分钟已超过10分钟，请尽快联系老爸！"
    )
"""

import urllib.request
import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Spug Push 通知地址
ALERT_URL = "https://push.spug.cc/send/XALgM8MNJOmdnwDe"


def _send(content: str, title: str = None) -> dict:
    """
    发送预警通知

    Args:
        content: 通知内容
        title: 通知标题（可选）

    Returns:
        API 响应
    """
    payload = {"content": content}
    if title:
        payload["title"] = title

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ALERT_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("code") == 200:
                print(f"[alert] ✅ 预警发送成功: {title or '通知'}", file=sys.stderr)
            else:
                print(f"[alert] ⚠️ 预警发送失败: {result}", file=sys.stderr)
            return result
    except Exception as e:
        print(f"[alert] ❌ 预警发送异常: {e}", file=sys.stderr)
        return {"code": -1, "msg": str(e)}


def send_alert(content: str) -> dict:
    """
    发送健康预警（中低级，通知子女）

    Args:
        content: 预警内容, 如 "老爸心率108次/分钟，略微偏高，已安抚休息"

    Returns:
        API 响应
    """
    now = datetime.now().strftime("%m-%d %H:%M")
    return _send(
        title="🏠 健康提醒",
        content=f"🕐 {now}\n{content}\n\n—— 银发健康守护陪伴官",
    )


def send_emergency_alert(title: str, content: str) -> dict:
    """
    发送紧急预警（紧急情况，需要立即关注）

    Args:
        title: 紧急标题, 如 "心率异常预警"
        content: 详细情况 + 建议动作

    Returns:
        API 响应
    """
    now = datetime.now().strftime("%m-%d %H:%M")
    return _send(
        title=f"🚨 紧急预警 — {title}",
        content=f"⏰ {now}\n🚨 紧急程度: 高\n\n{content}\n\n—— 银发健康守护陪伴官",
    )


# ── 命令行测试 ────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        content = sys.argv[1]
        title = sys.argv[2] if len(sys.argv) > 2 else None
        if title:
            result = send_emergency_alert(title, content)
        else:
            result = send_alert(content)
        print(json.dumps(result, ensure_ascii=False))
    else:
        # 自测
        r = send_alert("这是一条测试通知，确认预警通道正常 ✅")
        print(json.dumps(r, ensure_ascii=False))

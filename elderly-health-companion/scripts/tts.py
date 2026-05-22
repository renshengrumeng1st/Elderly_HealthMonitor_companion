"""
Edge TTS (微软语音合成) 模块
将文字转换为语音，使用微软 Edge TTS 在线服务

用法:
    # 命令行
    python tools/tts.py "您好，今天感觉怎么样？"

    # 代码中调用
    from tools.tts import text_to_speech, text_to_speech_slow

    path = text_to_speech_slow("爷爷，下午好，今天天气不错")
    print(f"语音已保存: {path}")
"""

import os
import sys
import asyncio
import tempfile
from pathlib import Path

import edge_tts

# ── 默认配置 ──────────────────────────────────

# 中文女声，温柔亲切，适合给老人听
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"

# 正常语速
DEFAULT_RATE = "+0%"
DEFAULT_VOLUME = "+0%"

# 常用中文语音角色（供参考）
AVAILABLE_VOICES = {
    "xiaoxiao": {
        "name": "zh-CN-XiaoxiaoNeural",
        "gender": "女",
        "desc": "温柔亲切（推荐给老人）",
    },
    "xiaoyi": {
        "name": "zh-CN-XiaoyiNeural",
        "gender": "女",
        "desc": "活泼开朗",
    },
    "yunxi": {
        "name": "zh-CN-YunxiNeural",
        "gender": "男",
        "desc": "温和男声",
    },
    "yunjian": {
        "name": "zh-CN-YunjianNeural",
        "gender": "男",
        "desc": "爽朗男声",
    },
    "yunze": {
        "name": "zh-CN-YunzeNeural",
        "gender": "男",
        "desc": "阳光男声",
    },
}


async def _synthesize(text: str, voice: str, rate: str, volume: str, output_path: str):
    """内部异步合成（edge-tts 核心调用）"""
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    await communicate.save(output_path)


def text_to_speech(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    volume: str = DEFAULT_VOLUME,
    output_path: str = None,
) -> str:
    """
    将文字转换为语音文件（MP3 格式）

    Args:
        text: 要朗读的文字
        voice: 语音角色，默认 zh-CN-XiaoxiaoNeural
        rate: 语速，"+0%"（正常）/ "-20%"（慢速）/ "+50%"（快速）
        volume: 音量，"+0%"（正常）/ "+50%"（更大）
        output_path: 输出文件路径，不传则生成临时文件

    Returns:
        语音文件的绝对路径

    示例:
        >>> text_to_speech("您好，我是您的健康助手")
        '/tmp/tmpabc123.mp3'
    """
    if not output_path:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        output_path = tmp.name
        tmp.close()

    asyncio.run(_synthesize(text, voice, rate, volume, output_path))
    return os.path.abspath(output_path)


def text_to_speech_slow(text: str, voice: str = DEFAULT_VOICE, **kwargs) -> str:
    """
    慢速语音合成（语速降低 20%，适合老人听）

    Args:
        text: 要朗读的文字
        voice: 语音角色
        **kwargs: 其他传给 text_to_speech 的参数

    Returns:
        语音文件的绝对路径
    """
    # 语速放慢 20%，音量略增
    return text_to_speech(text, voice=voice, rate="-20%", volume="+10%", **kwargs)


def text_to_speech_to_file(text: str, output_path: str, slow: bool = True, **kwargs) -> str:
    """
    合成语音并保存到指定文件

    Args:
        text: 要朗读的文字
        output_path: 保存路径（必须 .mp3）
        slow: 是否慢速（老人友好），默认 True
        **kwargs: 其他参数

    Returns:
        保存路径
    """
    fn = text_to_speech_slow if slow else text_to_speech
    return fn(text, output_path=output_path, **kwargs)


# ── 实用查询 ──────────────────────────────────

def list_chinese_voices() -> list:
    """列出所有可用的中文语音角色"""
    async def _fetch():
        voices = await edge_tts.list_voices()
        return [
            {
                "name": v["ShortName"],
                "gender": v["Gender"],
                "locale": v["Locale"],
                "desc": v.get("LocalName", ""),
            }
            for v in voices
            if "CN" in v.get("Locale", "")
        ]

    return asyncio.run(_fetch())


# ── 命令行入口 ────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--list", "-l"):
        print("可用的中文语音角色:")
        for v in list_chinese_voices():
            print(f"  {v['name']:30s}  {v['gender']}  {v['desc']}")
        sys.exit(0)

    text = sys.argv[1] if len(sys.argv) > 1 else (
        "您好，我是您的健康守护陪伴官。今天身体感觉怎么样？"
    )

    output = text_to_speech_slow(text)
    print(f"[tts] ✅ 语音已生成: {output}")
    print(f"[tts] 播放: ffplay -nodisp -autoexit '{output}'")
    print(f"[tts] 文件大小: {os.path.getsize(output):,} bytes")

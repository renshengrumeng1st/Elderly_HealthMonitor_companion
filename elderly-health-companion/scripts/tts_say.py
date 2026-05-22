#!/usr/bin/env python3
"""
TTS 语音生成脚本 — 输出 SILK 格式（WeChat 原生语音格式，直接点开播放）
供 AI 在 cron session 中通过 exec 调用

用法:
    python3 tools/tts_say.py "爷爷，早上好，今天身体怎么样？"
    → /tmp/tts_xxx.silk

AI 用 message(media=输出路径) 发送语音
"""
import sys
import os
import subprocess
import tempfile
import wave

# 加入 workspace 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.tts import text_to_speech


def calculate_playtime_ms(wav_path: str) -> int:
    """读取 wav 文件返回时长（毫秒）"""
    with wave.open(wav_path, 'rb') as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return int(frames / rate * 1000)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 tools/tts_say.py <要朗读的文字>", file=sys.stderr)
        sys.exit(1)

    text = sys.argv[1]

    # 1) Edge TTS → MP3
    tmp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    mp3_path = tmp_mp3.name
    tmp_mp3.close()

    try:
        text_to_speech(text, output_path=mp3_path)

        # 2) MP3 → WAV (24kHz 16-bit 单声道)
        tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wav_path = tmp_wav.name
        tmp_wav.close()

        subprocess.run([
            "ffmpeg", "-y", "-i", mp3_path,
            "-ar", "24000", "-ac", "1", "-sample_fmt", "s16",
            wav_path,
        ], check=True, capture_output=True)

        # 3) WAV → SILK（WeChat 原生语音格式）
        tmp_silk = tempfile.NamedTemporaryFile(suffix=".silk", delete=False)
        silk_path = tmp_silk.name
        tmp_silk.close()

        import pysilk
        with open(wav_path, 'rb') as fin, open(silk_path, 'wb') as fout:
            pysilk.encode(fin, fout, 24000, 24000)

        # 4) 输出 silk 文件路径
        print(silk_path)

    finally:
        for p in [mp3_path, wav_path]:
            try:
                os.unlink(p)
            except Exception:
                pass

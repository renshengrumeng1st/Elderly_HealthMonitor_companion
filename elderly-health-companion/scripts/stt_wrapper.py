#!/usr/bin/env python3
"""
OpenClaw STT 系统包装器
被 OpenClaw 的 tools.media.audio.models 调用
接收音频文件路径，输出识别文字到 stdout

用法（由 OpenClaw 自动调用）:
    python3 stt_wrapper.py /tmp/weixin/voice/xxx.wav
"""
import sys
import traceback
from pathlib import Path

# 把 workspace 加入路径
workspace = Path(__file__).parent.parent
sys.path.insert(0, str(workspace))

from tools.asr import transcribe_with_ffmpeg


def main():
    if len(sys.argv) < 2:
        print("[ERROR] 缺少音频文件参数", file=sys.stderr)
        sys.exit(1)

    audio_path = sys.argv[1]

    if not Path(audio_path).exists():
        print(f"[ERROR] 音频文件不存在: {audio_path}", file=sys.stderr)
        sys.exit(1)

    try:
        text = transcribe_with_ffmpeg(audio_path)
        # 只输出识别文字（OpenClaw 读 stdout 作为转录结果）
        print(text, end="")
    except Exception as e:
        print(f"[ERROR] 语音识别失败: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

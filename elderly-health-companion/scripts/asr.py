"""
腾讯云语音识别 (ASR) 模块
将音频文件转换为文字，使用腾讯云一句话识别 API

用法:
    # 命令行
    python tools/asr.py /path/to/audio.wav

    # 代码中调用
    from tools.asr import transcribe_audio, transcribe_with_ffmpeg

    text = transcribe_with_ffmpeg("/path/to/wechat_voice.silk")
    print(f"识别结果: {text}")
"""

import os
import sys
import json
import base64
import uuid
import subprocess
import tempfile
from pathlib import Path

from tencentcloud.common import credential
from tencentcloud.common.exception import TencentCloudSDKException
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.asr.v20190614 import asr_client, models

# ── 凭证配置 ──────────────────────────────────

_config_path = Path(__file__).parent / ".tencent_credentials.json"
_SECRET_ID = None
_SECRET_KEY = None

# 1) 优先环境变量
_SECRET_ID = os.environ.get("TENCENT_ASR_SECRET_ID")
_SECRET_KEY = os.environ.get("TENCENT_ASR_SECRET_KEY")

# 2) 其次配置文件
if (not _SECRET_ID or not _SECRET_KEY) and _config_path.exists():
    try:
        with open(_config_path) as f:
            cfg = json.load(f)
            _SECRET_ID = _SECRET_ID or cfg.get("secret_id")
            _SECRET_KEY = _SECRET_KEY or cfg.get("secret_key")
    except Exception as e:
        print(f"[asr] 警告: 读取凭证文件失败: {e}", file=sys.stderr)


def transcribe_audio(
    audio_path: str,
    secret_id: str = None,
    secret_key: str = None,
    engine_type: str = "16k_zh",
    voice_format: str = "wav",
) -> str:
    """
    将音频文件转换为文字（腾讯云一句话识别）

    Args:
        audio_path: 音频文件路径
        secret_id: 腾讯云 SecretId（不传则用默认配置）
        secret_key: 腾讯云 SecretKey（不传则用默认配置）
        engine_type: 引擎类型 "16k_zh"(中文普通话) / "16k_en"(英文)
        voice_format: 音频格式 "wav" / "mp3" / "m4a" / "amr" / "silk"

    Returns:
        识别出的文字

    Raises:
        ValueError: 未配置凭证
        Exception: 识别失败（含 API 错误信息）
    """
    sid = secret_id or _SECRET_ID
    sk = secret_key or _SECRET_KEY
    if not sid or not sk:
        raise ValueError(
            "未配置腾讯云 ASR 凭证。请设置环境变量 TENCENT_ASR_SECRET_ID / "
            "TENCENT_ASR_SECRET_KEY，或创建 tools/.tencent_credentials.json"
        )

    # 读取音频
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    data_b64 = base64.b64encode(audio_data).decode("utf-8")
    data_len = len(audio_data)

    # 认证
    cred = credential.Credential(sid, sk)

    # HTTP 配置
    http_profile = HttpProfile()
    http_profile.endpoint = "asr.tencentcloudapi.com"
    http_profile.reqTimeout = 30

    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile

    # ASR 客户端
    client = asr_client.AsrClient(cred, "", client_profile)

    # 构建一句话识别请求
    req = models.SentenceRecognitionRequest()
    req.ProjectId = 0
    req.SubServiceType = 2           # 一句话识别
    req.EngSerViceType = engine_type
    req.SourceType = 1               # 语音数据(body)
    req.VoiceFormat = voice_format
    req.UsrAudioKey = str(uuid.uuid4())
    req.Data = data_b64
    req.DataLen = data_len
    req.FilterDirty = 1              # 过滤脏词
    req.FilterPunc = 1               # 过滤句末标点
    req.FilterModal = 1              # 过滤语气词

    resp = client.SentenceRecognition(req)
    return resp.Result


def transcribe_with_ffmpeg(
    audio_path: str,
    sample_rate: int = 16000,
    **kwargs,
) -> str:
    """
    先用 ffmpeg 转码为 16kHz 单声道 wav，再调用 ASR

    适合 WeChat 语音消息（silk / amr / speex 等非标准格式）

    Args:
        audio_path: 原始音频路径（任意 ffmpeg 支持的格式）
        sample_rate: 目标采样率，默认 16000
        **kwargs: 透传给 transcribe_audio
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-ar", str(sample_rate), "-ac", "1",
            "-sample_fmt", "s16",
            tmp_path,
        ]
        result = subprocess.run(
            cmd, check=True, capture_output=True, text=True,
        )
        return transcribe_audio(tmp_path, voice_format="wav", **kwargs)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"ffmpeg 转码失败: {e.stderr[:500]}"
        ) from e
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ── 命令行入口 ────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python tools/asr.py <音频文件路径>")
        print("示例: python tools/asr.py test.wav")
        sys.exit(1)

    audio_file = sys.argv[1]
    print(f"[asr] 正在识别: {audio_file}")

    # 自动判断是否需要 ffmpeg 转码
    ext = Path(audio_file).suffix.lower()
    if ext in (".wav", ".mp3", ".m4a"):
        text = transcribe_audio(audio_file, voice_format=ext.lstrip("."))
    else:
        text = transcribe_with_ffmpeg(audio_file)

    print(f"[asr] ✅ 识别结果: {text}")

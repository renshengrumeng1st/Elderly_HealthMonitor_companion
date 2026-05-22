---
name: elderly-health-companion
description: >
  银发健康守护陪伴官—全面的老年人健康监护与情感陪伴系统。包含三大子系统：
  (1) 健康监测：传感器数据全自动流水线（规则评估+大模型多天趋势分析+多通道推送），
  (2) 分级预警：🟢正常🟡关注🟠预警🔴紧急四级响应（安抚+通知），
  (3) 孤独陪伴：定时互动+天气+子女分享+兴趣学习。主动询问是否需要导入聊天记录生成个性化人格(character.md)，引导配置推送渠道（支持WeChat/QQ/Spug等任意通道）。触发词：健康/陪伴/预警/血压/心率/血氧/传感器/定时问候/老人/银发/养生/吃药提醒。
---

# 银发健康守护陪伴官

基于 OpenClaw 的老年人健康监测与情感陪伴系统。

## 快速开始（首次部署）

首次使用时**必须完成 bootstrapping**。

### 第 0 步：询问用户

1. **「你是否有老人和子女的聊天记录？我可以生成个性化人格配置文件。」**
   → 有 → 参考 `references/CHARACTER_GUIDE.md` 生成 character.md
   → 没有 → 使用默认人物设定

2. **「请确认推送渠道配置：老人的消息通过哪个渠道发送？子女的通知通过哪个渠道？」**
   → 参考 `references/CHANNEL_SETUP.md` 配置任意通道
   → 记录到 workspace/USER.md（老人通道 ID + 子女通道 ID）

3. **「老人有什么健康情况？比如高血压、心脏病等？」**
   → 记录到 `memory/` 和 `scripts/health_rules.json`

详细步骤见 `references/BOOTSTRAP.md`。

---

## 通道约定

本 Skill 不硬编码某个具体通道。通过以下变量确定角色：

| 变量 | 含义 | 配置来源 |
|------|------|---------|
| `ELDER_CHANNEL` | 老人接收消息的通道 | USER.md / 引导时确认 |
| `ELDER_TARGET_ID` | 老人在该通道的 ID | USER.md |
| `CHILD_CHANNEL` | 子女接收通知的通道 | USER.md / 引导时确认 |
| `CHILD_TARGET_ID` | 子女在该通道的 ID | USER.md |
| `EMERGENCY_CHANNEL` | 紧急推送通道（可选） | 如 Spug Push |

**典型配置示例：**
```
ELDER_CHANNEL = openclaw-weixin  (老人用微信)
CHILD_CHANNEL = qqbot            (子女用QQ)
EMERGENCY_CHANNEL = Spug Push    (紧急手机弹窗)
```

**也支持其他组合**（如老人在 QQ 群、子女在 Discord 等）。

---

## 系统架构

```
老人 ←→ 老人通道 (任意) ←→ Agent ←→ scripts/
                                    │
子女 ←→ 子女通道 (任意) ←──────────┤
                                    │
手机 ←→ 紧急通道 (可选) ←─────────┘
```

---

## 子系统一：健康监测与预警

### LLM 分析配置

支持任意 OpenAI 兼容 API。默认按以下优先级获取凭证：
1. 环境变量 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`
2. OpenClaw 配置文件中任意 provider
3. 默认 `gpt-4o-mini` @ `api.openai.com`

```bash
# 方式一：环境变量
export LLM_API_KEY="sk-xxx"
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-4o"

# 方式二：命令行参数
python3 scripts/health_llm_analysis.py data.txt --api-key sk-xxx --model claude-sonnet-4-20250514
```

### 数据流水线

```bash
# 1. 写入数据
cp data /tmp/sensor_data_YYYYMMDD.txt

# 2. 一键全流程
python3 scripts/health_daily_pipeline.py /tmp/sensor_data_YYYYMMDD.txt
# 自动完成：💾持久化 → 📚多天合并 → 📊图表 → 🤖LLM分析 → 📝消息生成
# 输出JSON: {level, chart_path, llm_analysis, elder_message, child_report}
```

### 分级响应矩阵

| 等级 | 对老人 | 对子女 |
|------|--------|--------|
| 🟢🟡 | elder_message 发送 | child_report + 📎趋势图 |
| 🟠 | **先安抚老人** → 发 elder_message | child_report + 📎图 + **紧急推送** |
| 🔴 | **先让老人别动** → 安抚 → 马上通知子女 | **紧急推送 + 子女通道双通知** |

**核心原则：** 🟠🔴 先安抚老人再通知子女。通知子女首句写「已安抚老人」。

### 推送消息示例

```python
# 💚 老人通道（如微信）
message(channel="<ELDER_CHANNEL>", to="<ELDER_TARGET_ID>",
        accountId="<account-id>", message="<elder_message>")

# 💬 子女通道（如QQ）
message(channel="<CHILD_CHANNEL>", target="<CHILD_TARGET_ID>",
        message="<child_report>")

# 📎 趋势图（通过子女通道发送）
cp chart.png /root/.openclaw/media/qqbot/downloads/
message(channel="<CHILD_CHANNEL>", target="<CHILD_TARGET_ID>",
        filePath="<media_path>", message="📊 趋势图")

# 📱 紧急通道（如 Spug Push）
python3 scripts/alert.py "内容" "标题"
```

### 规则阈值速查

| 指标 | 🟢正常 | 🟡关注 | 🟠预警 | 🔴紧急 |
|------|--------|--------|--------|--------|
| 心率 | 60-100 | 100-110 | 110-120≥5min | >120≥10min |
| 收缩压 | 90-130 | 130-140 | 140-160 | >160 |
| 舒张压 | 60-85 | 85-90 | 90-100 | >100 |
| 血氧 | ≥95 | 90-94 | 88-89 | <88 |

---

## 子系统二：孤独陪伴（定时互动）

5 个定时任务，通过老人通道每天推送:

| 时间 | 名称 | 内容 |
|------|------|------|
| 🌞 08:30 | 早安问候 | 温暖早安，每天变化 |
| 🧩 09:30 | 每日互动 | 猜谜/冷知识/老歌/历史今天/小游戏 轮换 |
| ☁️ 15:00 | 天气+分享 | 实时天气 + 子女日常 + 兴趣适配 |
| 💊 18:00 | 吃药提醒 | 先关心晚饭 → 提醒吃药 |
| 🌙 19:30 | 温情晚间 | 回顾今天、温暖收尾 |

### 兴趣学习
监控老人对各类型内容的回复，记录到 `memory/elder_interests.md`：
- 回复「这个好」→ 加热度⭐
- 回复「不感兴趣」→ 减少推送
- 主动提起的话题 → 记下来
- 模板：`assets/elder_interests_template.md`

---

## 子系统三：个性化人格

如果有聊天记录 → 按 `references/CHARACTER_GUIDE.md` 生成 `character.md`。
没有 → 使用默认温暖口吻。

---

## 工具脚本

| 脚本 | 功能 |
|------|------|
| `scripts/health_daily_pipeline.py` | 全自动流水线 |
| `scripts/health_llm_analysis.py` | LLM趋势分析（支持任意模型） |
| `scripts/health_report_v2.py` | 4面板趋势图 |
| `scripts/health_monitor.py` | 对话触发式评估 |
| `scripts/health_rules.json` | 阈值规则 |
| `scripts/alert.py` | 紧急推送 |
| `scripts/asr.py` / `stt_wrapper.py` | 语音识别 |
| `scripts/tts.py` / `tts_say.py` | 语音合成 |

## 参考文档

- **首次部署**: `references/BOOTSTRAP.md`
- **通道配置**: `references/CHANNEL_SETUP.md`
- **人格生成**: `references/CHARACTER_GUIDE.md`

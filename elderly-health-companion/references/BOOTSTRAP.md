# Bootstrapping Guide — 首次部署流程

当 Agent 首次部署此 skill 时，按以下步骤完成初始化。

---

## 0. 检查依赖

```bash
pip install matplotlib requests 2>/dev/null || pip3 install matplotlib requests
apt-get install -y fonts-noto-cjk 2>/dev/null || true  # 中文字体
```

---

## 1. 创建工作目录结构

```bash
WORKSPACE=$(pwd)  # 你的 OpenClaw workspace
mkdir -p $WORKSPACE/data/sensor       # 传感器数据持久化
mkdir -p $WORKSPACE/memory            # 每日日志
mkdir -p $WORKSPACE/assets            # 图表输出
```

---

## 2. 配置 LLM 分析引擎

支持任意 OpenAI 兼容 API：

```bash
# 环境变量方式（推荐）
export LLM_API_KEY="sk-your-key"
export LLM_BASE_URL="https://api.openai.com/v1"   # 或 DeepSeek/Claude 等
export LLM_MODEL="gpt-4o"

# 或命令行方式
python3 scripts/health_llm_analysis.py data.txt --api-key sk-xxx --model gpt-4o
```

**优先级**: 环境变量 > OpenClaw config > 默认值

---

## 3. 配置推送通道

本 Skill **不硬编码通道类型**。你需要确定：

| 角色 | 配置项 | 说明 |
|------|--------|------|
| 老人通道 | `ELDER_CHANNEL` + `ELDER_TARGET_ID` | 老人使用哪个平台接收消息 |
| 子女通道 | `CHILD_CHANNEL` + `CHILD_TARGET_ID` | 子女使用哪个平台接收通知 |
| 紧急通道（可选） | `EMERGENCY_CHANNEL` | 如 Spug Push，用于 🟠🔴 紧急推送 |

### 典型配置

```
ELDER_CHANNEL  = openclaw-weixin   (微信)
CHILD_CHANNEL  = qqbot              (QQ)
EMERGENCY_CHANNEL = Spug Push       (手机弹窗)
```

### 也支持其他组合

```
ELDER_CHANNEL  = telegram           (Telegram)
CHILD_CHANNEL  = discord            (Discord)
```

### 通道登录

```bash
# WeChat
openclaw plugins install @tencent-weixin/openclaw-weixin
openclaw channels login --channel openclaw-weixin

# QQ
# 配置在 openclaw.json 的 channels.qqbot 下

# Spug Push
# 修改 scripts/alert.py 中的 SPUG_URL
```

### ⚠️ iLinkai 协议限制（仅 WeChat）
接收方必须先给 bot 发过消息，bot 才能主动推送。contextToken 持久化到磁盘，重启不影响。

---

## 4. 生成个性化人格（可选但推荐）

如果用户有老人与子女的真实聊天记录：

1. 读取聊天记录
2. 分析两人的性格画像
3. 生成 `character.md`

详见 `references/CHARACTER_GUIDE.md`。

---

## 5. 配置定时陪伴任务

| 时间 | 名称 | 内容 |
|------|------|------|
| 08:30 | 早安问候 | 温暖早安 |
| 09:30 | 每日互动 | 猜谜/冷知识/老歌等轮换 |
| 15:00 | 天气+分享 | 实时天气 + 子女日常 + 兴趣 |
| 18:00 | 吃药提醒 | 先关心晚饭→提醒吃药 |
| 19:30 | 温情晚间 | 回顾+温暖收尾 |

**Cron 任务创建示例：**
```bash
openclaw cron add \
  --name "🧩 每日互动" \
  --schedule "30 9 * * *" --tz Asia/Shanghai \
  --session-target isolated \
  --delivery-channel "<ELDER_CHANNEL>" \
  --delivery-to "<ELDER_TARGET_ID>" \
  --delivery-account-id "<account-id>" \
  --payload '{"kind":"agentTurn","message":"…提示词见 SKILL.md…"}'
```

---

## 6. 初始化兴趣追踪

创建 `memory/elder_interests.md`（模板见 `assets/elder_interests_template.md`）。

---

## 7. 验证推送通道

```bash
# 验证老人通道
openclaw message send --channel "<ELDER_CHANNEL>" \
  --to "<ELDER_TARGET_ID>" --message "这是一条测试消息 😊"

# 验证子女通道
openclaw message send --channel "<CHILD_CHANNEL>" \
  --target "<CHILD_TARGET_ID>" --message "通道测试成功"
```

---

## 8. 运行首次健康报告

```bash
python3 scripts/health_daily_pipeline.py /tmp/sensor_data.txt
```

---

## 完成后的文件结构

```
workspace/
├── AGENTS.md           ← 人格一致性说明
├── SOUL.md             ← 角色定义
├── USER.md             ← 推送目标 ID（老人+子女）
├── character.md        ← 个性化人格
├── memory/
│   ├── elder_interests.md    ← 兴趣追踪
│   └── YYYY-MM-DD.md        ← 每日日志
├── data/sensor/              ← 传感器持久化
├── assets/                   ← 图表输出
└── skills/
    └── elderly-health-companion/
```

# Channel Setup — 推送通道配置

本 Skill 不硬编码通道。系统需要 2-3 个通道：

1. **老人通道** — 老人接收问候和健康摘要
2. **子女通道** — 子女接收日报和预警
3. **紧急通道**（可选）— 🟠🔴 时的强提醒

---

## 配置方式

引导用户确认以下信息，记录到 `workspace/USER.md`：

```yaml
老人:
  通道: <openclaw-weixin | telegram | ...>
  目标ID: <channel-specific-target>
  账号ID: <account-id-if-needed>

子女:
  通道: <qqbot | discord | ...>
  目标ID: <channel-specific-target>

紧急:
  通道: <spug-push | none>
  URL: <spug-webhook-url>
```

---

## 典型通道配置

### WeChat（老人常用）

```bash
openclaw plugins install @tencent-weixin/openclaw-weixin
openclaw channels login --channel openclaw-weixin
```

发送消息：
```python
message(channel="openclaw-weixin", to="<openid>@im.wechat",
        accountId="<bot-account-id>", message="...")
```

**⚠️ iLinkai 限制**：老人须先给 bot 发一条消息，bot 才能主动推送。

### QQ Bot（子女常用）

在 `openclaw.json` 配置：
```json
{ "channels": { "qqbot": { "enabled": true, "appId": "...", "clientSecret": "..." } } }
```

```python
message(channel="qqbot", target="qqbot:c2c:<openid>", message="...")
```

图片须先复制到 `/root/.openclaw/media/qqbot/downloads/`。

### Telegram

```python
message(channel="telegram", target="<chat-id>", message="...")
```

### Discord

```python
message(channel="discord", target="<channel-id>", message="...")
```

### Spug Push（紧急推送）

编辑 `scripts/alert.py` 设置 `SPUG_URL`：
```python
SPUG_URL = "https://你的SpugPush地址"
```

```bash
python3 scripts/alert.py "告警内容" "告警标题"
```

---

## 消息风格指南

### 老人通道消息
- 短句分行（每行1-2句）
- 使用 emoji（🌞💊❤️⚠️）
- 不使用医学术语
- 语气温暖亲切

### 子女通道消息
- 结构化报告格式
- 包含数据 + 趋势 + LLM 分析
- 清晰标注等级和风险
- 🟠🔴 时首句写「已安抚老人」

---

## 推送矩阵

| 场景 | 老人通道 | 子女通道 | 紧急通道 | 图表 |
|------|---------|---------|---------|------|
| 🟢🟡 正常/关注 | ✅ 简短 | ✅ 日报 | ❌ | ✅ |
| 🟠 预警 | ✅ **先安抚** | ✅ 详报 | ✅ | ✅ |
| 🔴 紧急 | ✅ **先安抚别动** | ✅ 紧急 | ✅ 即时 | ✅ |
| 定时陪伴 | ✅ 5时段 | ❌ | ❌ | ❌ |

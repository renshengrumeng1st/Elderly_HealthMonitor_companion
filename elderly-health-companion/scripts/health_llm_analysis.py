#!/usr/bin/env python3
"""
health_llm_analysis.py — 基于大模型的健康趋势分析与疾病风险评估

用法:
  python3 tools/health_llm_analysis.py <传感器数据文件>

传感器数据文件格式（空格或 tab 分隔，无表头行）:
  08:00 36.5 75 98 125 82 0 起床
  12:00 36.4 78 97 130 85 2000 午饭后
  列: 时间 体温 心率 血氧 收缩压 舒张压 步数 备注

也可以接受多天数据（时间列含日期）:
  2026-05-21 08:00 36.5 75 98 125 82 0 起床

输出:
  结构化 JSON 健康评估（含趋势分析、风险评估、建议）

集成到每日报告:
  python3 tools/health_report_v2.py /tmp/sensor_data.txt
  python3 tools/health_llm_analysis.py /tmp/sensor_data.txt >> /tmp/llm_analysis.json
"""

import json
import sys
import os
import requests
from datetime import datetime

# ---------- Configuration ----------
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")

def _load_llm_config_from_openclaw():
    """Try to read API credentials from any provider in OpenClaw config."""
    try:
        cfg_path = os.path.expanduser("~/.openclaw/openclaw.json")
        if not os.path.exists(cfg_path):
            return None, None
        with open(cfg_path) as f:
            cfg = json.load(f)
        providers = cfg.get("models", {}).get("providers", {})
        for name, p in providers.items():
            key = p.get("apiKey", "")
            base = p.get("baseUrl", "")
            if key and not key.startswith("__"):
                return key, base
        return None, None
    except Exception:
        return None, None

if not LLM_API_KEY:
    _key, _base = _load_llm_config_from_openclaw()
    LLM_API_KEY = _key or ""
    if _base and not LLM_BASE_URL:
        LLM_BASE_URL = _base
if not LLM_BASE_URL:
    LLM_BASE_URL = "https://api.openai.com/v1"
if not LLM_MODEL:
    LLM_MODEL = "gpt-4o-mini"

# ---------- System Prompt ----------
SYSTEM_PROMPT = """你是一位经验丰富的健康数据分析助手，专注于老年慢性病管理的趋势分析与风险评估。

## 核心原则
1. **不给出医学诊断** — 只分析数据趋势和模式，所有结论以「可能提示」「值得关注」等措辞表达
2. **结合病史分析** — 已知患者有高血压，正在服用降压药
3. **区分正常波动与异常信号** — 老年人血压/心率日间有自然波动是正常的
4. **注重趋势而非单点值** — 单一超标值可能是测量误差，持续性趋势才是信号
5. **输出结构化 JSON**

## 疾病风险提示参考（基于指南共识，仅用于数据模式匹配）
- **高血压相关**：晨峰血压（起床后2h内收缩压升高>30mmHg）、夜间高血压、白大衣效应
- **心脑血管风险信号**：心率持续>100次/分、血压波动幅度大、活动后心悸+血压异常
- **呼吸系统风险**：血氧持续<94%、活动后血氧下降>3%
- **糖尿病风险信号**：血压+心率+体重变化综合模式（非诊断，仅提示）
- **自主神经功能**：心率变异性低、体位性血压变化大

## 输出 JSON 格式（仅输出 JSON，不要额外说明文字）
{
  "overall_status": "优|良|一般|需关注",
  "summary": "一段概括性总结（50-100字），用大白话",
  "data_coverage": {
    "days": "覆盖天数",
    "total_records": "总记录数",
    "missing_periods": "数据缺失时段说明（如有）"
  },
  "trend_analysis": [
    {
      "metric": "心率",
      "range": "65-98",
      "average": 78,
      "trend": "稳定|缓慢上升|缓慢下降|波动增大",
      "assessment": "在正常范围内波动，适合老年人",
      "concern_level": "无|低|中|高"
    },
    {
      "metric": "血压(收缩压)",
      "range": "110-152",
      "average": 132,
      "trend": "稳定|缓慢上升|缓慢下降|晨峰明显|波动增大",
      "assessment": "整体控制尚可，晨起时段偏高需关注",
      "concern_level": "无|低|中|高"
    },
    {
      "metric": "血氧",
      "range": "93-99",
      "average": 97,
      "trend": "稳定|偶尔偏低|逐步下降",
      "assessment": "正常范围",
      "concern_level": "无|低|中|高"
    },
    {
      "metric": "体温",
      "range": "36.2-36.8",
      "average": 36.4,
      "trend": "稳定",
      "assessment": "正常",
      "concern_level": "无"
    }
  ],
  "risk_analysis": [
    {
      "condition": "可能提示的状况",
      "evidence": "哪些数据支持此判断（具体到数值和时段）",
      "confidence": "低|中|高",
      "suggestion": "建议行动（可操作、不制造恐慌）"
    }
  ],
  "key_observations": [
    "值得注意的观察1",
    "值得注意的观察2"
  ],
  "recommendations": [
    "对老人的可操作建议1（如：晨起先在床边坐1分钟再站起来）",
    "对子女的参考建议1"
  ],
  "disclaimer": "此为AI辅助分析，仅供参考，不作为医疗诊断依据。如有持续不适请及时就医。"
}"""


# ========== Data Parsing ==========

def parse_sensor_file(filepath):
    """Parse sensor data file into structured records."""
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 7:
                continue

            # Detect if time includes date
            time_str = parts[0]
            date_part = None

            if ':' in time_str and '-' in time_str:
                # Format: "2026-05-21 08:00" — already split by split() into two tokens
                # Actually with split(), "2026-05-21" and "08:00" become separate tokens
                # So parts[0] is date, parts[1] is time
                pass

            # Determine if first two tokens are date+time
            idx = 0
            parsed_time = None
            if '-' in parts[0] and ':' in parts[1]:
                # Date present
                try:
                    parsed_time = datetime.strptime(f"{parts[0]} {parts[1]}", "%Y-%m-%d %H:%M")
                    idx = 2
                except ValueError:
                    idx = 1
            elif ':' in parts[0]:
                # Time only, treat as today
                try:
                    h, m = map(int, parts[0].split(':'))
                    now = datetime.now()
                    parsed_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    idx = 1
                except ValueError:
                    idx = 1
            else:
                idx = 1

            try:
                temp = float(parts[idx])
                hr = int(parts[idx + 1])
                spo2 = int(parts[idx + 2])
                sbp = int(parts[idx + 3])
                dbp = int(parts[idx + 4])
                steps = int(parts[idx + 5])
            except (ValueError, IndexError):
                continue

            note = ' '.join(parts[idx + 6:]) if len(parts) > idx + 6 else ''

            records.append({
                'time': parsed_time.strftime("%Y-%m-%d %H:%M") if parsed_time else parts[0],
                'temperature': temp,
                'heart_rate': hr,
                'blood_oxygen': spo2,
                'sbp': sbp,
                'dbp': dbp,
                'steps': steps,
                'note': note
            })

    return records


def compute_stats(records):
    """Compute per-day and overall statistics."""
    if not records:
        return "", ""

    # Group by date
    daily = {}
    for r in records:
        date_key = r['time'][:10]
        if date_key not in daily:
            daily[date_key] = []
        daily[date_key].append(r)

    daily_lines = []
    for date in sorted(daily.keys()):
        dr = daily[date]
        hrs = [r['heart_rate'] for r in dr]
        sbps = [r['sbp'] for r in dr]
        dbps = [r['dbp'] for r in dr]
        spo2s = [r['blood_oxygen'] for r in dr]
        temps = [r['temperature'] for r in dr]
        steps = [r['steps'] for r in dr]

        def fmt(vals):
            mn, mx = min(vals), max(vals)
            avg = sum(vals) / len(vals)
            return f"{mn:.0f}-{mx:.0f}(均{avg:.1f})" if isinstance(vals[0], int) else f"{mn:.1f}-{mx:.1f}(均{avg:.1f})"

        # Step count is cumulative (累计步数), take max as daily total
        total_steps = max(steps) if steps else 0

        line = f"{date}: {len(dr)}条记录 "
        line += f"心率{fmt(hrs)} " if hrs else ""
        line += f"血压{fmt(sbps)}/{fmt(dbps)} " if sbps else ""
        line += f"血氧{fmt(spo2s)} " if spo2s else ""
        line += f"体温{fmt(temps)} " if temps else ""
        line += f"步数{total_steps}" if steps else ""
        daily_lines.append(line)

    # Overall stats
    all_hrs = [r['heart_rate'] for r in records]
    all_sbps = [r['sbp'] for r in records]
    all_dbps = [r['dbp'] for r in records]
    all_spo2 = [r['blood_oxygen'] for r in records]

    overall = (
        f"心率: {min(all_hrs)}-{max(all_hrs)} (均{sum(all_hrs)/len(all_hrs):.1f}) | "
        f"血压: {min(all_sbps)}/{min(all_dbps)}-{max(all_sbps)}/{max(all_dbps)} "
        f"(均{sum(all_sbps)/len(all_sbps):.1f}/{sum(all_dbps)/len(all_dbps):.1f}) | "
        f"血氧: {min(all_spo2)}-{max(all_spo2)} (均{sum(all_spo2)/len(all_spo2):.1f})"
    )

    return "\n".join(daily_lines), overall


# ========== LLM Analysis ==========

def analyze_with_llm(daily_summary, overall_stats, raw_records):
    """Call LLM API for health analysis."""
    if not LLM_API_KEY:
        return {"error": "未配置 LLM API Key。请设置 LLM_API_KEY 环境变量或带 --api-key 参数运行"}

    timespan = f"{raw_records[0]['time']} 至 {raw_records[-1]['time']}" if len(raw_records) > 1 else raw_records[0]['time']
    days = len(set(r['time'][:10] for r in raw_records))

    # Steps are cumulative (累计步数), take max as daily total
    step_values = [r['steps'] for r in raw_records]
    true_total_steps = max(step_values) if step_values else 0
    step_note = f"当日步数: {true_total_steps} (累计值，取最大值)"
    if true_total_steps > 10000:
        step_note += "（活动量较大）"
    elif true_total_steps < 3000:
        step_note += "（活动较少）"

    user_prompt = f"""## 健康监测数据分析请求

### 患者背景
- 年龄：约70岁（男性长辈）
- 已知病史：高血压
- 用药：降压药（每日18:00晚餐后服用）
- 监测设备：智能手环

### 数据概况
- 时间跨度：{timespan}
- 覆盖天数：{days}天
- 总记录数：{len(raw_records)}条

### 每日统计摘要
{daily_summary}

### 整体统计
{overall_stats}

### 注意事项
- {step_note}
- 患者有高血压，正在服药控制
- 请结合老年人正常生理波动范围进行分析
- 注意晨峰血压、夜间血压模式
- 评估血氧趋势对于呼吸健康的意义
- **所有数值请严格以统计摘要为准，不要自行计算或推测具体数值**

请进行综合健康趋势分析与风险评估，输出指定 JSON 格式。"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}"
    }

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 3000
    }

    try:
        resp = requests.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=90
        )
        resp.raise_for_status()
        result = resp.json()
        content = result['choices'][0]['message']['content']

        # Clean markdown code blocks
        cleaned = content.strip()
        if '```' in cleaned:
            parts = cleaned.split('```')
            for p in parts:
                p = p.strip()
                if p.startswith('{') or p.startswith('json'):
                    cleaned = p.removeprefix('json').strip()
                    break

        return json.loads(cleaned)

    except json.JSONDecodeError as e:
        return {
            "error": f"JSON 解析失败: {e}",
            "raw_response": content
        }
    except requests.exceptions.Timeout:
        return {"error": "API 请求超时（90秒），请稍后重试"}
    except Exception as e:
        return {"error": f"分析失败: {e}"}


# ========== Main ==========

def main():
    # Parse optional CLI args for LLM config
    args = sys.argv[1:]
    filepath = None
    i = 0
    while i < len(args):
        if args[i] == '--api-key' and i + 1 < len(args):
            global LLM_API_KEY
            LLM_API_KEY = args[i + 1]; i += 2
        elif args[i] == '--api-base' and i + 1 < len(args):
            global LLM_BASE_URL
            LLM_BASE_URL = args[i + 1]; i += 2
        elif args[i] == '--model' and i + 1 < len(args):
            global LLM_MODEL
            LLM_MODEL = args[i + 1]; i += 2
        else:
            filepath = args[i]; i += 1

    if not filepath:
        print("用法: python3 health_llm_analysis.py <传感器数据文件>", file=sys.stderr)
        print("文件格式: 时间 体温 心率 血氧 收缩压 舒张压 步数 [备注]", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(filepath):
        print(f"❌ 文件不存在: {filepath}", file=sys.stderr)
        sys.exit(1)

    records = parse_sensor_file(filepath)

    records = parse_sensor_file(filepath)
    if not records:
        print("❌ 未解析到有效数据。请确认文件格式正确。", file=sys.stderr)
        sys.exit(1)

    daily_summary, overall_stats = compute_stats(records)

    # Print progress to stderr (so stdout is clean JSON)
    print(f"📊 {len(records)} 条记录, {len(set(r['time'][:10] for r in records))} 天数据", file=sys.stderr)
    print(f"📈 整体: {overall_stats}", file=sys.stderr)
    print(f"🤖 正在调用 {LLM_MODEL} 分析...", file=sys.stderr)

    result = analyze_with_llm(daily_summary, overall_stats, records)

    if "error" in result:
        print(f"❌ {result['error']}", file=sys.stderr)
        if "raw_response" in result:
            print(f"原始响应:\n{result['raw_response']}", file=sys.stderr)
        sys.exit(1)

    # Output clean JSON to stdout
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # Summary to stderr
    print(f"\n{'='*50}", file=sys.stderr)
    print(f"✅ 整体状态: {result.get('overall_status', 'N/A')}", file=sys.stderr)
    print(f"📋 {result.get('summary', '')}", file=sys.stderr)
    for risk in result.get('risk_analysis', []):
        print(f"⚠️  {risk['condition']} (置信度: {risk['confidence']})", file=sys.stderr)
    print(f"\n{result.get('disclaimer', '')}", file=sys.stderr)


if __name__ == "__main__":
    main()

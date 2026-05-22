#!/usr/bin/env python3
"""
health_daily_pipeline.py — 传感器数据全自动处理流水线（多天分析版）

流程:
  1. 持久化存储当日数据到 data/sensor/
  2. 收集最近 N 天的历史数据
  3. 生成今日可视化图表（复用 health_report_v2.py）
  4. 大模型综合分析（带上多天上下文）
  5. 输出结构化结果（JSON 格式），供 AI 分通道推送

用法:
  python3 tools/health_daily_pipeline.py /tmp/sensor_data_20260522.txt [--days 7]

输出:
  JSON to stdout，包含:
    - level: 规则层评估等级 (🟢🟡🟠🔴)
    - level_name: 等级名称
    - chart_path: 图表文件路径
    - data_span: 分析覆盖的时间范围
    - llm_analysis: 大模型分析（含多天趋势对比）
    - wechat_message: 微信推送用纯文字（给老爸）
    - qq_report: QQ 推送用结构化日报（给小张）
"""

import json
import os
import re
import subprocess
import sys
import shutil
from datetime import datetime, timedelta

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(TOOLS_DIR)
ASSETS_DIR = os.path.join(WORKSPACE, "assets")
SENSOR_DATA_DIR = os.path.join(WORKSPACE, "data", "sensor")
CONTEXT_DAYS = 7  # 默认携带最近7天数据

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(SENSOR_DATA_DIR, exist_ok=True)

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
if not LLM_API_KEY:
    try:
        cfg_path = os.path.expanduser("~/.openclaw/openclaw.json")
        with open(cfg_path) as f:
            cfg = json.load(f)
        key, base = None, None
        for name, p in cfg.get("models", {}).get("providers", {}).items():
            k = p.get("apiKey", "")
            b = p.get("baseUrl", "")
            if k and not k.startswith("__"):
                key, base = k, b
                break
        if key:
            LLM_API_KEY = key
            os.environ["LLM_API_KEY"] = key
    except Exception:
        pass


# ========== Data Persistence ==========

def detect_date_from_filename(filepath):
    """Extract date from filename like sensor_data_20260522.txt or 2026-05-22.txt."""
    basename = os.path.basename(filepath)
    # Try YYYYMMDD
    m = re.search(r'(\d{4})(\d{2})(\d{2})', basename)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # Try YYYY-MM-DD
    m = re.search(r'(\d{4}-\d{2}-\d{2})', basename)
    if m:
        return m.group(1)
    return datetime.now().strftime("%Y-%m-%d")


def save_data_persistently(source_file, date_str):
    """Save sensor data to data/sensor/YYYY-MM-DD.txt with dates prepended."""
    dest = os.path.join(SENSOR_DATA_DIR, f"{date_str}.txt")
    with open(source_file) as f:
        lines = f.readlines()

    # Prepend date to lines that look like sensor data (start with time HH:MM)
    saved_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # If line starts with HH:MM, prepend date
        if re.match(r'^\d{1,2}:\d{2}', line):
            saved_lines.append(f"{date_str} {line}")
        # If line already has date YYYY-MM-DD HH:MM, keep as-is
        elif re.match(r'^\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}', line):
            saved_lines.append(line)

    if not saved_lines:
        # Fallback: save raw data as-is
        with open(source_file) as f:
            raw = f.read().strip()
        if raw:
            saved_lines = [raw]

    with open(dest, 'w') as f:
        f.write('\n'.join(saved_lines) + '\n')

    print(f"💾 数据已持久化: {dest} ({len(saved_lines)}条)", file=sys.stderr)
    return dest


def collect_context_data(date_str, max_days=CONTEXT_DAYS):
    """Collect sensor data from recent days (including current). Returns merged file path."""
    today = datetime.strptime(date_str, "%Y-%m-%d")
    merged_path = os.path.join(SENSOR_DATA_DIR, f"_merged_{date_str}.txt")

    all_records = []
    for i in range(max_days):
        d = today - timedelta(days=i)
        fname = d.strftime("%Y-%m-%d") + ".txt"
        fpath = os.path.join(SENSOR_DATA_DIR, fname)
        if os.path.exists(fpath):
            with open(fpath) as f:
                all_records.extend([l.strip() for l in f if l.strip()])
            print(f"📂 加载历史数据: {fpath}", file=sys.stderr)

    if all_records:
        with open(merged_path, 'w') as f:
            f.write('\n'.join(all_records) + '\n')
        print(f"📊 合并数据: {len(all_records)}条记录, {date_str}(今日)起向前{max_days}天", file=sys.stderr)
        return merged_path, len(all_records)
    return None, 0


# ========== Basic Report + Chart ==========

def parse_basic_report(data_file):
    """Run health_report_v2.py and extract structured assessment."""
    v2_script = os.path.join(TOOLS_DIR, "health_report_v2.py")
    if not os.path.exists(v2_script):
        return None, None, None, None

    try:
        result = subprocess.run(
            ["python3", v2_script, data_file],
            capture_output=True, text=True, timeout=120
        )
        output = result.stdout + "\n" + result.stderr

        level = '🟢'
        level_name = '正常'
        for line in output.split('\n'):
            if '总体评级:' in line:
                parts = line.split()
                if len(parts) >= 3:
                    level = parts[1]
                    level_name = ' '.join(parts[2:])
                break

        chart_path = None
        for line in output.split('\n'):
            if 'Chart saved:' in line or 'chart saved:' in line.lower():
                chart_path = line.split(': ', 1)[1].strip()
                break

        return output, level, level_name, chart_path
    except Exception as e:
        return None, None, None, None


# ========== LLM Analysis (Multi-Day) ==========

def run_llm_analysis(merged_data_file, data_span_desc):
    """Run health_llm_analysis.py on merged multi-day data."""
    llm_script = os.path.join(TOOLS_DIR, "health_llm_analysis.py")
    if not os.path.exists(llm_script):
        return None

    try:
        result = subprocess.run(
            ["python3", llm_script, merged_data_file],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "LLM_API_KEY": LLM_API_KEY}
        )
        stdout = result.stdout.strip()
        if stdout:
            try:
                analysis = json.loads(stdout)
                # Augment with data span info
                analysis['data_span'] = data_span_desc
                return analysis
            except json.JSONDecodeError:
                return {"error": "LLM输出非JSON", "raw": stdout[:500]}
        return None
    except Exception as e:
        return {"error": str(e)}


# ========== Message Builders ==========

def build_wechat_message(basic_report_text, level, level_name, llm, data_span):
    """Build a simple, warm message for 老爸 (WeChat)."""
    lines = []
    lines.append("老爸，今天的健康报告出来了 📋")
    lines.append("")

    level_emoji = {'🟢': '✅', '🟡': '📌', '🟠': '⚠️', '🔴': '🚨'}
    lines.append(f"{level_emoji.get(level, '📋')} 身体状态: {level} {level_name}")
    lines.append("")

    if basic_report_text:
        for line in basic_report_text.split('\n'):
            clean = line.strip()
            if '心率:' in clean and 'avg' in clean:
                lines.append(f"❤️ {clean}")
            elif '血压:' in clean and 'avg' in clean:
                lines.append(f"💓 {clean}")
            elif '血氧:' in clean and 'avg' in clean:
                lines.append(f"🫁 {clean}")
            elif '体温:' in clean and '℃' in clean:
                lines.append(f"🌡️ {clean}")
            elif '步数:' in clean:
                lines.append(f"👟 {clean}")

    lines.append("")

    if llm and isinstance(llm, dict) and llm.get('summary'):
        summary = llm['summary']
        if len(summary) > 80:
            summary = summary[:80] + "……"
        lines.append(f"💬 {summary}")
        lines.append("")

    if llm and isinstance(llm, dict) and llm.get('recommendations'):
        recs = [r for r in llm['recommendations'] if len(r) < 35]
        for r in recs[:2]:
            lines.append(f"👉 {r}")

    if not lines[-1].endswith('😊'):
        lines.append("有情况随时跟我说 😊")

    return '\n'.join(lines)


def build_qq_report(basic_report_text, level, level_name, llm, chart_path, data_span):
    """Build structured daily report for 小张 (QQ)."""
    lines = []
    today_str = datetime.now().strftime("%Y-%m-%d")
    lines.append(f"📋 老爸健康日报 — {today_str}")
    lines.append(f"   覆盖范围: {data_span}")
    lines.append("=" * 30)
    lines.append(f"【规则评估】{level} {level_name}")
    lines.append("")

    if basic_report_text:
        for line in basic_report_text.split('\n'):
            clean = line.strip()
            if clean and not clean.startswith('=') and not clean.startswith('Chart'):
                lines.append(clean)

    if llm and 'summary' in llm:
        lines.append("")
        lines.append("📊 【AI 综合分析（多天对比）】")
        lines.append(f"整体状态: {llm.get('overall_status', 'N/A')}")
        lines.append(f"摘要: {llm['summary']}")
        lines.append("")

        lines.append("⚠️ 风险评估:")
        for risk in llm.get('risk_analysis', []):
            cl_emoji = {'高': '🔴', '中': '🟡', '低': '🟢'}
            ce = cl_emoji.get(risk.get('confidence', ''), '⚪')
            lines.append(f"  {ce} {risk['condition']}")
            lines.append(f"     证据: {risk['evidence'][:100]}...")
            lines.append(f"     建议: {risk['suggestion'][:80]}...")

        lines.append("")
        lines.append("💡 建议:")
        for rec in llm.get('recommendations', []):
            lines.append(f"  • {rec}")

        lines.append("")
        lines.append("📈 各指标趋势:")
        for trend in llm.get('trend_analysis', []):
            cl_emoji = {'无': '✅', '低': '🟢', '中': '🟡', '高': '🔴'}
            ce = cl_emoji.get(trend.get('concern_level', ''), '⚪')
            lines.append(f"  {ce} {trend['metric']}: {trend['assessment'][:60]}")

    if llm and 'key_observations' in llm:
        lines.append("")
        lines.append("🔍 关键观察:")
        for obs in llm['key_observations']:
            lines.append(f"  • {obs}")

    if chart_path and os.path.exists(chart_path):
        lines.append("")
        lines.append("📎 今日趋势图已推送")

    lines.append("")
    disclaimer = (llm or {}).get('disclaimer', '⚠️ 此为AI辅助分析，仅供参考，不作为医疗诊断依据')
    lines.append("— 银发健康守护陪伴官")

    return '\n'.join(lines)


# ========== Main ==========

def main():
    args = sys.argv[1:]
    if not args:
        print(json.dumps({"error": "用法: python3 health_daily_pipeline.py <传感器数据文件> [--days N]"}, ensure_ascii=False))
        sys.exit(1)

    data_file = args[0]
    max_days = CONTEXT_DAYS
    if '--days' in args:
        idx = args.index('--days')
        if idx + 1 < len(args):
            max_days = int(args[idx + 1])

    if not os.path.exists(data_file):
        print(json.dumps({"error": f"文件不存在: {data_file}"}, ensure_ascii=False))
        sys.exit(1)

    date_str = detect_date_from_filename(data_file)

    # --- Step 1: Persist today's data ---
    saved_path = save_data_persistently(data_file, date_str)

    # --- Step 2: Collect multi-day context ---
    merged_path, total_records = collect_context_data(date_str, max_days=max_days)
    data_span = f"最近{max_days}天 ({total_records}条记录)" if merged_path else "仅今日"
    if merged_path:
        print(f"📊 多天合并数据: {merged_path}", file=sys.stderr)
        print(f"📊 覆盖最近{max_days}天, 共{total_records}条记录", file=sys.stderr)

    # --- Step 3: Generate chart (today only) ---
    # health_report_v2.py only handles single-day data, use original /tmp file
    basic_text, level, level_name, chart_path = parse_basic_report(data_file)
    if not level:
        level, level_name = '🟢', '正常'
    if not chart_path:
        chart_path = os.path.join(ASSETS_DIR, "daily_report.png")

    # --- Step 4: LLM analysis (multi-day) ---
    llm_analysis = None
    if merged_path:
        llm_analysis = run_llm_analysis(merged_path, data_span)
    else:
        # Fallback: today only
        llm_analysis = run_llm_analysis(data_file, data_span)

    # --- Step 5: Build messages ---
    wechat_msg = build_wechat_message(basic_text, level, level_name, llm_analysis, data_span)
    qq_msg = build_qq_report(basic_text, level, level_name, llm_analysis, chart_path, data_span)

    # --- Step 6: Output ---
    result = {
        "status": "ok",
        "level": level,
        "level_name": level_name,
        "chart_path": chart_path if os.path.exists(chart_path) else None,
        "data_span": data_span,
        "total_records_across_days": total_records if merged_path else 0,
        "llm_analysis": llm_analysis,
        "wechat_message": wechat_msg,
        "qq_report": qq_msg
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

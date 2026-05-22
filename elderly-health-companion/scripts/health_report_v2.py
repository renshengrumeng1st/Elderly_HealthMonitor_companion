#!/usr/bin/env python3
"""Parse sensor data, evaluate health risk, and generate visualization."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sys, os
from datetime import datetime, timedelta
from matplotlib.font_manager import fontManager

fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
plt.rcParams['font.family'] = 'Noto Sans CJK JP'
plt.rcParams['axes.unicode_minus'] = False

data_file = sys.argv[1] if len(sys.argv) > 1 else '/tmp/sensor_data_20260521.txt'
with open(data_file) as f:
    data_text = f.read().strip()

today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
records = []
for line in data_text.split('\n'):
    if not line.strip():
        continue
    parts = line.strip().split()
    t = parts[0]
    h, m = map(int, t.split(':'))
    dt = today + timedelta(hours=h, minutes=m)
    records.append({
        'time': dt, 'label': t,
        'temp': float(parts[1]), 'hr': int(parts[2]),
        'spo2': int(parts[3]), 'sbp': int(parts[4]),
        'dbp': int(parts[5]), 'steps': int(parts[6]),
        'state': ' '.join(parts[7:]) if len(parts) > 7 else ''
    })

times = [r['time'] for r in records]
hr = [r['hr'] for r in records]
sbp = [r['sbp'] for r in records]
dbp = [r['dbp'] for r in records]
spo2 = [r['spo2'] for r in records]
temp = [r['temp'] for r in records]

# Stats
hr_avg, hr_min, hr_max = round(sum(hr)/len(hr),1), min(hr), max(hr)
sbp_avg, sbp_min, sbp_max = round(sum(sbp)/len(sbp),1), min(sbp), max(sbp)
dbp_avg, dbp_min, dbp_max = round(sum(dbp)/len(dbp),1), min(dbp), max(dbp)
spo2_avg, spo2_min, spo2_max = round(sum(spo2)/len(spo2),1), min(spo2), max(spo2)
temp_avg = round(sum(temp)/len(temp),1)
total_steps = max(r['steps'] for r in records)

# Count danger zones
spo2_low_count = sum(1 for s in spo2 if s < 90)
spo2_borderline_count = sum(1 for s in spo2 if 90 <= s < 95)
sbp_high_count = sum(1 for s in sbp if s > 140)
dbp_high_count = sum(1 for s in dbp if s > 90)
hr_alert_count = sum(1 for h in hr if h > 80)

# Determine overall level
level = '🟢'
level_name = '正常'
alerts = []
if dbp_max > 100:
    level = '🔴'; level_name = '紧急'
    alerts.append(f'舒张压超100 ({dbp_max} mmHg)')
elif spo2_min < 88:
    level = '🔴'; level_name = '紧急'
    alerts.append(f'血氧低于88% (最低{spo2_min}%)')
elif sbp_max > 160:
    level = '🔴'; level_name = '紧急'
    alerts.append(f'收缩压超160 ({sbp_max} mmHg)')
elif dbp_max >= 90:
    level = '🟠'; level_name = '预警'
    alerts.append(f'舒张压超标 ({dbp_max} mmHg)')
elif sbp_max > 140:
    level = '🟠'; level_name = '预警'
    alerts.append(f'收缩压超标 ({sbp_max} mmHg)')
elif spo2_min < 90:
    level = '🟠'; level_name = '预警'
    alerts.append(f'血氧偏低 (最低{spo2_min}%)')
elif hr_max > 100:
    level = '🟡'; level_name = '关注'
    alerts.append(f'心率偏高 ({hr_max} bpm)')
elif spo2_min < 95 or sbp_max > 130:
    level = '🟡'; level_name = '关注'

# Print assessment
print(f"=== 健康评估 ===")
print(f"总体评级: {level} {level_name}")
print(f"基础信息: 72岁 男 高血压+冠心病")
print(f"心率: {hr_avg} avg ({hr_min}-{hr_max}) | ≥80次共{hr_alert_count}次")
print(f"血压: {sbp_avg}/{dbp_avg} avg ({sbp_min}-{sbp_max}/{dbp_min}-{dbp_max})")
print(f"  收缩压>140: {sbp_high_count}次 | 舒张压>90: {dbp_high_count}次")
print(f"血氧: {spo2_avg}% avg ({spo2_min}-{spo2_max}) | <90%: {spo2_low_count}次 | <95%: {spo2_borderline_count+spo2_low_count}次")
print(f"体温: {temp_avg}℃ avg")
print(f"步数: {total_steps}")
if alerts:
    print(f"告警项: {' | '.join(alerts)}")

# Find peak risk time
peak_idx = spo2.index(spo2_min)
peak_time = records[peak_idx]['label']
peak_hr = records[peak_idx]['hr']
peak_sbp = records[peak_idx]['sbp']
peak_dbp = records[peak_idx]['dbp']
peak_spo2 = records[peak_idx]['spo2']
peak_state = records[peak_idx]['state']
print(f"最高风险时刻: {peak_time} (HR:{peak_hr} BP:{peak_sbp}/{peak_dbp} SpO2:{peak_spo2}%) {peak_state}")

# Create figure
fig, axes = plt.subplots(4, 1, figsize=(16, 12), sharex=True)
fig.patch.set_facecolor('#1a1a2e')
clr = {
    'bg': '#1a1a2e', 'text': '#e0e0e0', 'hr': '#ff6b6b',
    'bp_hi': '#ff6b35', 'bp_lo': '#ffd93d', 'spo2': '#6bcb77',
    'temp': '#4d96ff', 'grid': '#2d2d5e', 'danger': '#ef444480',
    'warning': '#f9731680'
}

for ax in axes:
    ax.set_facecolor('#16213e')
    ax.tick_params(colors=clr['text'], labelsize=9)
    ax.grid(True, alpha=0.15, color=clr['grid'])
    for spine in ax.spines.values():
        spine.set_color(clr['grid'])

# 1. Heart Rate
axes[0].plot(times, hr, color=clr['hr'], linewidth=1.8, marker='o', markersize=3)
axes[0].fill_between(times, hr, alpha=0.1, color=clr['hr'])
axes[0].axhline(y=80, color='#f97316', linestyle='--', linewidth=1, alpha=0.6, label='关注线 80')
axes[0].axhline(y=100, color='#ef4444', linestyle='--', linewidth=1, alpha=0.6, label='预警线 100')
axes[0].set_ylabel('心率 (次/分)', color=clr['hr'], fontsize=11, fontweight='bold')
axes[0].set_title(f'⚠️ 心率趋势 ({hr_min}-{hr_max} bpm)  夜间持续偏高', color=clr['text'], fontsize=13, fontweight='bold', loc='left')
axes[0].legend(loc='upper right', fontsize=8, facecolor='#1a1a2e', edgecolor=clr['grid'], labelcolor=clr['text'])
axes[0].set_ylim(55, 105)

# 2. Blood Pressure
axes[1].plot(times, sbp, color=clr['bp_hi'], linewidth=1.8, marker='o', markersize=3, label='收缩压')
axes[1].plot(times, dbp, color=clr['bp_lo'], linewidth=1.8, marker='o', markersize=3, label='舒张压')
# Danger zones
axes[1].axhline(y=140, color='#f97316', linestyle='--', linewidth=1, alpha=0.6, label='收缩压预警 140')
axes[1].axhline(y=160, color='#ef4444', linestyle='--', linewidth=1, alpha=0.6, label='收缩压紧急 160')
axes[1].axhline(y=90, color='#ef4444', linestyle=':', linewidth=1, alpha=0.6, label='舒张压预警 90')
axes[1].fill_between(times, 140, 165, alpha=0.08, color='#f97316', label='高血压预警区')
axes[1].fill_between(times, 90, 110, alpha=0.10, color='#ef4444', label='舒张压危险区')
axes[1].set_ylabel('血压 (mmHg)', color=clr['bp_lo'], fontsize=11, fontweight='bold')
axes[1].set_title(f'🔴 血压趋势 ({sbp_min}-{sbp_max} / {dbp_min}-{dbp_max} mmHg)  多时段超标', color=clr['text'], fontsize=13, fontweight='bold', loc='left')
axes[1].legend(loc='upper right', fontsize=7, facecolor='#1a1a2e', edgecolor=clr['grid'], labelcolor=clr['text'], ncol=2)
axes[1].set_ylim(55, 180)

# 3. SpO2
axes[2].plot(times, spo2, color=clr['spo2'], linewidth=1.8, marker='o', markersize=3)
axes[2].fill_between(times, spo2, alpha=0.1, color=clr['spo2'])
axes[2].axhline(y=95, color='#f97316', linestyle='--', linewidth=1, alpha=0.6, label='正常下线 95%')
axes[2].axhline(y=90, color='#ef4444', linestyle='-', linewidth=1.2, alpha=0.7, label='紧急线 90%')
axes[2].fill_between(times, 85, 90, alpha=0.15, color='#ef444488', label='危险低氧区')
# Annotate all dangerously low SpO2
for i, r in enumerate(records):
    if r['spo2'] <= 88:
        axes[2].annotate(f"{r['label']}\n{r['spo2']}%", (r['time'], r['spo2']),
                         fontsize=6, color='#ef4444', fontweight='bold',
                         xytext=(0, -18), textcoords='offset points', ha='center')
axes[2].set_ylabel('血氧 (%)', color=clr['spo2'], fontsize=11, fontweight='bold')
axes[2].set_title(f'🚨 血氧饱和度 ({spo2_min}-{spo2_max}%)  近半时段低于95%！', color='#ef4444', fontsize=13, fontweight='bold', loc='left')
axes[2].legend(loc='upper right', fontsize=8, facecolor='#1a1a2e', edgecolor=clr['grid'], labelcolor=clr['text'])
axes[2].set_ylim(84, 99)

# 4. Temperature
axes[3].plot(times, temp, color=clr['temp'], linewidth=1.8, marker='o', markersize=3)
axes[3].fill_between(times, temp, alpha=0.1, color=clr['temp'])
axes[3].axhline(y=36.0, color='#4ade80', linestyle='--', linewidth=0.8, alpha=0.4)
axes[3].axhline(y=37.3, color='#f97316', linestyle='--', linewidth=0.8, alpha=0.4)
axes[3].set_ylabel('体温 (℃)', color=clr['temp'], fontsize=11, fontweight='bold')
axes[3].set_title(f'🌡️ 体温趋势 ({min(temp):.1f}-{max(temp):.1f}℃)  正常', color=clr['text'], fontsize=13, fontweight='bold', loc='left')
axes[3].set_ylim(35.8, 37.8)

axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
axes[-1].xaxis.set_major_locator(mdates.HourLocator(interval=2))
axes[-1].set_xlabel('时间', color=clr['text'], fontsize=11)

# Summary
summary = (
    f"🔴 {level_name} | 72岁 男 高血压+冠心病 | "
    f"HR {hr_avg}({hr_min}-{hr_max}) | "
    f"BP {sbp_avg}/{dbp_avg}({sbp_min}-{sbp_max}/{dbp_min}-{dbp_max}) | "
    f"SpO2 {spo2_avg}%({spo2_min}-{spo2_max}) | "
    f"步数 {total_steps}"
)
fig.text(0.5, 0.008, summary, ha='center', fontsize=8, color='#ef4444', style='italic')

plt.tight_layout(rect=[0, 0.04, 1, 1])
out_path = '/root/.openclaw/workspace/assets/daily_report.png'
plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
plt.close()
print(f"\nChart saved: {out_path}")

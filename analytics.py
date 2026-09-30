import io
import base64
import sqlite3
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from database import DB_PATH

# Palette
PRIMARY_COLOR = '#4f46e5'     # Indigo
SECONDARY_COLOR = '#06b6d4'   # Cyan
WARNING_COLOR = '#f59e0b'     # Amber
DANGER_COLOR = '#ef4444'      # Rose
SUCCESS_COLOR = '#10b981'     # Emerald
SLATE_COLOR = '#64748b'       # Slate

def load_data():
    conn = sqlite3.connect(DB_PATH)
    complaints_query = '''
    SELECT 
        c.id, c.user_id, c.asset_id, c.room_no, c.floor, c.issue_type, 
        c.description, c.date_filed, c.status, c.is_anonymous, c.affected_students_count,
        a.asset_type, a.asset_code,
        r.resolved_date, r.resolved_by, r.remarks
    FROM complaints c
    JOIN assets a ON c.asset_id = a.id
    LEFT JOIN resolution_log r ON c.id = r.complaint_id
    '''
    df = pd.read_sql_query(complaints_query, conn)
    assets_df = pd.read_sql_query('SELECT * FROM assets', conn)
    conn.close()

    if not df.empty:
        df['date_filed'] = pd.to_datetime(df['date_filed'])
        if 'resolved_date' in df.columns:
            df['resolved_date'] = pd.to_datetime(df['resolved_date'])
            df['resolution_days'] = (df['resolved_date'] - df['date_filed']).dt.total_seconds() / (24 * 3600)
        else:
            df['resolution_days'] = np.nan
        df['month_year'] = df['date_filed'].dt.to_period('M').astype(str)

    return df, assets_df

def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=130, facecolor='#ffffff', edgecolor='none')
    buf.seek(0)
    img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close(fig)
    return img_b64

def generate_analytics_and_charts():
    df, assets_df = load_data()
    
    if df.empty:
        return {
            'charts': {},
            'metrics': {},
            'replacement_candidates': [],
            'hotspot_summary': {},
            'prediction_insights': []
        }

    # 1. Summary Metrics
    total_complaints = len(df)
    pending_count = len(df[df['status'] == 'Pending'])
    in_progress_count = len(df[df['status'] == 'In Progress'])
    resolved_count = len(df[df['status'] == 'Resolved'])
    avg_resolution_days = float(round(df['resolution_days'].mean(), 1)) if not df['resolution_days'].dropna().empty else 0.0
    total_affected_students = int(df['affected_students_count'].sum())

    # 2. Asset-wise breakdown counts & Replacement candidate identification
    # Assets with 3+ complaints
    asset_complaint_counts = df.groupby(['asset_id', 'asset_code', 'asset_type', 'room_no', 'floor']).size().reset_index(name='complaint_count')
    # Filter for last 6 months (180 days)
    six_months_ago = datetime.now() - timedelta(days=180)
    recent_df = df[df['date_filed'] >= six_months_ago]
    recent_counts = recent_df.groupby('asset_id').size().to_dict()

    asset_complaint_counts['recent_complaint_count'] = asset_complaint_counts['asset_id'].map(recent_counts).fillna(0).astype(int)
    asset_complaint_counts['needs_replacement'] = asset_complaint_counts['recent_complaint_count'] >= 3

    replacement_candidates = asset_complaint_counts[asset_complaint_counts['needs_replacement']].sort_values(by='recent_complaint_count', ascending=False).to_dict(orient='records')

    # 3. Generate Matplotlib Charts
    charts = {}

    # Chart A: Complaints by Asset Type
    fig, ax = plt.subplots(figsize=(6, 3.8))
    asset_type_counts = df['asset_type'].value_counts()
    colors = [PRIMARY_COLOR, SECONDARY_COLOR, WARNING_COLOR, DANGER_COLOR, SUCCESS_COLOR, SLATE_COLOR]
    bars = ax.bar(asset_type_counts.index, asset_type_counts.values, color=colors[:len(asset_type_counts)], width=0.55, edgecolor='#e2e8f0', linewidth=1)
    ax.set_title('Complaints Distribution by Asset Type', fontsize=12, fontweight='bold', pad=12, color='#1e293b')
    ax.set_ylabel('Number of Complaints', fontsize=10, color='#475569')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cbd5e1')
    ax.spines['bottom'].set_color('#cbd5e1')
    ax.yaxis.grid(True, linestyle='--', alpha=0.5, color='#e2e8f0')
    ax.set_axisbelow(True)
    # Add count labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{int(height)}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),  
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='600', color='#1e293b')
    plt.xticks(rotation=15, ha='right', fontsize=9, color='#334155')
    charts['asset_type'] = fig_to_base64(fig)

    # Chart B: Floor-wise Active vs Resolved Breakdown
    fig, ax = plt.subplots(figsize=(6, 3.8))
    floor_status = pd.crosstab(df['floor'], df['status'])
    # Ensure all statuses present
    for s in ['Pending', 'In Progress', 'Resolved']:
        if s not in floor_status.columns:
            floor_status[s] = 0
    floor_status = floor_status[['Pending', 'In Progress', 'Resolved']]
    floor_labels = [f"Floor {fl}" for fl in floor_status.index]
    
    x = np.arange(len(floor_labels))
    width = 0.25
    ax.bar(x - width, floor_status['Pending'], width, label='Pending', color=DANGER_COLOR, alpha=0.9)
    ax.bar(x, floor_status['In Progress'], width, label='In Progress', color=WARNING_COLOR, alpha=0.9)
    ax.bar(x + width, floor_status['Resolved'], width, label='Resolved', color=SUCCESS_COLOR, alpha=0.9)
    
    ax.set_title('Floor-wise Complaint Status Distribution', fontsize=12, fontweight='bold', pad=12, color='#1e293b')
    ax.set_xticks(x)
    ax.set_xticklabels(floor_labels, fontsize=9, color='#334155')
    ax.set_ylabel('Complaint Count', fontsize=10, color='#475569')
    ax.legend(frameon=False, fontsize=9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cbd5e1')
    ax.spines['bottom'].set_color('#cbd5e1')
    ax.yaxis.grid(True, linestyle='--', alpha=0.5, color='#e2e8f0')
    ax.set_axisbelow(True)
    charts['floor_distribution'] = fig_to_base64(fig)

    # Chart C: Monthly Complaint Timeline Trends
    fig, ax = plt.subplots(figsize=(6, 3.8))
    monthly_trend = df.groupby(['month_year', 'status']).size().unstack(fill_value=0)
    months = monthly_trend.index.tolist()
    if len(months) == 1:
        # If single month, plot a simple bar
        monthly_trend.plot(kind='bar', ax=ax, color=[DANGER_COLOR, WARNING_COLOR, SUCCESS_COLOR][:len(monthly_trend.columns)])
    else:
        ax.plot(months, monthly_trend.sum(axis=1), marker='o', linewidth=2.5, color=PRIMARY_COLOR, label='Total Filed')
        if 'Resolved' in monthly_trend.columns:
            ax.plot(months, monthly_trend['Resolved'], marker='s', linewidth=2, color=SUCCESS_COLOR, linestyle='--', label='Resolved')
    ax.set_title('Monthly Complaint Trajectory', fontsize=12, fontweight='bold', pad=12, color='#1e293b')
    ax.set_ylabel('Complaints', fontsize=10, color='#475569')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cbd5e1')
    ax.spines['bottom'].set_color('#cbd5e1')
    ax.yaxis.grid(True, linestyle='--', alpha=0.5, color='#e2e8f0')
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9)
    plt.xticks(rotation=20, ha='right', fontsize=9, color='#334155')
    charts['monthly_trend'] = fig_to_base64(fig)

    # Chart D: Status Donut Chart
    fig, ax = plt.subplots(figsize=(5, 3.8))
    status_counts = df['status'].value_counts()
    status_color_map = {'Pending': DANGER_COLOR, 'In Progress': WARNING_COLOR, 'Resolved': SUCCESS_COLOR}
    chart_colors = [status_color_map.get(s, SLATE_COLOR) for s in status_counts.index]
    
    wedges, texts, autotexts = ax.pie(
        status_counts.values,
        labels=status_counts.index,
        autopct='%1.0f%%',
        startangle=140,
        colors=chart_colors,
        wedgeprops=dict(width=0.45, edgecolor='white', linewidth=2),
        textprops=dict(color="#1e293b", fontsize=9, fontweight='500')
    )
    for at in autotexts:
        at.set_color('white')
        at.set_fontsize(9)
        at.set_fontweight('bold')
    ax.set_title('Overall Status Ratio', fontsize=12, fontweight='bold', pad=12, color='#1e293b')
    charts['status_donut'] = fig_to_base64(fig)

    # Chart E: Issue Type Frequency
    fig, ax = plt.subplots(figsize=(6, 3.8))
    issue_counts = df['issue_type'].value_counts()
    bars = ax.barh(issue_counts.index, issue_counts.values, color=SECONDARY_COLOR, height=0.5, edgecolor='#e2e8f0')
    ax.set_title('Reported Issue Types', fontsize=12, fontweight='bold', pad=12, color='#1e293b')
    ax.set_xlabel('Count', fontsize=10, color='#475569')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cbd5e1')
    ax.spines['bottom'].set_color('#cbd5e1')
    ax.xaxis.grid(True, linestyle='--', alpha=0.5, color='#e2e8f0')
    ax.set_axisbelow(True)
    for bar in bars:
        width = bar.get_width()
        ax.annotate(f'{int(width)}',
                    xy=(width, bar.get_y() + bar.get_height() / 2),
                    xytext=(4, 0),
                    textcoords="offset points",
                    ha='left', va='center', fontsize=9, fontweight='600', color='#1e293b')
    charts['issue_type'] = fig_to_base64(fig)

    # 4. Trend-Based Predictions & Hotspot Analytics using Pandas
    # A. Floor failure hotspot index
    floor_group = df.groupby('floor').agg(
        total_complaints=('id', 'count'),
        unresolved_complaints=('status', lambda s: (s != 'Resolved').sum()),
        total_affected_students=('affected_students_count', 'sum')
    ).reset_index()
    floor_group['vulnerability_score'] = (
        floor_group['total_complaints'] * 1.5 + 
        floor_group['unresolved_complaints'] * 3.0 + 
        floor_group['total_affected_students'] * 0.8
    ).round(1)
    floor_hotspots = floor_group.sort_values(by='vulnerability_score', ascending=False).to_dict(orient='records')

    # B. Asset-type failure rate & MTBF (Mean Time Between Failures) estimate
    type_group = df.groupby('asset_type').agg(
        total_issues=('id', 'count'),
        noise_issues=('issue_type', lambda it: (it == 'Making noise').sum()),
        damaged_issues=('issue_type', lambda it: (it == 'Damaged').sum()),
        not_working=('issue_type', lambda it: (it == 'Not working').sum())
    ).reset_index()
    total_assets_per_type = assets_df.groupby('asset_type').size().to_dict()
    type_group['installed_base'] = type_group['asset_type'].map(total_assets_per_type).fillna(1)
    type_group['breakdown_rate_pct'] = ((type_group['total_issues'] / type_group['installed_base']) * 100).round(1)
    type_metrics = type_group.sort_values(by='breakdown_rate_pct', ascending=False).to_dict(orient='records')

    # C. Prediction Insights (Predictive Failure Warnings)
    prediction_insights = []
    
    # 1. Hotspot floor prediction
    if floor_hotspots:
        top_floor = floor_hotspots[0]
        prediction_insights.append({
            'level': 'high',
            'title': f"Floor {top_floor['floor']} Maintenance Hotspot Alert",
            'text': f"Floor {top_floor['floor']} has recorded the highest failure intensity (Vulnerability Score: {top_floor['vulnerability_score']}, {top_floor['unresolved_complaints']} active issues). Pre-emptive floor audit is strongly recommended.",
            'action': 'Schedule Comprehensive Floor Audit'
        })

    # 2. Asset replacement prediction
    if replacement_candidates:
        top_repl = replacement_candidates[0]
        prediction_insights.append({
            'level': 'danger',
            'title': f"Repeated Breakdown: {top_repl['asset_code']} in Room {top_repl['room_no']}",
            'text': f"This {top_repl['asset_type']} has logged {top_repl['recent_complaint_count']} breakdowns within 6 months. Continued patching incurs diminishing returns. Replace assembly to prevent emergency downtime.",
            'action': f"Approve Asset Replacement for {top_repl['asset_code']}"
        })

    # 3. High-breakdown asset class trend
    if type_metrics:
        top_type = type_metrics[0]
        prediction_insights.append({
            'level': 'warning',
            'title': f"{top_type['asset_type']}s Exhibit Highest Failure Rate ({top_type['breakdown_rate_pct']}%)",
            'text': f"Historical trend indicates {top_type['asset_type']} units have the highest frequency of '{top_type['not_working']} complete outages' and '{top_type['noise_issues']} mechanical noise alerts'. Recommend procuring spare components.",
            'action': f"Restock {top_type['asset_type']} Spare Inventory"
        })

    metrics = {
        'total_complaints': total_complaints,
        'pending_count': pending_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'avg_resolution_days': avg_resolution_days,
        'total_affected_students': total_affected_students,
        'replacement_count': len(replacement_candidates)
    }

    return {
        'charts': charts,
        'metrics': metrics,
        'replacement_candidates': replacement_candidates,
        'floor_hotspots': floor_hotspots,
        'type_metrics': type_metrics,
        'prediction_insights': prediction_insights
    }

if __name__ == '__main__':
    data = generate_analytics_and_charts()
    print("Analytics processed successfully!")
    print("Metrics:", data['metrics'])
    print("Replacement candidates count:", len(data['replacement_candidates']))
    print("Charts generated:", list(data['charts'].keys()))

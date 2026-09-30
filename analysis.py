import os
import tempfile
# Ensure Matplotlib has write permissions on cloud environments like Render
os.environ['MPLCONFIGDIR'] = os.environ.get('MPLCONFIGDIR', tempfile.gettempdir())
import sqlite3
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

from models import DB_PATH

CHARTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'charts')
os.makedirs(CHARTS_DIR, exist_ok=True)

# Severity weights definition as per Feature 8
# Electrical = 3 (Fan, Light, Switchboard)
# Plumbing = 2 (Geyser, Tap)
# Other = 1 (Other)
def get_severity_weight(asset_type):
    atype = str(asset_type).strip().title()
    if atype in ['Fan', 'Light', 'Switchboard', 'Electrical']:
        return 3
    elif atype in ['Geyser', 'Tap', 'Plumbing']:
        return 2
    else:
        return 1

def calculate_impact_score(affected_students_count, asset_type):
    weight = get_severity_weight(asset_type)
    try:
        count = int(affected_students_count)
    except (ValueError, TypeError):
        count = 1
    return count * weight

def load_data():
    conn = sqlite3.connect(DB_PATH)
    query = '''
    SELECT 
        c.id, c.user_id, c.asset_id, c.room_no, c.floor, c.issue_type,
        c.description, c.date_filed, c.status, c.is_anonymous, c.affected_students_count,
        a.asset_type, a.asset_code,
        u.name AS user_name, u.email AS user_email,
        r.resolved_date, r.resolved_by, r.remarks
    FROM complaints c
    JOIN assets a ON c.asset_id = a.id
    LEFT JOIN users u ON c.user_id = u.id
    LEFT JOIN resolution_log r ON c.id = r.complaint_id
    '''
    df = pd.read_sql_query(query, conn)
    assets_df = pd.read_sql_query('SELECT * FROM assets', conn)
    conn.close()

    if not df.empty:
        df['date_filed'] = pd.to_datetime(df['date_filed'])
        df['severity_weight'] = df['asset_type'].apply(get_severity_weight)
        df['impact_score'] = df['affected_students_count'] * df['severity_weight']
        df['month_period'] = df['date_filed'].dt.to_period('M')
        df['month_str'] = df['month_period'].astype(str)

    return df, assets_df

def generate_charts():
    """Generates server-side bar chart and pie chart, saves to static/charts/."""
    df, _ = load_data()
    
    floor_chart_path = os.path.join(CHARTS_DIR, 'floor_bar.png')
    asset_chart_path = os.path.join(CHARTS_DIR, 'asset_pie.png')

    if df.empty:
        return {'floor_bar': 'charts/floor_bar.png', 'asset_pie': 'charts/asset_pie.png'}

    # 1. Bar Chart: Complaint Count by Floor
    fig, ax = plt.subplots(figsize=(6, 4))
    floor_counts = df['floor'].value_counts().sort_index()
    labels = [f"Floor {fl}" for fl in floor_counts.index]
    colors = ['#4f46e5', '#06b6d4', '#8b5cf6', '#3b82f6'][:len(floor_counts)]
    
    bars = ax.bar(labels, floor_counts.values, color=colors, width=0.55, edgecolor='#cbd5e1')
    ax.set_title('Complaints Count by Floor', fontsize=12, fontweight='bold', pad=12, color='#1e293b')
    ax.set_ylabel('Total Complaints', fontsize=10, color='#475569')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cbd5e1')
    ax.spines['bottom'].set_color('#cbd5e1')
    ax.yaxis.grid(True, linestyle='--', alpha=0.6, color='#e2e8f0')
    ax.set_axisbelow(True)

    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{int(height)}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 4),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold', color='#1e293b')

    plt.tight_layout()
    fig.savefig(floor_chart_path, dpi=120)
    plt.close(fig)

    # 2. Pie Chart: Complaint Distribution by Asset Type
    fig, ax = plt.subplots(figsize=(6, 4))
    asset_counts = df['asset_type'].value_counts()
    pie_colors = ['#4f46e5', '#06b6d4', '#f59e0b', '#ef4444', '#10b981', '#64748b'][:len(asset_counts)]

    wedges, texts, autotexts = ax.pie(
        asset_counts.values,
        labels=asset_counts.index,
        autopct='%1.1f%%',
        startangle=140,
        colors=pie_colors,
        wedgeprops=dict(edgecolor='white', linewidth=2)
    )
    for at in autotexts:
        at.set_color('white')
        at.set_fontsize(9)
        at.set_fontweight('bold')
    for t in texts:
        t.set_fontsize(9)
        t.set_color('#1e293b')

    ax.set_title('Complaint Distribution by Asset Type', fontsize=12, fontweight='bold', pad=12, color='#1e293b')
    plt.tight_layout()
    fig.savefig(asset_chart_path, dpi=120)
    plt.close(fig)

    return {
        'floor_bar': 'charts/floor_bar.png',
        'asset_pie': 'charts/asset_pie.png'
    }

def get_trend_predictions():
    """
    Feature 4: Trend-Based Prediction
    Use Pandas to group complaints by room/floor/asset_type by month.
    Calculate simple moving average of complaint count over last 3 months per room/floor.
    Display a projected estimate for next month (e.g. Room 204: 2 -> 3 -> 5 complaints trend, projected 6-7 next month).
    """
    df, assets_df = load_data()
    if df.empty:
        return {'room_predictions': [], 'floor_predictions': []}

    now = datetime.now()
    # Define last 3 full/recent months
    # E.g. month-3, month-2, month-1
    # Create complete monthly index for each room
    all_rooms = sorted(assets_df['room_no'].unique().tolist())
    all_floors = sorted(assets_df['floor'].unique().tolist())

    # Build monthly period groups
    # Group by room_no and month_period
    monthly_room_counts = df.groupby(['room_no', 'month_period']).size().unstack(fill_value=0)
    
    # Sort columns by period
    periods = sorted(df['month_period'].unique())
    last_3_periods = periods[-3:] if len(periods) >= 3 else periods
    period_labels = [p.strftime('%b %Y') for p in last_3_periods]

    room_predictions = []
    for r in all_rooms:
        counts = []
        for p in last_3_periods:
            if r in monthly_room_counts.index and p in monthly_room_counts.columns:
                counts.append(int(monthly_room_counts.loc[r, p]))
            else:
                counts.append(0)

        # 3-month moving average
        # Also compute trend direction (positive slope = increasing)
        avg_3m = round(float(np.mean(counts)), 1)
        
        # Projected estimate for next month
        # If trend is accelerating (e.g. 2 -> 3 -> 5), project upper bound
        if len(counts) == 3 and counts[2] > counts[1] >= counts[0]:
            diff = counts[2] - counts[1]
            projected_low = counts[2] + 1
            projected_high = counts[2] + diff + 1
            projected_str = f"{projected_low} - {projected_high}"
            trend_badge = "Rapid Increase"
            badge_color = "danger"
        elif avg_3m > 2:
            projected_low = int(np.floor(avg_3m))
            projected_high = int(np.ceil(avg_3m + 1))
            projected_str = f"{projected_low} - {projected_high}"
            trend_badge = "High"
            badge_color = "warning"
        elif avg_3m >= 1:
            projected_str = f"{int(np.round(avg_3m))} - {int(np.round(avg_3m + 1))}"
            trend_badge = "Moderate"
            badge_color = "info"
        else:
            projected_str = "0 - 1"
            trend_badge = "Stable"
            badge_color = "success"

        trend_sequence_str = " → ".join(str(c) for c in counts)

        floor_num = 1
        for ch in str(r):
            if ch.isdigit():
                floor_num = int(ch)
                break

        room_predictions.append({
            'room_no': r,
            'floor': floor_num,
            'history': counts,
            'history_str': trend_sequence_str,
            'moving_avg': avg_3m,
            'projected_next_month': projected_str,
            'trend_badge': trend_badge,
            'badge_color': badge_color
        })

    # Sort rooms with highest moving average first
    room_predictions.sort(key=lambda x: (x['moving_avg'], x['room_no']), reverse=True)

    # Floor-level predictions
    monthly_floor_counts = df.groupby(['floor', 'month_period']).size().unstack(fill_value=0)
    floor_predictions = []
    for fl in all_floors:
        f_counts = []
        for p in last_3_periods:
            if fl in monthly_floor_counts.index and p in monthly_floor_counts.columns:
                f_counts.append(int(monthly_floor_counts.loc[fl, p]))
            else:
                f_counts.append(0)
        f_avg = round(float(np.mean(f_counts)), 1)
        f_trend_str = " → ".join(str(c) for c in f_counts)
        f_proj = f"{max(1, int(np.round(f_avg)))} - {int(np.round(f_avg + 2))}"

        floor_predictions.append({
            'floor': fl,
            'history_str': f_trend_str,
            'moving_avg': f_avg,
            'projected_next_month': f_proj
        })

    return {
        'period_labels': period_labels,
        'room_predictions': room_predictions,
        'floor_predictions': floor_predictions
    }

def get_heatmap_data():
    """
    Feature 7: Visual Heatmap
    Build a simple grid representing hostel floors/rooms.
    Color-code each room cell based on complaint count in last 30 days:
    - green (0-1)
    - yellow (2-3)
    - red (4+)
    """
    conn = sqlite3.connect(DB_PATH)
    assets_df = pd.read_sql_query('SELECT DISTINCT floor, room_no FROM assets ORDER BY floor DESC, room_no ASC', conn)
    
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    complaints_query = f'''
        SELECT room_no, COUNT(*) as count_30d
        FROM complaints
        WHERE date_filed >= '{thirty_days_ago}'
        GROUP BY room_no
    '''
    c_df = pd.read_sql_query(complaints_query, conn)
    conn.close()

    count_map = dict(zip(c_df['room_no'], c_df['count_30d'])) if not c_df.empty else {}

    # Organize rooms by floor
    floors_data = {}
    for _, row in assets_df.iterrows():
        fl = int(row['floor'])
        room = str(row['room_no'])
        count = count_map.get(room, 0)

        if count <= 1:
            color = 'green'
            bg = '#d1fae5'
            border = '#10b981'
            text_color = '#065f46'
            label = 'Normal (0-1)'
        elif count <= 3:
            color = 'yellow'
            bg = '#fef3c7'
            border = '#f59e0b'
            text_color = '#92400e'
            label = 'Elevated (2-3)'
        else:
            color = 'red'
            bg = '#fee2e2'
            border = '#ef4444'
            text_color = '#991b1b'
            label = 'Critical (4+)'

        if fl not in floors_data:
            floors_data[fl] = []

        floors_data[fl].append({
            'room_no': room,
            'count': count,
            'color': color,
            'bg': bg,
            'border': border,
            'text_color': text_color,
            'label': label
        })

    return floors_data

if __name__ == '__main__':
    charts = generate_charts()
    print("Generated charts:", charts)
    preds = get_trend_predictions()
    if preds['room_predictions']:
        top_p = preds['room_predictions'][0]
        print(f"Sample room prediction: Room {top_p['room_no']}, moving_avg: {top_p['moving_avg']}, projected: {top_p['projected_next_month']}")
    heatmap = get_heatmap_data()
    print("Floors in heatmap:", list(heatmap.keys()))

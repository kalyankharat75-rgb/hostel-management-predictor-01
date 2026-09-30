import os
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from models import get_db, init_db, seed_db
from analysis import (
    calculate_impact_score,
    generate_charts,
    get_trend_predictions,
    get_heatmap_data,
    get_severity_weight
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'hostel_predictor_secret_key_2026_super_secure')

# Ensure DB & static directories are ready
init_db()
seed_db()
generate_charts()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Admin authentication required.', 'warning')
            return redirect(url_for('login', next=request.url))
        if session.get('role') != 'admin':
            flash('Access restricted to Hostel Administrators.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user():
    return {
        'current_user': {
            'id': session.get('user_id'),
            'name': session.get('name'),
            'email': session.get('email'),
            'role': session.get('role'),
            'room_no': session.get('room_no'),
            'floor': session.get('floor')
        } if 'user_id' in session else None,
        'current_time': datetime.now()
    }

# ----------------- HOME & AUTH ----------------- #

@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM complaints")
    total_complaints = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Resolved'")
    resolved_complaints = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Pending'")
    pending_complaints = cursor.fetchone()[0]
    
    # 6-month threshold replacement count
    six_months_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        SELECT COUNT(*) FROM (
            SELECT asset_id FROM complaints
            WHERE date_filed >= ?
            GROUP BY asset_id
            HAVING COUNT(*) >= 3
        )
    ''', (six_months_ago,))
    replacement_count = cursor.fetchone()[0]

    # Quick preview of predictions
    conn.close()

    return render_template(
        'index.html',
        total_complaints=total_complaints,
        resolved_complaints=resolved_complaints,
        pending_complaints=pending_complaints,
        replacement_count=replacement_count
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and user['password'] == password:
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['email'] = user['email']
            session['role'] = user['role']
            session['room_no'] = user['room_no']
            session['floor'] = user['floor']

            flash(f"Welcome back, {user['name']}!", 'success')
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('file_complaint'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'student')
        floor = request.form.get('floor')
        room_no = request.form.get('room_no', '').strip()

        if not name or not email or not password:
            flash('Please fill in all required fields.', 'warning')
            return redirect(url_for('register'))

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO users (name, email, password, role, room_no, floor)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, email, password, role, room_no if role == 'student' else None, floor if role == 'student' else None))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception:
            flash('An account with this email already exists.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# ----------------- FEATURE 1: COMPLAINT REGISTRATION & FEATURE 6: DUPLICATE ALERT ----------------- #

@app.route('/complaint/new', methods=['GET', 'POST'])
def file_complaint():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        floor = request.form.get('floor')
        room_no = request.form.get('room_no')
        asset_id = request.form.get('asset_id')
        issue_type = request.form.get('issue_type')
        description = request.form.get('description', '').strip()
        affected_students = request.form.get('affected_students_count', 1)
        is_anonymous = 1 if request.form.get('is_anonymous') == 'on' else 0
        confirmed_duplicate = request.form.get('confirmed_duplicate') == '1'

        try:
            affected_students = max(1, int(affected_students))
        except (ValueError, TypeError):
            affected_students = 1

        if not (floor and room_no and asset_id and issue_type and description):
            flash('Please complete all required fields.', 'warning')
            return redirect(url_for('file_complaint'))

        # Feature 6: Duplicate Complaint Alert
        # Query Complaints table for same asset_id with status != 'Resolved' filed in last 7 days.
        if not confirmed_duplicate:
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                SELECT c.id, c.status, c.issue_type, c.date_filed, c.description, a.asset_code, a.room_no
                FROM complaints c
                JOIN assets a ON c.asset_id = a.id
                WHERE c.asset_id = ? AND c.status != 'Resolved' AND c.date_filed >= ?
                ORDER BY c.date_filed DESC LIMIT 1
            ''', (asset_id, seven_days_ago))
            duplicate = cursor.fetchone()

            if duplicate:
                conn.close()
                # Return page with duplicate warning modal / prompt with Yes/No option
                cursor_fl = get_db().cursor()
                cursor_fl.execute("SELECT DISTINCT floor FROM assets ORDER BY floor ASC")
                floors = [r['floor'] for r in cursor_fl.fetchall()]
                cursor_fl.connection.close()

                return render_template(
                    'file_complaint.html',
                    floors=floors,
                    duplicate_alert=True,
                    duplicate=duplicate,
                    form_data={
                        'floor': floor,
                        'room_no': room_no,
                        'asset_id': asset_id,
                        'issue_type': issue_type,
                        'description': description,
                        'affected_students_count': affected_students,
                        'is_anonymous': is_anonymous
                    }
                )

        # Feature 5: Anonymous Complaint Mode
        # If checked, don't save user_id (set to NULL)
        user_id = None if is_anonymous else session.get('user_id')
        date_filed = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO complaints (
                user_id, asset_id, room_no, floor, issue_type,
                description, date_filed, status, is_anonymous, affected_students_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?)
        ''', (user_id, asset_id, room_no, floor, issue_type, description, date_filed, is_anonymous, affected_students))
        conn.commit()
        complaint_id = cursor.lastrowid
        conn.close()

        # Regenerate charts in background so charts stay up to date
        try:
            generate_charts()
        except Exception:
            pass

        flash(f'Complaint #{complaint_id} registered successfully! Maintenance team has been notified.', 'success')
        return redirect(url_for('index'))

    # Load initial distinct floors
    cursor.execute("SELECT DISTINCT floor FROM assets ORDER BY floor ASC")
    floors = [row['floor'] for row in cursor.fetchall()]
    conn.close()

    return render_template('file_complaint.html', floors=floors)

@app.route('/api/rooms')
def api_rooms():
    floor = request.args.get('floor')
    if not floor:
        return jsonify([])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT room_no FROM assets WHERE floor = ? ORDER BY room_no ASC", (floor,))
    rooms = [row['room_no'] for row in cursor.fetchall()]
    conn.close()
    return jsonify(rooms)

@app.route('/api/assets')
def api_assets():
    room_no = request.args.get('room_no')
    if not room_no:
        return jsonify([])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, asset_type, asset_code FROM assets WHERE room_no = ? ORDER BY asset_type, asset_code ASC", (room_no,))
    assets = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(assets)

@app.route('/api/check_duplicate')
def api_check_duplicate():
    asset_id = request.args.get('asset_id')
    if not asset_id:
        return jsonify({'exists': False})
    
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.id, c.issue_type, c.description, c.date_filed, c.status, c.affected_students_count,
               a.asset_code, a.asset_type, a.room_no, a.floor
        FROM complaints c
        JOIN assets a ON c.asset_id = a.id
        WHERE c.asset_id = ? AND c.status != 'Resolved' AND c.date_filed >= ?
        ORDER BY c.date_filed DESC LIMIT 1
    ''', (asset_id, seven_days_ago))
    row = cursor.fetchone()
    conn.close()

    if row:
        return jsonify({'exists': True, 'complaint': dict(row)})
    return jsonify({'exists': False})

# ----------------- FEATURE 2: ADMIN DASHBOARD & FEATURE 8: IMPACT SCORE ----------------- #

@app.route('/admin')
@admin_required
def admin_dashboard():
    floor = request.args.get('floor', '')
    asset_type = request.args.get('asset_type', '')
    status = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    conn = get_db()
    cursor = conn.cursor()

    query = '''
        SELECT 
            c.id, c.room_no, c.floor, c.issue_type, c.description, c.date_filed, c.status,
            c.is_anonymous, c.affected_students_count,
            a.id AS asset_id, a.asset_code, a.asset_type,
            u.name AS student_name, u.email AS student_email,
            r.resolved_date, r.resolved_by, r.remarks
        FROM complaints c
        JOIN assets a ON c.asset_id = a.id
        LEFT JOIN users u ON c.user_id = u.id
        LEFT JOIN resolution_log r ON c.id = r.complaint_id
        WHERE 1=1
    '''
    params = []

    if floor:
        query += ' AND c.floor = ?'
        params.append(floor)
    if asset_type:
        query += ' AND a.asset_type = ?'
        params.append(asset_type)
    if status:
        query += ' AND c.status = ?'
        params.append(status)
    if start_date:
        query += ' AND c.date_filed >= ?'
        params.append(start_date + ' 00:00:00')
    if end_date:
        query += ' AND c.date_filed <= ?'
        params.append(end_date + ' 23:59:59')

    cursor.execute(query, params)
    raw_complaints = cursor.fetchall()

    # Feature 8: Calculate impact_score = affected_students_count * severity_weight
    # Severity weights: Electrical (Fan, Light, Switchboard) = 3, Plumbing (Geyser, Tap) = 2, Other = 1
    # Feature 5: Hide identity if is_anonymous -> "Anonymous Student, Room {room_no}"
    complaints = []
    for row in raw_complaints:
        item = dict(row)
        score = calculate_impact_score(item['affected_students_count'], item['asset_type'])
        item['impact_score'] = score
        item['severity_weight'] = get_severity_weight(item['asset_type'])

        if item['is_anonymous']:
            item['display_reporter'] = f"Anonymous Student, Room {item['room_no']}"
        elif item['student_name']:
            item['display_reporter'] = f"{item['student_name']} (Room {item['room_no']})"
        else:
            item['display_reporter'] = f"Unregistered Resident, Room {item['room_no']}"

        complaints.append(item)

    # Sort by impact_score descending as DEFAULT VIEW
    complaints.sort(key=lambda x: (x['status'] == 'Resolved', -x['impact_score'], x['date_filed']))

    # Metadata for filter dropdowns
    cursor.execute("SELECT DISTINCT floor FROM assets ORDER BY floor ASC")
    floors = [r['floor'] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT asset_type FROM assets ORDER BY asset_type ASC")
    asset_types = [r['asset_type'] for r in cursor.fetchall()]

    # Stats
    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Pending'")
    pending_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'In Progress'")
    in_progress_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Resolved'")
    resolved_count = cursor.fetchone()[0]

    # Assets with 3+ complaints in last 6 months (Needs Replacement)
    six_months_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        SELECT a.id, a.room_no, a.floor, a.asset_type, a.asset_code, COUNT(c.id) AS recent_complaints
        FROM assets a
        JOIN complaints c ON a.id = c.asset_id
        WHERE c.date_filed >= ?
        GROUP BY a.id, a.room_no, a.floor, a.asset_type, a.asset_code
        HAVING recent_complaints >= 3
        ORDER BY recent_complaints DESC
    ''', (six_months_ago,))
    replacement_candidates = cursor.fetchall()
    replacement_asset_ids = {r['id'] for r in replacement_candidates}

    conn.close()

    # Feature 9: Generate or ensure charts exist in static/charts/
    charts = generate_charts()

    return render_template(
        'admin_dashboard.html',
        complaints=complaints,
        floors=floors,
        asset_types=asset_types,
        selected_floor=floor,
        selected_asset_type=asset_type,
        selected_status=status,
        selected_start_date=start_date,
        selected_end_date=end_date,
        pending_count=pending_count,
        in_progress_count=in_progress_count,
        resolved_count=resolved_count,
        total_count=len(complaints),
        charts=charts,
        replacement_candidates=replacement_candidates,
        replacement_asset_ids=replacement_asset_ids
    )

@app.route('/admin/complaint/<int:complaint_id>/update_status', methods=['POST'])
@admin_required
def update_complaint_status(complaint_id):
    new_status = request.form.get('status')
    remarks = request.form.get('remarks', '').strip()
    resolved_by = request.form.get('resolved_by', '').strip() or session.get('name', 'Admin')

    if new_status not in ['Pending', 'In Progress', 'Resolved']:
        flash('Invalid status supplied.', 'danger')
        return redirect(request.referrer or url_for('admin_dashboard'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE complaints SET status = ? WHERE id = ?", (new_status, complaint_id))

    if new_status == 'Resolved':
        resolved_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("SELECT id FROM resolution_log WHERE complaint_id = ?", (complaint_id,))
        existing_log = cursor.fetchone()
        if existing_log:
            cursor.execute('''
                UPDATE resolution_log 
                SET resolved_date = ?, resolved_by = ?, remarks = ?
                WHERE complaint_id = ?
            ''', (resolved_date, resolved_by, remarks or 'Issue resolved by maintenance staff.', complaint_id))
        else:
            cursor.execute('''
                INSERT INTO resolution_log (complaint_id, resolved_date, resolved_by, remarks)
                VALUES (?, ?, ?, ?)
            ''', (complaint_id, resolved_date, resolved_by, remarks or 'Issue resolved by maintenance staff.'))
        flash(f'Complaint #{complaint_id} marked as Resolved and recorded in Resolution_Log.', 'success')
    else:
        flash(f'Complaint #{complaint_id} status updated to {new_status}.', 'info')

    conn.commit()
    conn.close()

    try:
        generate_charts()
    except Exception:
        pass

    return redirect(request.referrer or url_for('admin_dashboard'))

# ----------------- FEATURE 3: ASSET-WISE COMPLAINT TRACKING & REPLACEMENT ----------------- #

@app.route('/assets')
def assets_list():
    filter_floor = request.args.get('floor', '')
    filter_type = request.args.get('asset_type', '')
    only_replacement = request.args.get('replacement', '') == '1'

    conn = get_db()
    cursor = conn.cursor()

    six_months_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d %H:%M:%S')

    query = '''
        SELECT 
            a.id, a.room_no, a.floor, a.asset_type, a.asset_code,
            COUNT(c.id) AS total_complaints,
            SUM(CASE WHEN c.date_filed >= ? THEN 1 ELSE 0 END) AS recent_complaints,
            SUM(CASE WHEN c.status != 'Resolved' THEN 1 ELSE 0 END) AS active_complaints
        FROM assets a
        LEFT JOIN complaints c ON a.id = c.asset_id
        WHERE 1=1
    '''
    params = [six_months_ago]

    if filter_floor:
        query += ' AND a.floor = ?'
        params.append(filter_floor)
    if filter_type:
        query += ' AND a.asset_type = ?'
        params.append(filter_type)

    query += ' GROUP BY a.id, a.room_no, a.floor, a.asset_type, a.asset_code'

    if only_replacement:
        query += ' HAVING recent_complaints >= 3'

    query += ' ORDER BY recent_complaints DESC, total_complaints DESC, a.floor ASC, a.room_no ASC'

    cursor.execute(query, params)
    assets = cursor.fetchall()

    cursor.execute("SELECT DISTINCT floor FROM assets ORDER BY floor ASC")
    floors = [r['floor'] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT asset_type FROM assets ORDER BY asset_type ASC")
    asset_types = [r['asset_type'] for r in cursor.fetchall()]

    conn.close()

    return render_template(
        'assets.html',
        assets=assets,
        floors=floors,
        asset_types=asset_types,
        selected_floor=filter_floor,
        selected_type=filter_type,
        only_replacement=only_replacement
    )

@app.route('/asset/<int:asset_id>')
def asset_history(asset_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
    asset = cursor.fetchone()
    if not asset:
        flash('Asset not found.', 'danger')
        conn.close()
        return redirect(url_for('index'))

    # Calculate 6 months count
    six_months_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
        SELECT 
            c.*, 
            u.name AS student_name,
            r.resolved_date, r.resolved_by, r.remarks
        FROM complaints c
        LEFT JOIN users u ON c.user_id = u.id
        LEFT JOIN resolution_log r ON c.id = r.complaint_id
        WHERE c.asset_id = ?
        ORDER BY c.date_filed DESC
    ''', (asset_id,))
    raw_history = cursor.fetchall()

    history = []
    recent_complaints_6m = 0
    for r in raw_history:
        item = dict(r)
        if item['date_filed'] >= six_months_ago:
            recent_complaints_6m += 1
        
        if item['is_anonymous']:
            item['display_reporter'] = f"Anonymous Student, Room {item['room_no']}"
        elif item['student_name']:
            item['display_reporter'] = item['student_name']
        else:
            item['display_reporter'] = "Resident"

        history.append(item)

    needs_replacement = recent_complaints_6m >= 3

    conn.close()

    return render_template(
        'asset_history.html',
        asset=asset,
        history=history,
        total_complaints=len(history),
        recent_complaints_6m=recent_complaints_6m,
        needs_replacement=needs_replacement
    )

# ----------------- FEATURE 4: TREND-BASED PREDICTION ----------------- #

@app.route('/predictions')
def predictions_view():
    pred_data = get_trend_predictions()
    return render_template(
        'predictions.html',
        period_labels=pred_data['period_labels'],
        room_predictions=pred_data['room_predictions'],
        floor_predictions=pred_data['floor_predictions']
    )

# ----------------- FEATURE 7: VISUAL HEATMAP ----------------- #

@app.route('/heatmap')
def heatmap():
    floors_data = get_heatmap_data()
    return render_template('heatmap.html', floors_data=floors_data)

@app.route('/my_complaints')
@login_required
def my_complaints():
    user_id = session.get('user_id')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.*, a.asset_code, a.asset_type, r.resolved_date, r.resolved_by, r.remarks
        FROM complaints c
        JOIN assets a ON c.asset_id = a.id
        LEFT JOIN resolution_log r ON c.id = r.complaint_id
        WHERE c.user_id = ?
        ORDER BY c.date_filed DESC
    ''', (user_id,))
    complaints = cursor.fetchall()
    conn.close()
    return render_template('my_complaints.html', complaints=complaints)

# Aliases for template compatibility
app.add_url_rule('/asset/<int:asset_id>', endpoint='asset_detail', view_func=asset_history)

# ----------------- SEMINAR PRESENTATION & DEMO RESET ----------------- #

@app.route('/presentation')
def presentation():
    return render_template('presentation.html')

@app.route('/resolutions')
def resolutions_view():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            r.id AS log_id, r.resolved_date, r.resolved_by, r.remarks,
            c.id AS complaint_id, c.asset_id, c.room_no, c.floor, c.issue_type, c.description, c.date_filed,
            a.asset_code, a.asset_type
        FROM resolution_log r
        JOIN complaints c ON r.complaint_id = c.id
        JOIN assets a ON c.asset_id = a.id
        ORDER BY r.resolved_date DESC
    ''')
    logs = cursor.fetchall()
    conn.close()
    return render_template('resolution_logs.html', logs=logs)

@app.route('/api/reset_demo_data', methods=['GET', 'POST'])
def reset_demo_data():
    from models import force_reseed
    force_reseed()
    try:
        generate_charts()
    except Exception:
        pass
    flash('✓ Database successfully restored to pristine Seminar Demo State (Room 204 trend & Fan-1 replacement ready)!', 'success')
    return redirect(request.referrer or url_for('presentation'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

import sqlite3
import os
from datetime import datetime, timedelta
import random

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hostel_maintenance.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student', 'admin')),
        room_no TEXT,
        floor INTEGER
    )
    ''')

    # Assets Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_no TEXT NOT NULL,
        floor INTEGER NOT NULL,
        asset_type TEXT NOT NULL CHECK(asset_type IN ('Fan', 'Light', 'Geyser', 'Tap', 'Switchboard', 'Other')),
        asset_code TEXT NOT NULL
    )
    ''')

    # Complaints Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        asset_id INTEGER NOT NULL,
        room_no TEXT NOT NULL,
        floor INTEGER NOT NULL,
        issue_type TEXT NOT NULL CHECK(issue_type IN ('Not working', 'Damaged', 'Making noise', 'Other')),
        description TEXT NOT NULL,
        date_filed TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Pending', 'In Progress', 'Resolved')) DEFAULT 'Pending',
        is_anonymous INTEGER NOT NULL DEFAULT 0,
        affected_students_count INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (asset_id) REFERENCES assets (id)
    )
    ''')

    # Resolution_Log Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS resolution_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id INTEGER NOT NULL,
        resolved_date TEXT NOT NULL,
        resolved_by TEXT NOT NULL,
        remarks TEXT NOT NULL,
        FOREIGN KEY (complaint_id) REFERENCES complaints (id)
    )
    ''')

    conn.commit()
    conn.close()

def seed_sample_data():
    conn = get_db()
    cursor = conn.cursor()

    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    print("Seeding initial hostel management database...")

    # Default Users (Admin & Students)
    users = [
        ('Hostel Warden', 'admin@hostel.edu', 'admin123', 'admin', None, None),
        ('Maintenance Incharge', 'supervisor@hostel.edu', 'admin123', 'admin', None, None),
        ('Rahul Sharma', 'rahul@hostel.edu', 'student123', 'student', '101', 1),
        ('Priya Patel', 'priya@hostel.edu', 'student123', 'student', '202', 2),
        ('Amit Verma', 'amit@hostel.edu', 'student123', 'student', '204', 2),
        ('Sneha Kulkarni', 'sneha@hostel.edu', 'student123', 'student', '303', 3),
        ('Rohan Das', 'rohan@hostel.edu', 'student123', 'student', '401', 4)
    ]
    cursor.executemany('''
    INSERT INTO users (name, email, password, role, room_no, floor)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', users)

    # Generate standard hostel assets across 4 floors, 4 rooms per floor
    floors = [1, 2, 3, 4]
    rooms_per_floor = 4
    asset_templates = [
        ('Fan', 'Fan-1'),
        ('Fan', 'Fan-2'),
        ('Light', 'Light-1'),
        ('Light', 'Light-2'),
        ('Geyser', 'Geyser-1'),
        ('Tap', 'Tap-1'),
        ('Switchboard', 'Switchboard-1')
    ]

    assets_to_insert = []
    for fl in floors:
        for r_idx in range(1, rooms_per_floor + 1):
            room_no = f"{fl}0{r_idx}"
            for atype, acode in asset_templates:
                assets_to_insert.append((room_no, fl, atype, acode))

    cursor.executemany('''
    INSERT INTO assets (room_no, floor, asset_type, asset_code)
    VALUES (?, ?, ?, ?)
    ''', assets_to_insert)

    # Fetch inserted assets
    cursor.execute("SELECT id, room_no, floor, asset_type, asset_code FROM assets")
    all_assets = cursor.fetchall()
    asset_dict = {(a['room_no'], a['asset_code']): a['id'] for a in all_assets}

    # Generate realistic historical complaints over the past 120 days
    # Ensure specific assets have 3+ complaints to trigger the "Needs Replacement" flag
    # e.g., Fan-1 in Room 204 (explicitly mentioned in requirement!)
    # and Geyser-1 in Room 303, Tap-1 in Room 102
    now = datetime.now()

    sample_complaints = [
        # Fan-1 in Room 204: 4 complaints (Needs Replacement!)
        {
            'room_no': '204', 'floor': 2, 'asset_code': 'Fan-1', 'issue_type': 'Making noise',
            'desc': 'Fan makes high pitched squeaking noise at speed 3 and above.',
            'days_ago': 105, 'status': 'Resolved', 'is_anon': 0, 'affected': 3,
            'resolved_by': 'Technician Ramesh', 'remarks': 'Applied bearing lubricant.'
        },
        {
            'room_no': '204', 'floor': 2, 'asset_code': 'Fan-1', 'issue_type': 'Not working',
            'desc': 'Fan stopped spinning completely after voltage fluctuation.',
            'days_ago': 68, 'status': 'Resolved', 'is_anon': 0, 'affected': 3,
            'resolved_by': 'Electrician Suresh', 'remarks': 'Replaced capacitor and wiring.'
        },
        {
            'room_no': '204', 'floor': 2, 'asset_code': 'Fan-1', 'issue_type': 'Making noise',
            'desc': 'Heavy vibrations and wobbling sound returned; motor smells hot.',
            'days_ago': 25, 'status': 'Resolved', 'is_anon': 0, 'affected': 3,
            'resolved_by': 'Technician Ramesh', 'remarks': 'Blades aligned, motor re-seated.'
        },
        {
            'room_no': '204', 'floor': 2, 'asset_code': 'Fan-1', 'issue_type': 'Not working',
            'desc': 'Motor completely jammed and smoking slightly. Unusable.',
            'days_ago': 3, 'status': 'In Progress', 'is_anon': 0, 'affected': 4,
            'resolved_by': None, 'remarks': None
        },

        # Geyser-1 in Room 303: 3 complaints (Needs Replacement!)
        {
            'room_no': '303', 'floor': 3, 'asset_code': 'Geyser-1', 'issue_type': 'Not working',
            'desc': 'No hot water even after 45 minutes.',
            'days_ago': 90, 'status': 'Resolved', 'is_anon': 0, 'affected': 3,
            'resolved_by': 'Plumber Dinesh', 'remarks': 'Thermostat reset and cleaned coil.'
        },
        {
            'room_no': '303', 'floor': 3, 'asset_code': 'Geyser-1', 'issue_type': 'Damaged',
            'desc': 'Water leaking from base of the geyser tank.',
            'days_ago': 45, 'status': 'Resolved', 'is_anon': 0, 'affected': 3,
            'resolved_by': 'Plumber Dinesh', 'remarks': 'Patched pipe inlet washer.'
        },
        {
            'room_no': '303', 'floor': 3, 'asset_code': 'Geyser-1', 'issue_type': 'Making noise',
            'desc': 'Loud boiling popping noise and tripping circuit breaker.',
            'days_ago': 2, 'status': 'Pending', 'is_anon': 1, 'affected': 3,
            'resolved_by': None, 'remarks': None
        },

        # Tap-1 in Room 102: 3 complaints (Needs Replacement!)
        {
            'room_no': '102', 'floor': 1, 'asset_code': 'Tap-1', 'issue_type': 'Damaged',
            'desc': 'Tap handle cracked and leaking continuously.',
            'days_ago': 80, 'status': 'Resolved', 'is_anon': 0, 'affected': 2,
            'resolved_by': 'Plumber Dinesh', 'remarks': 'Handle replaced.'
        },
        {
            'room_no': '102', 'floor': 1, 'asset_code': 'Tap-1', 'issue_type': 'Not working',
            'desc': 'Water pressure minimal, spindle stuck shut.',
            'days_ago': 40, 'status': 'Resolved', 'is_anon': 0, 'affected': 2,
            'resolved_by': 'Plumber Dinesh', 'remarks': 'Descaled tap spindle.'
        },
        {
            'room_no': '102', 'floor': 1, 'asset_code': 'Tap-1', 'issue_type': 'Damaged',
            'desc': 'Thread stripped, tap detached from washbasin wall mount.',
            'days_ago': 4, 'status': 'Pending', 'is_anon': 0, 'affected': 2,
            'resolved_by': None, 'remarks': None
        },

        # Various other complaints across different floors and assets
        {
            'room_no': '101', 'floor': 1, 'asset_code': 'Light-1', 'issue_type': 'Not working',
            'desc': 'Tube light flickering violently and turning off after 2 minutes.',
            'days_ago': 15, 'status': 'Resolved', 'is_anon': 0, 'affected': 2,
            'resolved_by': 'Electrician Suresh', 'remarks': 'Replaced tube with new 20W LED rod.'
        },
        {
            'room_no': '101', 'floor': 1, 'asset_code': 'Switchboard-1', 'issue_type': 'Damaged',
            'desc': 'Socket 2 loose, sparks when laptop plug is inserted.',
            'days_ago': 6, 'status': 'In Progress', 'is_anon': 0, 'affected': 2,
            'resolved_by': None, 'remarks': None
        },
        {
            'room_no': '201', 'floor': 2, 'asset_code': 'Geyser-1', 'issue_type': 'Not working',
            'desc': 'Water heating element not turning on.',
            'days_ago': 30, 'status': 'Resolved', 'is_anon': 0, 'affected': 3,
            'resolved_by': 'Plumber Dinesh', 'remarks': 'Heating coil terminal re-soldered.'
        },
        {
            'room_no': '202', 'floor': 2, 'asset_code': 'Light-2', 'issue_type': 'Not working',
            'desc': 'Study lamp switch not responding.',
            'days_ago': 50, 'status': 'Resolved', 'is_anon': 0, 'affected': 2,
            'resolved_by': 'Electrician Suresh', 'remarks': 'Switch contact cleaned.'
        },
        {
            'room_no': '202', 'floor': 2, 'asset_code': 'Tap-1', 'issue_type': 'Damaged',
            'desc': 'Continuous drip waste in washroom.',
            'days_ago': 1, 'status': 'Pending', 'is_anon': 1, 'affected': 2,
            'resolved_by': None, 'remarks': None
        },
        {
            'room_no': '301', 'floor': 3, 'asset_code': 'Fan-2', 'issue_type': 'Not working',
            'desc': 'Fan does not rotate even when switch is toggled.',
            'days_ago': 20, 'status': 'Resolved', 'is_anon': 0, 'affected': 2,
            'resolved_by': 'Electrician Suresh', 'remarks': 'Regulator wire was loose.'
        },
        {
            'room_no': '302', 'floor': 3, 'asset_code': 'Geyser-1', 'issue_type': 'Not working',
            'desc': 'Geyser power light is red but water does not warm up.',
            'days_ago': 12, 'status': 'In Progress', 'is_anon': 0, 'affected': 3,
            'resolved_by': None, 'remarks': None
        },
        {
            'room_no': '304', 'floor': 3, 'asset_code': 'Switchboard-1', 'issue_type': 'Damaged',
            'desc': 'Broken switch faceplate exposing internal wires.',
            'days_ago': 5, 'status': 'Pending', 'is_anon': 0, 'affected': 3,
            'resolved_by': None, 'remarks': None
        },
        {
            'room_no': '401', 'floor': 4, 'asset_code': 'Fan-1', 'issue_type': 'Making noise',
            'desc': 'Clicking noise from ceiling mount.',
            'days_ago': 60, 'status': 'Resolved', 'is_anon': 0, 'affected': 2,
            'resolved_by': 'Technician Ramesh', 'remarks': 'Tightened safety bolt and downrod.'
        },
        {
            'room_no': '402', 'floor': 4, 'asset_code': 'Light-1', 'issue_type': 'Not working',
            'desc': 'Main ceiling light dead.',
            'days_ago': 18, 'status': 'Resolved', 'is_anon': 0, 'affected': 3,
            'resolved_by': 'Electrician Suresh', 'remarks': 'Replaced burnt out driver.'
        },
        {
            'room_no': '403', 'floor': 4, 'asset_code': 'Tap-1', 'issue_type': 'Not working',
            'desc': 'No water coming out from tap, clogged aerator.',
            'days_ago': 7, 'status': 'Resolved', 'is_anon': 0, 'affected': 2,
            'resolved_by': 'Plumber Dinesh', 'remarks': 'Cleaned sediment mesh.'
        },
        {
            'room_no': '404', 'floor': 4, 'asset_code': 'Geyser-1', 'issue_type': 'Damaged',
            'desc': 'Corrosion on inlet valve and water dripping onto floor.',
            'days_ago': 2, 'status': 'Pending', 'is_anon': 0, 'affected': 3,
            'resolved_by': None, 'remarks': None
        }
    ]

    for item in sample_complaints:
        asset_id = asset_dict.get((item['room_no'], item['asset_code']))
        if not asset_id:
            continue
        date_filed = (now - timedelta(days=item['days_ago'])).strftime('%Y-%m-%d %H:%M:%S')
        user_id = 3 if not item['is_anon'] else None  # Assign to student or null

        cursor.execute('''
        INSERT INTO complaints (
            user_id, asset_id, room_no, floor, issue_type, description,
            date_filed, status, is_anonymous, affected_students_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, asset_id, item['room_no'], item['floor'], item['issue_type'],
            item['desc'], date_filed, item['status'], item['is_anon'], item['affected']
        ))
        complaint_id = cursor.lastrowid

        if item['status'] == 'Resolved':
            resolved_date = (now - timedelta(days=item['days_ago'] - 1)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            INSERT INTO resolution_log (complaint_id, resolved_date, resolved_by, remarks)
            VALUES (?, ?, ?, ?)
            ''', (complaint_id, resolved_date, item['resolved_by'], item['remarks']))

    conn.commit()
    conn.close()
    print("Database seeded successfully!")

if __name__ == '__main__':
    init_db()
    seed_sample_data()

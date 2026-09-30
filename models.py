import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users Table
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

    # 2. Assets Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_no TEXT NOT NULL,
        floor INTEGER NOT NULL,
        asset_type TEXT NOT NULL CHECK(asset_type IN ('Fan', 'Light', 'Geyser', 'Tap', 'Switchboard', 'Other')),
        asset_code TEXT NOT NULL
    )
    ''')

    # 3. Complaints Table
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

    # 4. Resolution_Log Table
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

def force_reseed():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS resolution_log")
    cursor.execute("DROP TABLE IF EXISTS complaints")
    cursor.execute("DROP TABLE IF EXISTS assets")
    cursor.execute("DROP TABLE IF EXISTS users")
    conn.commit()
    conn.close()
    init_db()
    seed_db()

def seed_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    print("Populating database with initial hostel data...")

    # Users
    users = [
        ('Hostel Warden', 'admin@hostel.edu', 'admin123', 'admin', None, None),
        ('Supervisor Sharma', 'supervisor@hostel.edu', 'admin123', 'admin', None, None),
        ('Rahul Verma', 'rahul@hostel.edu', 'student123', 'student', '101', 1),
        ('Priya Nair', 'priya@hostel.edu', 'student123', 'student', '204', 2),
        ('Amit Patel', 'amit@hostel.edu', 'student123', 'student', '302', 3),
        ('Sneha Roy', 'sneha@hostel.edu', 'student123', 'student', '403', 4)
    ]
    cursor.executemany('''
    INSERT INTO users (name, email, password, role, room_no, floor)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', users)

    # Assets across 4 floors, 4 rooms per floor (101-104, 201-204, 301-304, 401-404)
    asset_types_and_codes = [
        ('Fan', 'Fan-1'),
        ('Fan', 'Fan-2'),
        ('Light', 'Light-1'),
        ('Light', 'Light-2'),
        ('Geyser', 'Geyser-1'),
        ('Tap', 'Tap-1'),
        ('Switchboard', 'Switchboard-1')
    ]

    assets_data = []
    for fl in [1, 2, 3, 4]:
        for r in [1, 2, 3, 4]:
            room_no = f"{fl}0{r}"
            for atype, acode in asset_types_and_codes:
                assets_data.append((room_no, fl, atype, acode))

    cursor.executemany('''
    INSERT INTO assets (room_no, floor, asset_type, asset_code)
    VALUES (?, ?, ?, ?)
    ''', assets_data)

    # Map assets
    cursor.execute("SELECT id, room_no, asset_code FROM assets")
    asset_map = {(row['room_no'], row['asset_code']): row['id'] for row in cursor.fetchall()}

    now = datetime.now()

    # Generate historical complaints to establish:
    # 1. Room 204: 2 -> 3 -> 5 complaints trend over last 3 months (so projected next month is 6-7)
    # 2. Fan-1 in Room 204 has 3+ complaints in last 6 months (Flagged as "Needs Replacement")
    # 3. Heatmap colors:
    #    - Room 204: 5 complaints in last 30 days -> RED (4+)
    #    - Room 302: 3 complaints in last 30 days -> YELLOW (2-3)
    #    - Room 101: 1 complaint in last 30 days -> GREEN (0-1)
    #    - Other rooms: 0-1 complaints -> GREEN
    # 4. Anonymous complaints with is_anonymous = 1 and user_id = None
    # 5. Active tickets filed within last 3 days for duplicate alerts

    complaints_to_insert = [
        # Room 204 - Month -3 (approx 75-85 days ago): 2 complaints
        {
            'room': '204', 'floor': 2, 'code': 'Fan-1', 'issue': 'Making noise',
            'desc': 'Fan motor rattling loudly at speed 3.', 'days': 85,
            'status': 'Resolved', 'anon': 0, 'affected': 2,
            'resolved_by': 'Technician Ramesh', 'remarks': 'Lubricated bearings and tightened downrod.'
        },
        {
            'room': '204', 'floor': 2, 'code': 'Light-1', 'issue': 'Not working',
            'desc': 'Tube light blinking continuously.', 'days': 78,
            'status': 'Resolved', 'anon': 0, 'affected': 2,
            'resolved_by': 'Electrician Suresh', 'remarks': 'Replaced choke and starter.'
        },

        # Room 204 - Month -2 (approx 45-55 days ago): 3 complaints
        {
            'room': '204', 'floor': 2, 'code': 'Fan-1', 'issue': 'Not working',
            'desc': 'Fan stopped spinning completely.', 'days': 52,
            'status': 'Resolved', 'anon': 0, 'affected': 3,
            'resolved_by': 'Technician Ramesh', 'remarks': 'Replaced burnt capacitor.'
        },
        {
            'room': '204', 'floor': 2, 'code': 'Tap-1', 'issue': 'Damaged',
            'desc': 'Washbasin tap handle loose and leaking.', 'days': 48,
            'status': 'Resolved', 'anon': 1, 'affected': 2,
            'resolved_by': 'Plumber Dinesh', 'remarks': 'Replaced washer and washer spindle.'
        },
        {
            'room': '204', 'floor': 2, 'code': 'Switchboard-1', 'issue': 'Damaged',
            'desc': 'Socket 1 loose, plug slips out.', 'days': 42,
            'status': 'Resolved', 'anon': 0, 'affected': 2,
            'resolved_by': 'Electrician Suresh', 'remarks': 'Fixed loose socket clips.'
        },

        # Room 204 - Month -1 / Last 30 days: 5 complaints (Red on Heatmap!)
        {
            'room': '204', 'floor': 2, 'code': 'Fan-1', 'issue': 'Making noise',
            'desc': 'Fan wobbling violently and screeching noise returned.', 'days': 20,
            'status': 'Resolved', 'anon': 0, 'affected': 3,
            'resolved_by': 'Technician Ramesh', 'remarks': 'Blades aligned, re-balanced.'
        },
        {
            'room': '204', 'floor': 2, 'code': 'Fan-1', 'issue': 'Not working',
            'desc': 'Fan-1 burned smell and stopped working again. 4th time failing!', 'days': 3,
            'status': 'In Progress', 'anon': 0, 'affected': 4,
            'resolved_by': None, 'remarks': None
        },
        {
            'room': '204', 'floor': 2, 'code': 'Geyser-1', 'issue': 'Not working',
            'desc': 'Water not heating at all.', 'days': 15,
            'status': 'Resolved', 'anon': 0, 'affected': 3,
            'resolved_by': 'Plumber Dinesh', 'remarks': 'Reset safety thermostat switch.'
        },
        {
            'room': '204', 'floor': 2, 'code': 'Light-2', 'issue': 'Not working',
            'desc': 'Balcony light fixture dead.', 'days': 10,
            'status': 'Pending', 'anon': 1, 'affected': 2,
            'resolved_by': None, 'remarks': None
        },
        {
            'room': '204', 'floor': 2, 'code': 'Switchboard-1', 'issue': 'Making noise',
            'desc': 'Sparks and buzzing sound when turning on main switch.', 'days': 2,
            'status': 'Pending', 'anon': 0, 'affected': 4,
            'resolved_by': None, 'remarks': None
        },

        # Room 302: Yellow on Heatmap (2-3 in last 30 days)
        {
            'room': '302', 'floor': 3, 'code': 'Geyser-1', 'issue': 'Damaged',
            'desc': 'Water dripping from bottom pipe connection.', 'days': 18,
            'status': 'Resolved', 'anon': 0, 'affected': 3,
            'resolved_by': 'Plumber Dinesh', 'remarks': 'Applied thread seal tape and tightened nut.'
        },
        {
            'room': '302', 'floor': 3, 'code': 'Fan-1', 'issue': 'Making noise',
            'desc': 'Fan regulator clicks and runs only at full speed.', 'days': 8,
            'status': 'In Progress', 'anon': 0, 'affected': 2,
            'resolved_by': None, 'remarks': None
        },
        {
            'room': '302', 'floor': 3, 'code': 'Tap-1', 'issue': 'Not working',
            'desc': 'Very low water pressure in washroom tap.', 'days': 4,
            'status': 'Pending', 'anon': 1, 'affected': 3,
            'resolved_by': None, 'remarks': None
        },

        # Room 101: Green (1 complaint in last 30 days)
        {
            'room': '101', 'floor': 1, 'code': 'Light-1', 'issue': 'Not working',
            'desc': 'Tube light bulb fused.', 'days': 12,
            'status': 'Resolved', 'anon': 0, 'affected': 2,
            'resolved_by': 'Electrician Suresh', 'remarks': 'Replaced with 20W LED rod.'
        },

        # Room 102:
        {
            'room': '102', 'floor': 1, 'code': 'Tap-1', 'issue': 'Damaged',
            'desc': 'Continuous water drip waste.', 'days': 75,
            'status': 'Resolved', 'anon': 0, 'affected': 2,
            'resolved_by': 'Plumber Dinesh', 'remarks': 'Replaced washer.'
        },
        {
            'room': '102', 'floor': 1, 'code': 'Tap-1', 'issue': 'Not working',
            'desc': 'Tap spindle stuck.', 'days': 40,
            'status': 'Resolved', 'anon': 0, 'affected': 2,
            'resolved_by': 'Plumber Dinesh', 'remarks': 'Descaled spindle.'
        },
        {
            'room': '102', 'floor': 1, 'code': 'Tap-1', 'issue': 'Damaged',
            'desc': 'Tap handle broken off completely.', 'days': 5,
            'status': 'In Progress', 'anon': 0, 'affected': 2,
            'resolved_by': None, 'remarks': None
        },

        # Room 403:
        {
            'room': '403', 'floor': 4, 'code': 'Geyser-1', 'issue': 'Not working',
            'desc': 'Geyser trips MCB after 5 minutes of heating.', 'days': 25,
            'status': 'Resolved', 'anon': 0, 'affected': 3,
            'resolved_by': 'Electrician Suresh', 'remarks': 'Replaced heating element and thermostat.'
        },
        {
            'room': '403', 'floor': 4, 'code': 'Fan-2', 'issue': 'Making noise',
            'desc': 'High humming sound.', 'days': 1,
            'status': 'Pending', 'anon': 1, 'affected': 2,
            'resolved_by': None, 'remarks': None
        }
    ]

    for item in complaints_to_insert:
        asset_id = asset_map.get((item['room'], item['code']))
        if not asset_id:
            continue
        date_filed = (now - timedelta(days=item['days'])).strftime('%Y-%m-%d %H:%M:%S')
        user_id = None if item['anon'] else 3

        cursor.execute('''
        INSERT INTO complaints (
            user_id, asset_id, room_no, floor, issue_type,
            description, date_filed, status, is_anonymous, affected_students_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, asset_id, item['room'], item['floor'], item['issue'],
            item['desc'], date_filed, item['status'], item['anon'], item['affected']
        ))
        complaint_id = cursor.lastrowid

        if item['status'] == 'Resolved':
            resolved_date = (now - timedelta(days=max(0, item['days'] - 1))).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            INSERT INTO resolution_log (complaint_id, resolved_date, resolved_by, remarks)
            VALUES (?, ?, ?, ?)
            ''', (complaint_id, resolved_date, item['resolved_by'], item['remarks']))

    conn.commit()
    conn.close()
    print("Database initialization and seeding complete!")

if __name__ == '__main__':
    init_db()
    seed_db()

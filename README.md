# 🏢 Hostel Maintenance Predictor

A Flask-based web application for tracking and predicting hostel maintenance issues (fans, lights, geysers, taps, switchboards). Harnesses **SQLite** for relational tracking, **Pandas** for statistical failure aggregation, and **Matplotlib** for trend chart generation, wrapped in a responsive **HTML/CSS + Jinja2** interface.

---

## 🌟 Key Features

### 1. Complaint Registration with Smart Filtering
- **Dynamic Cascading Selectors**: Selecting **Floor** dynamically loads available **Rooms**, and selecting a **Room** instantly loads only the assets registered in that room (`Fan-1`, `Fan-2`, `Light-1`, `Geyser-1`, etc.).
- **Anonymous Mode Toggle**: Students can choose to file anonymously or attach their student profile.
- **Affected Students Count**: Quantifies user impact score to prioritize high-urgency repairs.

### 2. Real-Time Duplicate Complaint Detection & Impact Upvoting (Feature 6)
- Whenever an asset is selected, the system queries the active ticket backlog.
- If an unresolved issue already exists for that asset, a warning banner appears detailing the open ticket.
- **Anti-Clutter Upvote**: Instead of spamming duplicate tickets, students can click **"Upvote Impact (+1 Affected Student)"**, which dynamically increments the existing ticket's impact score in real-time, escalating its priority on the admin dashboard.

### 3. Admin Maintenance Operations Dashboard
- Multi-criteria filtering: **Floor**, **Asset Type**, **Ticket Status** (Pending / In Progress / Resolved), **Date Range**, and keyword search.
- **Interactive Status Transition**:
  - `Pending` &rarr; `In Progress` &rarr; `Resolved`.
  - When marking a complaint as `Resolved`, an interactive modal prompts for **Resolution Remarks** and **Serviced By (Technician Name)**, writing permanently to the `Resolution_Log` audit trail.

### 4. Asset-Wise Complaint Tracking & "Needs Replacement" Flag
- View health metrics for every individual hostel asset.
- Tracks both **Lifetime Complaints** and **Complaints in the last 6 months**.
- **Automated Replacement Flag**: Any asset recording **3 or more complaints within 6 months** (e.g. *Fan-1 in Room 204*) is highlighted with a pulsing **"🚨 Needs Replacement"** badge to prevent wasteful ongoing patchwork repairs.

### 5. Trend-Based Failure Prediction & Visual Analytics
- **Pandas Grouping**: Analyzes failure frequency across asset classes, floor-wise vulnerability scores, and mean time between failures (MTBF).
- **High-DPI Headless Matplotlib Charts** (embedded via Base64):
  1. *Complaints Distribution by Asset Type*
  2. *Floor-wise Status Breakdown (Active vs Resolved)*
  3. *Monthly Complaint Trajectory Line Graph*
  4. *Overall Resolution Ratio Donut Chart*
  5. *Reported Problem Categories (Damaged, Noise, Outages)*
- **Predictive Maintenance Insights**: Algorithmic warnings highlighting high-risk floors, replacement candidate appliances, and spare inventory recommendations.

---

## 🗄️ Database Schema (SQLite)

The system automatically creates and seeds `hostel_maintenance.db`:

- **`users`**: `id` (PK), `name`, `email` (UNIQUE), `password`, `role` (`student`/`admin`), `room_no`, `floor`
- **`assets`**: `id` (PK), `room_no`, `floor`, `asset_type` (`Fan`/`Light`/`Geyser`/`Tap`/`Switchboard`/`Other`), `asset_code` (e.g. `Fan-1`, `Geyser-1`)
- **`complaints`**: `id` (PK), `user_id` (FK nullable), `asset_id` (FK), `room_no`, `floor`, `issue_type` (`Not working`/`Damaged`/`Making noise`/`Other`), `description`, `date_filed`, `status` (`Pending`/`In Progress`/`Resolved`), `is_anonymous` (0/1), `affected_students_count` (int)
- **`resolution_log`**: `id` (PK), `complaint_id` (FK), `resolved_date`, `resolved_by`, `remarks`

---

## 🔑 Pre-Configured Demo Accounts

| Role | Email | Password | Details |
|---|---|---|---|
| **Admin / Warden** | `admin@hostel.edu` | `admin123` | Full dashboard, status triage, predictions, replacement logs |
| **Student** | `rahul@hostel.edu` | `student123` | Room 101 resident, complaint filing, tracking personal tickets |
| **Anonymous** | *No login needed* | - | Toggle anonymous mode on the filing form |

---

## 🚀 How to Run

1. **Install Dependencies** (if needed):
   ```bash
   py -m pip install -r requirements.txt
   ```

2. **Initialize Database and Seed Realistic History**:
   ```bash
   py database.py
   ```
   *(Pre-populates 4 floors, 16 rooms, 112 assets, and 20+ realistic historical complaints including Fan-1 in Room 204 with 3+ complaints).*

3. **Start the Flask Application**:
   ```bash
   py app.py
   ```

4. **Open in Browser**:
   Navigate to:
   ```
   http://127.0.0.1:5000/
   ```

5. **Run Test Suite**:
   ```bash
   py test_app.py
   ```

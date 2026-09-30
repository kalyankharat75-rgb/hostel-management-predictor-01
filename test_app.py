import unittest
import os
from app import app
from models import get_db
from analysis import calculate_impact_score, get_trend_predictions, get_heatmap_data

class TestHostelMaintenanceApp(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True

    def test_01_homepage_and_charts(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Hostel Maintenance Predictor', res.data)
        self.assertTrue(os.path.exists('static/charts/floor_bar.png'))
        self.assertTrue(os.path.exists('static/charts/asset_pie.png'))

    def test_02_complaint_registration_and_cascade_api(self):
        # API rooms for Floor 2
        res = self.client.get('/api/rooms?floor=2')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'204', res.data)

        # API assets for Room 204
        res = self.client.get('/api/assets?room_no=204')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Fan-1', res.data)

        # File a new complaint
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM assets WHERE room_no = '101' AND asset_code = 'Light-2'")
        asset_id = cursor.fetchone()[0]
        conn.close()

        res = self.client.post('/complaint/new', data={
            'floor': '1',
            'room_no': '101',
            'asset_id': asset_id,
            'issue_type': 'Not working',
            'description': 'Tube light bulb fused.',
            'affected_students_count': '2',
            'is_anonymous': 'on',
            'confirmed_duplicate': '1'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'registered successfully', res.data)

    def test_03_duplicate_check_and_alert(self):
        # Query active asset Fan-1 in 204 (which has an open in-progress ticket)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM assets WHERE room_no = '204' AND asset_code = 'Fan-1'")
        asset_id = cursor.fetchone()[0]
        conn.close()

        # Check API
        res = self.client.get(f'/api/check_duplicate?asset_id={asset_id}')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['exists'])

        # Server-side submit without confirmed_duplicate triggers duplicate warning prompt
        res = self.client.post('/complaint/new', data={
            'floor': '2',
            'room_no': '204',
            'asset_id': asset_id,
            'issue_type': 'Not working',
            'description': 'Fan stopped again.',
            'affected_students_count': '3',
            'is_anonymous': 'on'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'This issue is already reported', res.data)
        self.assertIn(b'Do you still want to file a new one?', res.data)

    def test_04_anonymous_mode_identity_masking(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'
            sess['name'] = 'Hostel Warden'

        res = self.client.get('/admin')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Anonymous Student, Room', res.data)

    def test_05_admin_dashboard_status_update_and_resolution_log(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'
            sess['name'] = 'Hostel Warden'

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM complaints WHERE status = 'Pending' LIMIT 1")
        row = cursor.fetchone()
        complaint_id = row[0]
        conn.close()

        # Update to Resolved with remarks
        res = self.client.post(f'/admin/complaint/{complaint_id}/update_status', data={
            'status': 'Resolved',
            'resolved_by': 'Technician Ramesh',
            'remarks': 'Replaced broken switch contact.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify Resolution_Log contains entry
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM resolution_log WHERE complaint_id = ?", (complaint_id,))
        log = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(log)
        self.assertEqual(log['resolved_by'], 'Technician Ramesh')

    def test_06_asset_history_and_replacement_flag(self):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM assets WHERE room_no = '204' AND asset_code = 'Fan-1'")
        asset_id = cursor.fetchone()[0]
        conn.close()

        res = self.client.get(f'/asset/{asset_id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Needs Replacement', res.data)
        self.assertIn(b'Fan-1 in Room 204 has had', res.data)

    def test_07_impact_score_calculation(self):
        # Electrical = 3, Plumbing = 2, Other = 1
        self.assertEqual(calculate_impact_score(3, 'Fan'), 9)
        self.assertEqual(calculate_impact_score(2, 'Tap'), 4)
        self.assertEqual(calculate_impact_score(1, 'Other'), 1)

    def test_08_predictions_and_moving_average(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'
            sess['name'] = 'Hostel Warden'

        res = self.client.get('/predictions')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Room-Level 3-Month Moving Average', res.data)
        self.assertIn(b'Room 204', res.data)

        pred_data = get_trend_predictions()
        room_204_pred = next(p for p in pred_data['room_predictions'] if p['room_no'] == '204')
        self.assertTrue(room_204_pred['moving_avg'] > 2)

    def test_09_heatmap_view(self):
        res = self.client.get('/heatmap')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Hostel Infrastructure Heatmap', res.data)
        self.assertIn(b'Green: Normal', res.data)
        self.assertIn(b'Yellow: Elevated', res.data)
        self.assertIn(b'Red: Critical Hotspot', res.data)

        # Verify Room 204 is red (4+ complaints in last 30 days)
        floors_data = get_heatmap_data()
        room_204 = next(r for r in floors_data[2] if r['room_no'] == '204')
        self.assertEqual(room_204['color'], 'red')

if __name__ == '__main__':
    unittest.main()

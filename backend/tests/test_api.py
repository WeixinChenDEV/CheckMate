"""Offline API regressions: isolated SQLite data and mocked external services."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Do not load real credentials or connect to a user's configured database.
with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:", "JWT_SECRET_KEY": "test-only-secret-at-least-32-characters"}), patch("dotenv.load_dotenv"):
    import app as backend


class ApiTests(unittest.TestCase):
    def setUp(self):
        backend.app.config["TESTING"] = True
        self.client = backend.app.test_client()
        self.secret = patch.dict(os.environ, {"JWT_SECRET_KEY": "test-only-secret-at-least-32-characters"})
        self.secret.start()
        with backend.app.app_context():
            backend.db.drop_all()
            backend.db.create_all()
        result = self.client.post('/api/auth/register', json={"username": "owner", "password": "testpass123"})
        self.assertEqual(result.status_code, 201)
        self.headers = {"Authorization": f"Bearer {result.get_json()['token']}"}

    def tearDown(self):
        with backend.app.app_context():
            backend.db.session.remove()
            backend.db.drop_all()
        self.secret.stop()

    def test_auth_required(self):
        self.assertEqual(self.client.get('/api/scenarios').status_code, 401)

    def test_assistant_without_key_returns_rule_based_suggestions(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": ""}), \
             patch.object(backend, '_deepseek_chat') as provider:
            result = self.client.post('/api/assistant/reply', headers=self.headers,
                                      json={"message": "I am going camping this weekend"})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.get_json()['source'], 'rules')
            self.assertTrue(result.get_json()['reply'])
            provider.assert_not_called()

    def test_trip_dates_and_items_persist(self):
        payload = {"id": "weekend", "name": "Weekend", "items": [{"id": "p", "text": "Passport", "assignedTo": "me"}],
                   "trip_start_at": "2099-06-01T09:00", "trip_end_at": "2099-06-03T18:00"}
        result = self.client.post('/api/scenarios', json=payload, headers=self.headers)
        self.assertEqual(result.status_code, 201)
        saved = self.client.get('/api/scenarios/weekend', headers=self.headers).get_json()
        self.assertEqual(saved['trip_end_at'], '2099-06-03T18:00:00')
        self.assertEqual(saved['items'], payload['items'])

    def test_reversed_dates_rejected(self):
        result = self.client.post('/api/scenarios', headers=self.headers, json={
            "name": "Weekend", "items": [{"text": "Passport"}],
            "trip_start_at": "2099-06-03T18:00", "trip_end_at": "2099-06-01T09:00"})
        self.assertEqual(result.status_code, 400)

    def test_invalid_coordinates_do_not_fall_back_to_another_city(self):
        with patch.object(backend, '_geocode_place') as geocode:
            for route in ('/api/weather', '/api/weather/detail'):
                for query in ('lat=abc&lon=10', 'lat=10', 'lon=10', 'lat=&lon=',
                              'lat=91&lon=0', 'lat=0&lon=181', 'lat=nan&lon=0', 'lat=inf&lon=0'):
                    with self.subTest(route=route, query=query):
                        result = self.client.get(f'{route}?{query}', headers=self.headers)
                        self.assertEqual(result.status_code, 400)
            geocode.assert_not_called()

    def test_valid_coordinates_reach_weather_provider(self):
        with patch.object(backend, '_resolve_gps_headline', return_value=('Dublin', None)), \
             patch.object(backend, '_weather_current_with_fallback', return_value={"temp": 14, "source": "open-meteo"}) as provider:
            result = self.client.get('/api/weather?lat=53.35&lon=-6.26', headers=self.headers)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.get_json()['temp'], 14)
            provider.assert_called_once_with(53.35, -6.26, 'Dublin', location_detail=None)

    def test_weather_outage_returns_unknown_temperature(self):
        with patch.object(backend, '_weather_resolve_from_request', return_value=(53.35, -6.26, 'Dublin', None)), \
             patch.object(backend, '_weather_current_with_fallback', side_effect=RuntimeError('offline')), \
             patch.object(backend, '_weather_detail_with_fallback', side_effect=RuntimeError('offline')):
            for route in ('/api/weather', '/api/weather/detail'):
                result = self.client.get(route, headers=self.headers)
                self.assertEqual(result.status_code, 200)
                self.assertIsNone(result.get_json()['temp'])
                self.assertIsNone(result.get_json()['weatherCode'])
                self.assertEqual(result.get_json()['source'], 'system-fallback')

    def test_readonly_and_editable_sharing(self):
        viewer = self.client.post('/api/auth/register', json={"username": "viewer", "password": "testpass123"}).get_json()
        viewer_headers = {"Authorization": f"Bearer {viewer['token']}"}
        friend = self.client.post('/api/friends/requests', json={"username": "viewer"}, headers=self.headers)
        self.assertEqual(friend.status_code, 201)
        requests = self.client.get('/api/friends/requests', headers=viewer_headers).get_json()
        self.assertEqual(self.client.post(f"/api/friends/requests/{requests[0]['id']}/accept", headers=viewer_headers).status_code, 200)
        self.client.post('/api/scenarios', json={"id": "shared", "name": "Shared trip", "items": [{"id": "p", "text": "Passport", "assignedTo": "me"}]}, headers=self.headers)
        self.assertEqual(self.client.post('/api/scenarios/shared/share', json={"username": "viewer", "can_edit": False}, headers=self.headers).status_code, 201)
        update = {"items": [{"id": "p", "text": "Passport", "assignedTo": "me", "critical": True}]}
        self.assertEqual(self.client.put('/api/scenarios/shared', json=update, headers=viewer_headers).status_code, 403)
        self.client.post('/api/scenarios/shared/share', json={"username": "viewer", "can_edit": True}, headers=self.headers)
        self.assertEqual(self.client.put('/api/scenarios/shared', json=update, headers=viewer_headers).status_code, 200)
        self.assertEqual(self.client.put('/api/scenarios/shared', json={"name": "Renamed"}, headers=viewer_headers).status_code, 403)


if __name__ == '__main__':
    unittest.main()

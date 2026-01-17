"""Smoke tests for API endpoints"""

import pytest
import json
from unittest.mock import patch, Mock


class TestAPIEndpoints:
    """Tests for Flask API endpoints"""
    
    def test_api_status_returns_200(self, client):
        """Test that /api/status returns 200 OK"""
        response = client.get('/api/status')
        assert response.status_code == 200
    
    def test_api_status_returns_json(self, client):
        """Test that /api/status returns valid JSON"""
        response = client.get('/api/status')
        assert response.content_type == 'application/json'
        data = response.get_json()
        assert isinstance(data, dict)
    
    def test_api_status_has_summary_and_retailers(self, client):
        """Test that /api/status has summary and retailers fields"""
        response = client.get('/api/status')
        data = response.get_json()
        assert 'summary' in data
        assert 'retailers' in data
        assert isinstance(data['summary'], dict)
        assert isinstance(data['retailers'], dict)
    
    def test_api_status_retailer_valid(self, client):
        """Test that /api/status/verizon returns valid retailer status"""
        response = client.get('/api/status/verizon')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, dict)
        assert 'name' in data
        assert 'enabled' in data
        assert 'overall_progress' in data
    
    def test_api_status_retailer_invalid_returns_404(self, client):
        """Test that invalid retailer returns 404"""
        response = client.get('/api/status/invalid_retailer')
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
    
    def test_api_scraper_start_without_retailer_returns_400(self, client):
        """Test that start without retailer param returns 400"""
        response = client.post('/api/scraper/start', 
                              json={},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_api_scraper_start_invalid_retailer_returns_400(self, client):
        """Test that start with invalid retailer returns 400"""
        response = client.post('/api/scraper/start', 
                              json={'retailer': 'invalid_retailer'},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_api_scraper_stop_without_retailer_returns_400(self, client):
        """Test that stop without retailer param returns 400"""
        response = client.post('/api/scraper/stop',
                              json={},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_api_config_get_returns_200(self, client):
        """Test that GET /api/config returns 200"""
        response = client.get('/api/config')
        assert response.status_code == 200
    
    def test_api_config_get_returns_yaml(self, client):
        """Test that GET /api/config returns YAML content"""
        response = client.get('/api/config')
        data = response.get_json()
        assert 'content' in data
        assert isinstance(data['content'], str)
        assert 'retailers:' in data['content']
    
    def test_api_config_post_without_config_returns_400(self, client):
        """Test that POST /api/config without config param returns 400"""
        response = client.post('/api/config',
                              json={},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_api_config_post_invalid_yaml_returns_400(self, client):
        """Test that invalid YAML syntax returns 400"""
        invalid_yaml = "retailers:\n  verizon:\n    - invalid syntax ["
        response = client.post('/api/config',
                              json={'content': invalid_yaml},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_api_config_post_missing_retailers_key_returns_400(self, client):
        """Test that config without 'retailers' key returns 400"""
        invalid_config = "something_else:\n  value: test"
        response = client.post('/api/config',
                              json={'content': invalid_config},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'validation failed' in data['error'].lower()
    
    def test_api_runs_valid_retailer(self, client):
        """Test that /api/runs/verizon returns 200"""
        response = client.get('/api/runs/verizon')
        assert response.status_code == 200
        data = response.get_json()
        assert 'runs' in data
        assert isinstance(data['runs'], list)
    
    def test_api_runs_invalid_retailer_returns_404(self, client):
        """Test that /api/runs with invalid retailer returns 404"""
        response = client.get('/api/runs/invalid_retailer')
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
    
    def test_api_logs_invalid_retailer_returns_404(self, client):
        """Test that /api/logs with invalid retailer returns 404"""
        response = client.get('/api/logs/invalid_retailer/run123')
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
    
    def test_api_logs_path_traversal_blocked(self, client):
        """Test that path traversal attempts are blocked"""
        response = client.get('/api/logs/verizon/../../../etc/passwd')
        assert response.status_code == 404
    
    def test_dashboard_index_returns_200(self, client):
        """Test that main dashboard page loads"""
        response = client.get('/')
        assert response.status_code == 200
    
    def test_api_scraper_restart_without_retailer_returns_400(self, client):
        """Test that restart without retailer param returns 400"""
        response = client.post('/api/scraper/restart',
                              json={},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_api_endpoints_require_json_content_type(self, client):
        """Test that POST endpoints require application/json content type"""
        response = client.post('/api/scraper/start',
                              data='{"retailer": "verizon"}',
                              content_type='text/plain')
        assert response.status_code == 415
    
    def test_api_runs_limit_parameter(self, client):
        """Test that /api/runs respects limit parameter"""
        response = client.get('/api/runs/verizon?limit=3')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['runs']) <= 3
    
    def test_api_status_all_retailers_present(self, client):
        """Test that all 6 retailers are in status response"""
        response = client.get('/api/status')
        data = response.get_json()
        retailers = data['retailers']
        expected = ['verizon', 'att', 'target', 'tmobile', 'walmart', 'bestbuy']
        for retailer in expected:
            assert retailer in retailers

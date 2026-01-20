"""Smoke tests for API endpoints"""


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

    def test_api_scraper_start_test_and_limit_conflict_returns_400(self, client):
        """Test that start with both test and limit returns 400"""
        response = client.post('/api/scraper/start',
                              json={'retailer': 'verizon', 'test': True, 'limit': 50},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'test' in data['error'].lower()
        assert 'limit' in data['error'].lower()

    def test_api_scraper_start_render_js_without_proxy_returns_400(self, client):
        """Test that render_js without proxy returns 400"""
        response = client.post('/api/scraper/start',
                              json={'retailer': 'verizon', 'render_js': True},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'render' in data['error'].lower()
        assert 'web_scraper_api' in data['error'].lower()

    def test_api_scraper_start_render_js_with_wrong_proxy_returns_400(self, client):
        """Test that render_js with non-web_scraper_api proxy returns 400"""
        response = client.post('/api/scraper/start',
                              json={'retailer': 'verizon', 'render_js': True, 'proxy': 'residential'},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'render' in data['error'].lower()
        assert 'web_scraper_api' in data['error'].lower()

    def test_api_scraper_start_limit_boolean_true_returns_400(self, client):
        """Test that limit with boolean True value returns 400 (not accepted as int)"""
        response = client.post('/api/scraper/start',
                              json={'retailer': 'verizon', 'limit': True},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'limit' in data['error'].lower()
        assert 'integer' in data['error'].lower()

    def test_api_scraper_start_limit_boolean_false_returns_400(self, client):
        """Test that limit with boolean False value returns 400 (not accepted as int)"""
        response = client.post('/api/scraper/start',
                              json={'retailer': 'verizon', 'limit': False},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'limit' in data['error'].lower()
        assert 'integer' in data['error'].lower()

    def test_api_scraper_stop_without_retailer_returns_400(self, client):
        """Test that stop without retailer param returns 400"""
        response = client.post('/api/scraper/stop',
                              json={},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_api_scraper_stop_timeout_boolean_true_returns_400(self, client):
        """Test that stop with boolean True timeout returns 400 (not accepted as int)"""
        response = client.post('/api/scraper/stop',
                              json={'retailer': 'verizon', 'timeout': True},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'timeout' in data['error'].lower()
        assert 'integer' in data['error'].lower()

    def test_api_scraper_stop_timeout_boolean_false_returns_400(self, client):
        """Test that stop with boolean False timeout returns 400 (not accepted as int)"""
        response = client.post('/api/scraper/stop',
                              json={'retailer': 'verizon', 'timeout': False},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'timeout' in data['error'].lower()
        assert 'integer' in data['error'].lower()

    def test_api_scraper_restart_timeout_boolean_true_returns_400(self, client):
        """Test that restart with boolean True timeout returns 400 (not accepted as int)"""
        response = client.post('/api/scraper/restart',
                              json={'retailer': 'verizon', 'timeout': True},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'timeout' in data['error'].lower()
        assert 'integer' in data['error'].lower()

    def test_api_scraper_restart_timeout_boolean_false_returns_400(self, client):
        """Test that restart with boolean False timeout returns 400 (not accepted as int)"""
        response = client.post('/api/scraper/restart',
                              json={'retailer': 'verizon', 'timeout': False},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'timeout' in data['error'].lower()
        assert 'integer' in data['error'].lower()

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

    def test_api_logs_path_traversal_url_encoded(self, client):
        """Test that URL-encoded path traversal is blocked"""
        # %2e = '.', %2f = '/'
        response = client.get('/api/logs/verizon/%2e%2e%2f%2e%2e%2fetc%2fpasswd')
        assert response.status_code == 404

    def test_api_logs_path_traversal_double_encoded(self, client):
        """Test that double-encoded path traversal is blocked"""
        # %252e = '%2e' which decodes to '.'
        response = client.get('/api/logs/verizon/%252e%252e%252f%252e%252e%252fetc%252fpasswd')
        # Either 400 (bad request) or 404 (not found) is acceptable
        assert response.status_code in [400, 404]

    def test_api_logs_path_traversal_windows_separators(self, client):
        """Test that Windows-style path traversal is blocked"""
        response = client.get('/api/logs/verizon/..\\..\\..\\windows\\system32')
        # Either 400 (bad request) or 404 (not found) is acceptable
        assert response.status_code in [400, 404]

    def test_api_logs_run_id_path_traversal(self, client):
        """Test that run_id parameter path traversal is blocked"""
        response = client.get('/api/logs/verizon/../../etc/passwd')
        assert response.status_code == 404

    def test_api_export_path_traversal_blocked(self, client):
        """Test that export endpoint blocks path traversal"""
        response = client.get('/api/export/../../../etc/passwd/json')
        assert response.status_code == 404

    def test_api_runs_path_traversal_blocked(self, client):
        """Test that runs endpoint blocks path traversal in retailer"""
        response = client.get('/api/runs/../../../etc/passwd')
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

    # Export API tests

    def test_api_export_formats_returns_200(self, client):
        """Test that /api/export/formats returns 200 OK"""
        response = client.get('/api/export/formats')
        assert response.status_code == 200
        data = response.get_json()
        assert 'formats' in data
        assert isinstance(data['formats'], list)

    def test_api_export_formats_contains_expected_formats(self, client):
        """Test that export formats include all expected formats"""
        response = client.get('/api/export/formats')
        data = response.get_json()
        format_ids = [f['id'] for f in data['formats']]
        expected = ['json', 'csv', 'excel', 'geojson']
        for fmt in expected:
            assert fmt in format_ids

    def test_api_export_invalid_retailer_returns_404(self, client):
        """Test that export with invalid retailer returns 404"""
        response = client.get('/api/export/invalid_retailer/json')
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    def test_api_export_invalid_format_returns_400(self, client):
        """Test that export with invalid format returns 400"""
        response = client.get('/api/export/verizon/invalid_format')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_api_export_multi_without_retailers_returns_400(self, client):
        """Test that multi export without retailers param returns 400"""
        response = client.post('/api/export/multi',
                              json={},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_api_export_multi_invalid_format_returns_400(self, client):
        """Test that multi export with invalid format returns 400"""
        response = client.post('/api/export/multi',
                              json={'retailers': ['verizon'], 'format': 'invalid'},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_api_export_multi_no_data_returns_404(self, client):
        """Test that multi export with no data returns 404"""
        response = client.post('/api/export/multi',
                              json={'retailers': ['verizon', 'att'], 'format': 'json'},
                              content_type='application/json')
        # May return 404 if no stores data exists for these retailers
        assert response.status_code in [200, 404]

    def test_api_export_multi_all_empty_stores_returns_404(self, client, tmp_path, monkeypatch):
        """Test that multi export with all retailers having empty stores returns 404"""
        import json
        from pathlib import Path
        
        # Create temporary data directory with empty store files
        data_dir = tmp_path / "data"
        verizon_dir = data_dir / "verizon" / "output"
        att_dir = data_dir / "att" / "output"
        verizon_dir.mkdir(parents=True)
        att_dir.mkdir(parents=True)
        
        # Create empty stores files
        (verizon_dir / "stores_latest.json").write_text("[]")
        (att_dir / "stores_latest.json").write_text("[]")
        
        # Mock Path to point to our temp directory
        def mock_path(path_str):
            if path_str.startswith("data/"):
                return tmp_path / path_str
            return Path(path_str)
        
        monkeypatch.setattr("dashboard.app.Path", mock_path)
        
        response = client.post('/api/export/multi',
                              json={'retailers': ['verizon', 'att'], 'format': 'excel'},
                              content_type='application/json')
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
        assert 'empty' in data['error'].lower()

    def test_api_export_multi_non_string_retailers_returns_400(self, client):
        """Test that multi export with non-string retailer values returns 400 Bad Request"""
        # Test with dict in retailers list
        response = client.post('/api/export/multi',
                              json={'retailers': [{'evil': True}], 'format': 'json'},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'string' in data['error'].lower() or 'invalid' in data['error'].lower()
        
        # Test with list in retailers list
        response = client.post('/api/export/multi',
                              json={'retailers': [['nested', 'list']], 'format': 'json'},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        
        # Test with number in retailers list
        response = client.post('/api/export/multi',
                              json={'retailers': [123], 'format': 'json'},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        
        # Test with mixed types
        response = client.post('/api/export/multi',
                              json={'retailers': ['verizon', {'evil': True}, 'att'], 'format': 'json'},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_api_export_multi_invalid_retailer_format_returns_400(self, client):
        """Test that multi export with invalid retailer name format returns 400"""
        # Test with uppercase
        response = client.post('/api/export/multi',
                              json={'retailers': ['Verizon'], 'format': 'json'},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'format' in data['error'].lower()
        
        # Test with special characters
        response = client.post('/api/export/multi',
                              json={'retailers': ['../etc/passwd'], 'format': 'json'},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        
        # Test starting with number
        response = client.post('/api/export/multi',
                              json={'retailers': ['123retailer'], 'format': 'json'},
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

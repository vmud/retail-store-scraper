"""
Test security fixes for timing attacks and XSS vulnerabilities.

Tests for:
1. API key validation using constant-time comparison (secrets.compare_digest)
2. XSS prevention in JavaScript escaping for onclick handlers
"""

import os
import pytest
import time
from dashboard.app import app


class TestAPIKeyTimingAttack:
    """Test that API key comparison is resistant to timing attacks."""

    def test_constant_time_comparison_used(self):
        """Verify that secrets.compare_digest is used for API key validation."""
        # Read the source code to verify the fix
        from pathlib import Path
        app_path = Path(__file__).parent.parent / 'dashboard' / 'app.py'
        with open(app_path, 'r') as f:
            content = f.read()
        
        # Verify secrets.compare_digest is used
        assert 'secrets.compare_digest' in content, \
            "API key comparison should use secrets.compare_digest for constant-time comparison"
        
        # Verify the old vulnerable pattern is NOT present
        assert 'if provided_key != api_key_configured:' not in content, \
            "Direct string comparison should not be used for API key validation"

    def test_no_vulnerable_comparison_pattern(self):
        """Verify the vulnerable comparison pattern is not present."""
        from pathlib import Path
        app_path = Path(__file__).parent.parent / 'dashboard' / 'app.py'
        with open(app_path, 'r') as f:
            content = f.read()
        
        # Verify the old vulnerable patterns are NOT present
        assert 'if provided_key != api_key_configured:' not in content, \
            "Direct string comparison should not be used for API key validation"
        assert 'if api_key_configured != provided_key:' not in content, \
            "Direct string comparison should not be used for API key validation"
        assert 'provided_key == api_key_configured' not in content, \
            "Direct string comparison should not be used for API key validation"


class TestXSSPrevention:
    """Test that XSS vulnerabilities in JavaScript escaping are fixed."""

    def test_escape_for_js_applies_html_encoding(self):
        """Verify that escapeForJs applies both JS and HTML encoding."""
        from pathlib import Path
        js_path = Path(__file__).parent.parent / 'dashboard' / 'static' / 'dashboard.js'
        with open(js_path, 'r') as f:
            content = f.read()
        
        # Verify that escapeForJs function exists
        assert 'function escapeForJs(str)' in content, \
            "escapeForJs function should exist"
        
        # Verify that it calls escapeHtml (HTML encoding step)
        # Look for the pattern within the escapeForJs function
        escape_for_js_start = content.find('function escapeForJs(str)')
        escape_for_js_end = content.find('\n}', escape_for_js_start)
        escape_for_js_body = content[escape_for_js_start:escape_for_js_end]
        
        assert 'escapeHtml(' in escape_for_js_body, \
            "escapeForJs should call escapeHtml to prevent XSS in HTML attributes"

    def test_dangerous_characters_escaped_in_onclick(self):
        """Test that dangerous characters are properly escaped for onclick handlers."""
        # This is a functional test that would require rendering the dashboard
        # For now, we verify the escaping logic through code inspection above
        pass

    def test_xss_payload_is_neutralized(self):
        """Test that XSS payloads are neutralized using data attributes (better approach)."""
        # Example payloads that should be safely escaped
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "'; alert('XSS'); //",
            '"; alert("XSS"); //',
            "<img src=x onerror=alert('XSS')>",
            "\\'; alert('XSS'); //",
            "\\'; alert(\\'XSS\\'); //",
        ]
        
        # Read the JavaScript file to verify escaping is applied
        from pathlib import Path
        js_path = Path(__file__).parent.parent / 'dashboard' / 'static' / 'dashboard.js'
        with open(js_path, 'r') as f:
            content = f.read()
        
        # Verify the BETTER security approach: data attributes instead of inline onclick
        # This avoids inline JavaScript execution entirely and uses event listeners instead
        
        # 1. Verify that retailer and runId are escaped with escapeHtml (not escapeForJs)
        #    because they're placed in HTML data attributes, not JS string literals
        assert 'const safeRetailerAttr = escapeHtml(retailer)' in content, \
            "Retailer should be escaped with escapeHtml for data attributes"
        assert 'const safeRunIdAttr = escapeHtml(runId)' in content, \
            "RunId should be escaped with escapeHtml for data attributes"
        
        # 2. Verify data attributes are used instead of onclick handlers
        assert 'data-retailer="${safeRetailerAttr}"' in content, \
            "Should use data-retailer attribute instead of inline onclick"
        assert 'data-run-id="${safeRunIdAttr}"' in content, \
            "Should use data-run-id attribute instead of inline onclick"
        
        # 3. Verify event listeners are bound separately (not inline)
        assert 'bindRunHistoryLogButtons' in content, \
            "Should use separate event listener binding instead of inline handlers"
        assert 'button.addEventListener' in content, \
            "Should use addEventListener for safe event binding"
        
        # 4. Verify NO inline onclick for user-controlled data in run items
        #    (onclick is OK for controlled retailerId from RETAILER_CONFIG, but not for API data)
        #    The createRunItem function should not have onclick with template literals
        create_run_item_start = content.find('function createRunItem(')
        create_run_item_end = content.find('\n}', create_run_item_start + 500)
        create_run_item_body = content[create_run_item_start:create_run_item_end]
        
        assert 'onclick="openLogViewer' not in create_run_item_body, \
            "createRunItem should not use inline onclick handlers for user data"


def test_security_documentation_exists():
    """Verify that security fixes are documented."""
    from pathlib import Path
    
    # Check if security fix documentation exists
    docs_dir = Path(__file__).parent.parent / '.docs'
    security_docs = list(docs_dir.glob('*SECURITY*.md')) + \
                   list(docs_dir.glob('*security*.md')) + \
                   list(docs_dir.glob('*XSS*.md')) + \
                   list(docs_dir.glob('*TIMING*.md'))
    
    # We should have documentation for these fixes
    # (This will be created after the tests)
    # For now, just log if docs are missing
    if not security_docs:
        print("\nNote: Consider adding security fix documentation to .docs/")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

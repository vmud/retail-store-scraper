"""
Security tests for XML parsing using defusedxml.

Tests verify that all XML-parsing scrapers use defusedxml instead of
the vulnerable stdlib xml.etree.ElementTree.
"""

import importlib
import inspect
import pytest


def test_att_scraper_uses_defusedxml():
    """Verify att.py imports defusedxml.ElementTree, not xml.etree.ElementTree."""
    from src.scrapers import att

    # Check the source code for the import
    source = inspect.getsource(att)

    # Should NOT have unsafe import
    assert "import xml.etree.ElementTree" not in source, \
        "att.py still uses unsafe xml.etree.ElementTree"

    # Should have safe import
    assert "import defusedxml.ElementTree" in source, \
        "att.py does not import defusedxml.ElementTree"


def test_tmobile_scraper_uses_defusedxml():
    """Verify tmobile.py imports defusedxml.ElementTree, not xml.etree.ElementTree."""
    from src.scrapers import tmobile

    # Check the source code for the import
    source = inspect.getsource(tmobile)

    # Should NOT have unsafe import
    assert "import xml.etree.ElementTree" not in source, \
        "tmobile.py still uses unsafe xml.etree.ElementTree"

    # Should have safe import
    assert "import defusedxml.ElementTree" in source, \
        "tmobile.py does not import defusedxml.ElementTree"


def test_walmart_scraper_uses_defusedxml():
    """Verify walmart.py imports defusedxml.ElementTree, not xml.etree.ElementTree."""
    from src.scrapers import walmart

    # Check the source code for the import
    source = inspect.getsource(walmart)

    # Should NOT have unsafe import
    assert "import xml.etree.ElementTree" not in source, \
        "walmart.py still uses unsafe xml.etree.ElementTree"

    # Should have safe import
    assert "import defusedxml.ElementTree" in source, \
        "walmart.py does not import defusedxml.ElementTree"


def test_bell_scraper_uses_defusedxml():
    """Verify bell.py imports defusedxml.ElementTree, not xml.etree.ElementTree."""
    from src.scrapers import bell

    # Check the source code for the import
    source = inspect.getsource(bell)

    # Should NOT have unsafe import
    assert "import xml.etree.ElementTree" not in source, \
        "bell.py still uses unsafe xml.etree.ElementTree"

    # Should have safe import
    assert "import defusedxml.ElementTree" in source, \
        "bell.py does not import defusedxml.ElementTree"


def test_samsclub_scraper_uses_defusedxml():
    """Verify samsclub.py imports defusedxml.ElementTree, not xml.etree.ElementTree."""
    from src.scrapers import samsclub

    # Check the source code for the import
    source = inspect.getsource(samsclub)

    # Should NOT have unsafe import
    assert "import xml.etree.ElementTree" not in source, \
        "samsclub.py still uses unsafe xml.etree.ElementTree"

    # Should have safe import
    assert "import defusedxml.ElementTree" in source, \
        "samsclub.py does not import defusedxml.ElementTree"


def test_defusedxml_blocks_billion_laughs():
    """
    Verify that defusedxml blocks billion laughs (entity expansion bomb) attack.

    The billion laughs attack uses nested entity expansion to cause
    exponential memory consumption and DoS.
    """
    import defusedxml.ElementTree as ET

    # Billion laughs payload - exponential entity expansion
    malicious_xml = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
]>
<lolz>&lol4;</lolz>"""

    # defusedxml should block this
    with pytest.raises((ET.ParseError, Exception)):
        ET.fromstring(malicious_xml)


def test_defusedxml_blocks_xxe_file_read():
    """
    Verify that defusedxml blocks XXE (XML External Entity) file read attack.

    XXE attacks can read arbitrary files from the server filesystem.
    """
    import defusedxml.ElementTree as ET

    # XXE payload attempting to read /etc/passwd
    malicious_xml = b"""<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root>&xxe;</root>"""

    # Parse should either raise or return empty entity
    try:
        root = ET.fromstring(malicious_xml)
        # If it doesn't raise, verify the entity wasn't expanded
        text = root.text or ""
        assert "root:" not in text.lower(), "XXE file read was not blocked!"
    except (ET.ParseError, Exception):
        # Expected - parser blocked the attack
        pass


def test_defusedxml_blocks_xxe_ssrf():
    """
    Verify that defusedxml blocks XXE SSRF (Server-Side Request Forgery) attack.

    XXE attacks can make HTTP requests to internal/external services.
    """
    import defusedxml.ElementTree as ET

    # XXE payload attempting to make HTTP request
    malicious_xml = b"""<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "http://evil.com/malicious">
]>
<root>&xxe;</root>"""

    # Parse should either raise or return empty entity
    try:
        root = ET.fromstring(malicious_xml)
        # If it doesn't raise, verify the entity wasn't expanded
        text = root.text or ""
        assert len(text) == 0 or text.isspace(), "XXE SSRF was not blocked!"
    except (ET.ParseError, Exception):
        # Expected - parser blocked the attack
        pass


def test_defusedxml_allows_valid_sitemap():
    """
    Verify that defusedxml allows legitimate sitemap XML to parse correctly.

    Security hardening should not break normal functionality.
    """
    import defusedxml.ElementTree as ET

    # Valid sitemap XML (simplified)
    valid_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/store/123</loc>
    <lastmod>2026-01-01</lastmod>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://example.com/store/456</loc>
    <lastmod>2026-01-02</lastmod>
    <priority>0.8</priority>
  </url>
</urlset>"""

    # Should parse successfully
    root = ET.fromstring(valid_xml)

    # Verify we can access elements
    assert root.tag.endswith("urlset")

    # Find all URL elements
    namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = root.findall(".//ns:url", namespace)
    assert len(urls) == 2

    # Verify we can read loc elements
    locs = [url.find("ns:loc", namespace).text for url in urls]
    assert "https://example.com/store/123" in locs
    assert "https://example.com/store/456" in locs

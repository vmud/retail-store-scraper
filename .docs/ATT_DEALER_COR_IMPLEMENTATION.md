# AT&T Store Type Classification Implementation

**Date:** January 17, 2026
**Feature:** Differentiate between Corporate (COR) and Dealer stores in AT&T scraper

## Overview

The AT&T scraper now extracts store type information to distinguish between:
- **COR (Corporate)** stores - Operated directly by AT&T
- **Dealer** stores - Authorized Retailers operated by third-party dealers

This classification is critical for business analytics, network planning, and understanding the AT&T retail channel structure.

## Implementation Details

### Data Extraction Method

The store type information is embedded in JavaScript variables within the store page HTML:

```javascript
// COR Store Example
let topDisplayType = 'AT&T Retail';
storeMasterDealer: ''

// Dealer Store Example
let topDisplayType = 'Authorized Retail';
storeMasterDealer: 'PRIME COMMUNICATIONS - 58'
```

### New Fields

Two new fields have been added to the `ATTStore` dataclass:

| Field | Type | Description | Example Values |
|-------|------|-------------|----------------|
| `sub_channel` | `str` | Store channel type | "COR", "Dealer" |
| `dealer_name` | `Optional[str]` | Dealer name (if applicable) | "PRIME COMMUNICATIONS", None |

### Extraction Logic

The `_extract_store_type_and_dealer()` function:

1. **Searches for JavaScript variables** using regex patterns:
   - `topDisplayType` - Indicates store type
   - `storeMasterDealer` - Contains dealer name with numeric suffix

2. **Classifies based on topDisplayType**:
   - `"AT&T Retail"` → COR store (no dealer)
   - `"Authorized Retail"` → Dealer store (extract dealer name)
   - Unknown/missing → Defaults to COR

3. **Cleans dealer names**:
   - Removes trailing numeric suffix (e.g., " - 58")
   - Example: "PRIME COMMUNICATIONS - 58" → "PRIME COMMUNICATIONS"

### Code Structure

```python
def _extract_store_type_and_dealer(html_content: str) -> tuple:
    """
    Extract store type (COR or Dealer) and dealer name from AT&T store page HTML.

    Returns:
        Tuple of (sub_channel, dealer_name)
        - sub_channel: "COR" or "Dealer"
        - dealer_name: Dealer name string or None for COR stores
    """
```

## Validated Examples

### COR Store
- **URL:** https://www.att.com/stores/new-york/new-york/2679
- **Name:** Broadway & E 8th St
- **Location:** New York, NY
- **sub_channel:** COR
- **dealer_name:** None
- **JavaScript variables:**
  ```javascript
  topDisplayType = 'AT&T Retail'
  storeMasterDealer: ''
  ```

### Dealer Store
- **URL:** https://www.att.com/stores/delaware/bear/113752
- **Name:** Bear
- **Location:** Bear, DE
- **sub_channel:** Dealer
- **dealer_name:** PRIME COMMUNICATIONS
- **JavaScript variables:**
  ```javascript
  topDisplayType = 'Authorized Retail'
  storeMasterDealer: 'PRIME COMMUNICATIONS - 58'
  ```

## Known Dealers

Based on initial testing, identified dealer partners include:
- PRIME COMMUNICATIONS
- (More will be discovered during full scraping runs)

## Output Format

### JSON Output
```json
{
  "store_id": "2679",
  "name": "Broadway & E 8th St",
  "telephone": "+1 212-677-4673",
  "street_address": "745 Broadway",
  "city": "New York",
  "state": "NY",
  "postal_code": "10003",
  "country": "US",
  "rating_value": 4.0,
  "rating_count": 157,
  "url": "https://www.att.com/stores/new-york/new-york/2679",
  "sub_channel": "COR",
  "dealer_name": null,
  "scraped_at": "2026-01-17T12:00:00.000000"
}
```

### CSV Output
```csv
store_id,name,telephone,street_address,city,state,postal_code,country,rating_value,rating_count,url,sub_channel,dealer_name,scraped_at
2679,Broadway & E 8th St,+1 212-677-4673,745 Broadway,New York,NY,10003,US,4.0,157,https://www.att.com/stores/new-york/new-york/2679,COR,,2026-01-17T12:00:00.000000
113752,Bear,+1 302-836-8600,1839 Pulaski Hwy,Bear,DE,19701,US,4.4,185,https://www.att.com/stores/delaware/bear/113752,Dealer,PRIME COMMUNICATIONS,2026-01-17T12:00:00.000000
```

## Configuration Updates

Updated `config/retailers.yaml` to include new fields in output:

```yaml
att:
  output_fields:
    - store_id
    - name
    - telephone
    - street_address
    - city
    - state
    - postal_code
    - country
    - rating_value
    - rating_count
    - url
    - sub_channel      # NEW
    - dealer_name      # NEW
    - scraped_at
```

## Usage

Run the AT&T scraper normally - the new fields are automatically extracted:

```bash
# Scrape all AT&T stores with new fields
python run.py --retailer att

# Test with limited stores
python run.py --retailer att --limit 10

# Resume from checkpoint
python run.py --retailer att --resume
```

## Error Handling

- If JavaScript variables are not found, defaults to `sub_channel="COR"` and `dealer_name=None`
- Logs debug message when display type cannot be determined
- No scraping failures - gracefully handles missing data

## Future Enhancements

Potential improvements:
1. **Dealer database** - Maintain list of known dealer partners
2. **Dealer statistics** - Track store counts per dealer
3. **Geographic analysis** - Dealer vs COR distribution by region
4. **Change detection** - Track when stores change ownership (COR ↔ Dealer)

## Testing

Manual testing verified correct extraction:
- ✓ COR store (NYC Broadway & E 8th St): Correctly identified as COR
- ✓ Dealer stores (PRIME COMMUNICATIONS): Correctly identified as Dealer
- ✓ Dealer name cleaning: Suffix removal works correctly
- ✓ CSV/JSON export: New fields properly formatted

## Technical Notes

### Why JavaScript Variables?
- Store type information is not in JSON-LD structured data
- Page displays "Authorized Retailer" badge using JavaScript
- Most reliable extraction point is JavaScript variable initialization
- Alternative: Parse visible HTML (less reliable, more fragile)

### Regex Patterns Used
```python
# Extract topDisplayType
r"let\s+topDisplayType\s*=\s*['\"]([^'\"]+)['\"]"

# Extract storeMasterDealer
r"storeMasterDealer:\s*['\"]([^'\"]+)['\"]"

# Clean dealer name (remove suffix)
r'\s*-\s*\d+\s*$'
```

### Performance Impact
- Minimal - regex search on HTML already being parsed
- No additional HTTP requests required
- Average extraction time: < 1ms per store

## References

- **COR Store Example:** https://www.att.com/stores/new-york/new-york/2679
- **Dealer Store Example:** https://www.att.com/stores/delaware/bear/113752
- **AT&T Store Locator:** https://www.att.com/stores/
- **Implementation PR:** feature/att-dealer-cor-extraction

---

*This feature aligns with the Verizon scraper's sub_channel/dealer_name fields for consistency across carrier scrapers.*

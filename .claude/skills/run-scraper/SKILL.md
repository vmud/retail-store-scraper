---
name: run-scraper
description: Run retail store scrapers with common configurations
disable-model-invocation: true
---

# Run Scraper

Run the retail store scraper with specified configuration.

## Common Invocations

| Command | Description |
|---------|-------------|
| `/run-scraper verizon` | Single retailer with defaults |
| `/run-scraper all --test` | All retailers, test mode (10 stores each) |
| `/run-scraper target --limit 50` | Target with 50-store limit |
| `/run-scraper all --incremental` | Incremental update (new/changed only) |
| `/run-scraper verizon --proxy residential` | Single retailer with proxy |
| `/run-scraper all --cloud` | All retailers with GCS sync |

## Available Flags

| Flag | Description |
|------|-------------|
| `--retailer <name>` | Run specific retailer (verizon, att, target, tmobile, walmart, bestbuy, telus, cricket) |
| `--all` | Run all enabled retailers concurrently |
| `--test` | Test mode - 10 stores per retailer |
| `--limit <n>` | Limit stores per retailer |
| `--resume` | Resume from checkpoints |
| `--incremental` | Only scrape new/changed stores |
| `--proxy <mode>` | Proxy mode: direct, residential, web_scraper_api |
| `--validate-proxy` | Validate proxy credentials before running |
| `--format <types>` | Export formats: json,csv,excel,geojson |
| `--cloud` | Sync to GCS after scraping |
| `--gcs-history` | Save timestamped history copies |
| `--states <codes>` | Target specific states (Verizon only) |
| `--exclude <retailers>` | Exclude specific retailers from --all |
| `--status` | Check status without running |

## Execution Steps

1. Ensure virtualenv is active: `source venv/bin/activate`
2. Parse user arguments from the command
3. Run: `python run.py {parsed_args}`
4. Report:
   - Store counts per retailer
   - Any errors or rate limiting encountered
   - Change detection summary (new/closed/modified)
   - GCS sync status if --cloud used

## Examples

```bash
# Quick test run
python run.py --retailer verizon --test

# Production run with proxy and cloud sync
python run.py --all --proxy residential --cloud

# Incremental update for specific retailers
python run.py --retailer target --retailer walmart --incremental

# Full run excluding problematic retailers
python run.py --all --exclude bestbuy --proxy residential
```

## Error Handling

- If rate limited (429), report the retailer and suggest `--proxy residential`
- If credentials missing for proxy, suggest running `--validate-proxy` first
- If GCS fails, data is still saved locally in `data/{retailer}/output/`

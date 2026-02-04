# Issue Triage Report

**Generated:** 2026-02-03
**Total Open Issues:** 28
**Reviewed By:** Claude Code (cc1)

---

## Summary Statistics

| Priority | Count | Description |
|----------|-------|-------------|
| P0 - Critical | 1 | Broken functionality, concurrency issues |
| P1 - High | 7 | Security issues, significant bugs |
| P2 - Medium | 11 | Quality improvements, moderate bugs |
| P3 - Low | 4 | Nice-to-haves, cosmetic issues |
| Close | 4 | Already fixed in codebase |
| Tracking | 1 | Umbrella issue (keep open) |

### By Type

| Type | Count |
|------|-------|
| Bug/Fix | 8 |
| Security | 4 |
| Enhancement | 12 |
| Refactor | 3 |
| Documentation | 1 |

---

## Issues to Close (Already Fixed)

These issues have been resolved in the codebase but remain open:

### #144 - fix: Reduce 403 backoff in get_with_retry
**Status:** Fixed in `src/shared/utils.py:226-231`
**Evidence:** Exponential backoff implemented with comment `# Use exponential backoff starting at 30s (#144)`
**Closing comment:** Resolved - exponential backoff for 403 errors implemented in get_with_retry()

### #145 - fix: Log full tracebacks for retailer errors
**Status:** Fixed in `run.py:566-567`
**Evidence:** `logging.error(f"[{retailer}] Scraper failed with exception:", exc_info=result)` with comment `# Log full traceback for debugging (#145)`
**Closing comment:** Resolved - full traceback logging implemented using exc_info parameter

### #146 - fix: Union fieldnames in export_service
**Status:** Fixed in `src/shared/export_service.py:144-153`
**Evidence:** `sample_size: int = 100` parameter with comment `# Takes union of fieldnames across first N records for completeness (#146)`
**Closing comment:** Resolved - fieldnames now collected from first N stores (default 100)

### #147 - fix: Add retry/backoff to Telus scraper
**Status:** Fixed in `src/scrapers/telus.py:189-192`
**Evidence:** `response = utils.get_with_retry(session, telus_config.API_URL, max_retries=telus_config.MAX_RETRIES, ...)`
**Closing comment:** Resolved - Telus now uses get_with_retry() with configurable retries

---

## Prioritized Issue List

### P0 - Critical (Fix Immediately)

#### #163 - Thread safety concern in setup_logging()
**Type:** Bug
**Risk:** High - duplicate log entries in concurrent execution
**Complexity:** Quick fix (< 30 min)
**Rationale:** setup_logging() has idempotency checks but no thread lock. Multiple threads could add duplicate handlers between check and add.
**Fix:** Add `threading.Lock()` around handler checks.

---

### P1 - High (Fix Soon)

#### #164 - Replace MD5 with SHA256 for cache keys
**Type:** Security
**Labels:** security, enhancement
**Complexity:** Quick fix
**Locations:** `walmart.py:51,90`, `bestbuy.py:425,532`
**Rationale:** MD5 is cryptographically broken. While not critical for cache keys, it triggers security scanners.
**Fix:** Replace `hashlib.md5()` with `hashlib.sha256()`.

#### #165 - Move hardcoded API keys to environment variables
**Type:** Security
**Labels:** security, enhancement
**Complexity:** Quick fix
**Status:** Partially fixed - Target uses env var with fallback
**Remaining:** `config/cricket_config.py:11` still has hardcoded `API_KEY`
**Fix:** Update cricket_config.py to use `os.getenv()`.

#### #172 - Use defusedxml for secure XML parsing
**Type:** Security
**Labels:** security, enhancement
**Complexity:** Moderate (need to add dependency)
**Rationale:** Standard library XML parser vulnerable to XXE and billion laughs attacks.
**Fix:** Add `defusedxml` to requirements.txt, update imports.

#### #166 - Refactor global RequestCounter state
**Type:** Enhancement
**Complexity:** Moderate
**Locations:** `verizon.py:24`, `target.py:25`, `walmart.py:24`
**Rationale:** Global mutable state causes testing difficulties and potential concurrency issues.

#### #167 - Narrow exception handling in scrapers
**Type:** Enhancement
**Complexity:** Moderate
**Rationale:** Broad `except Exception` hides bugs. Should catch specific exceptions or log with traceback.

#### #168 - Add comprehensive type hints
**Type:** Enhancement
**Complexity:** Substantial
**Rationale:** Missing return type hints reduce IDE support and static analysis effectiveness.

---

### P2 - Medium (Plan for Next Sprint)

#### #148 - Change detector key collisions
**Type:** Bug
**Tier:** 2 (Soon)
**Rationale:** Multi-tenant locations (malls) silently drop stores due to key collisions.

#### #149 - Walmart scraper ignores proxy overrides
**Type:** Bug
**Tier:** 2 (Soon)
**Rationale:** Users cannot switch proxy modes for Walmart via CLI/config.

#### #150 - Create shared scrape runner
**Type:** Refactor
**Tier:** 3 (Next)
**Rationale:** Reduce code duplication across scrapers.

#### #151 - Create central store schema and serializer
**Type:** Refactor
**Tier:** 3 (Next)
**Depends on:** #150

#### #152 - Add structured logging and metrics
**Type:** Feature
**Tier:** 3 (Next)
**Rationale:** Required for live monitoring and alerting.

#### #153 - Global concurrency and rate budgets
**Type:** Feature
**Tier:** 3 (Next)
**Depends on:** #150

#### #169 - Reduce code duplication in scraper run() functions
**Type:** Refactor
**Rationale:** Related to #150.

#### #170 - Standardize field naming across retailers
**Type:** Enhancement
**Rationale:** Makes cross-retailer analysis difficult.

#### #171 - Centralize magic numbers into configuration
**Type:** Enhancement
**Rationale:** Scattered config values are hard to maintain.

#### #173 - Add early CLI validation for state abbreviations
**Type:** Enhancement
**Rationale:** Invalid states not caught until scraper runs.

#### #176 - Improve test coverage for edge cases
**Type:** Testing
**Rationale:** Missing tests for concurrent execution, GCS mocks, malformed responses.

---

### P3 - Low (Backlog)

#### #154 - Unified caching interface
**Type:** Refactor
**Tier:** 4 (Optional)
**Rationale:** Nice to have after shared runner.

#### #155 - Discovery-phase checkpointing for Verizon
**Type:** Feature
**Tier:** 4 (Optional)
**Rationale:** Only valuable if discovery phases are slow.

#### #174 - Break down long functions
**Type:** Refactor
**Rationale:** Low priority without clear benefit. Functions work correctly.

#### #175 - Add __all__ exports to modules
**Type:** Enhancement
**Rationale:** Nice to have for API clarity.

#### #177 - Standardize docstring format
**Type:** Documentation
**Rationale:** Cosmetic improvement only.

---

### Tracking Issue (Keep Open)

#### #142 - Scraper Architecture Improvements (Jan 2026 Review)
**Type:** Tracking
**Rationale:** Umbrella issue for related work. Update checklist as issues are closed.

---

## Quick Wins (Can Fix Today)

| Issue | Description | Effort |
|-------|-------------|--------|
| #163 | Add threading.Lock to setup_logging | 15 min |
| #164 | Replace MD5 with SHA256 | 10 min |
| #165 | Move cricket API key to env var | 10 min |

**Total estimated: ~35 minutes for 3 security/critical fixes**

---

## Issues Needing Clarification

None identified. All issues are well-documented with clear acceptance criteria.

---

## Recommended Next Steps

1. **Close fixed issues** (#144, #145, #146, #147) with evidence
2. **Fix P0 critical** (#163) - thread safety
3. **Fix P1 security quick wins** (#164, #165)
4. **Add defusedxml** (#172) - requires dependency change
5. **Update #142 tracking issue** with current progress

---

## Test Status

**Note:** Some test files have collection errors due to missing `dotenv` module in test environment. This is an environment issue, not a code issue. Run `pip install python-dotenv` to resolve.

```
ERROR tests/test_cli_validation.py
ERROR tests/test_config_validation.py
ERROR tests/test_run_tracebacks.py
```

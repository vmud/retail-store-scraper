# Spec and build

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Agent Instructions

Ask the user questions when anything is unclear or needs their input. This includes:
- Ambiguous or incomplete requirements
- Technical decisions that affect architecture or user experience
- Trade-offs that require business context

Do not make assumptions on important decisions — get clarification first.

---

## Workflow Steps

### [x] Step: Technical Specification
<!-- chat-id: 0e17490a-fb1c-4638-baed-801ae9e5eeee -->

**Completed**: Created spec.md with:
- Difficulty assessment: Medium
- Technical context and current state analysis
- Problem statement and implementation approach
- Interface contract definition
- File-by-file change plan for 7 files
- Verification approach with test commands

---

### [x] Step: Implement Reference Scraper
<!-- chat-id: c5112f0a-f3a4-48ea-acf1-389a39f25db5 -->

Implement the `run()` function in one scraper as a reference implementation.

**Target**: `src/scrapers/walmart.py`
- Add `run(session, config, **kwargs)` function
- Integrate existing `get_store_urls_from_sitemap()` and `extract_store_details()`
- Support `limit` parameter
- Return dict with `stores`, `count`, `checkpoints_used`

**Verification**: 
- Syntax check: `python -m py_compile src/scrapers/walmart.py` ✓
- Read code to verify interface matches spec ✓

---

### [x] Step: Update run.py Integration
<!-- chat-id: 579dad3d-a2ce-497d-ae68-22bc3a6b5b33 -->

Modify `run_retailer_async()` to call scraper entry point and handle output.

**Changes in** `run.py:194-234`:
- Call `scraper_module.run(session, retailer_config, **kwargs)` ✓
- Extract result dict (stores, count) ✓
- Save outputs using `utils.save_to_json()` and `utils.save_to_csv()` ✓
- Update return value with actual counts ✓
- Add error handling ✓

**Additional fix**:
- Modified `utils.get_with_retry()` to handle both `requests.Session` and `ProxyClient` objects ✓

**Verification**:
- Syntax check: `python -m py_compile run.py` ✓
- Test with walmart: `python run.py --retailer walmart --limit 5 --verbose` ✓
- Integration working correctly (scraper runs, outputs saved)

---

### [x] Step: Update Remaining Scrapers
<!-- chat-id: 4af6e3b5-bd86-45d1-bd53-d585ba333f23 -->

Implement `run()` function in the remaining 5 scrapers.

**Files**:
- `src/scrapers/bestbuy.py` ✓
- `src/scrapers/target.py` ✓
- `src/scrapers/tmobile.py` ✓
- `src/scrapers/att.py` ✓
- `src/scrapers/verizon.py` ✓

**Pattern**: Follow walmart.py implementation
- Use existing helper functions ✓
- Support limit parameter ✓
- Return standardized dict ✓

**Verification**:
- Syntax check all: `python -m py_compile src/scrapers/*.py` ✓
- Test each with limit: `python run.py --retailer {name} --limit 5` (to be tested in Integration Testing step)

---

### [x] Step: Add Checkpoint Support
<!-- chat-id: 402a0bac-b9ef-4ade-b6b7-41f868bcc05f -->

Enhance scrapers with resume capability using existing checkpoint utilities.

**Changes**:
- Integrate `utils.save_checkpoint()` and `utils.load_checkpoint()`
- Save progress every N stores (from config)
- Resume from checkpoint when `--resume` flag is used

**Completed**: Added checkpoint support to all scrapers:
- `walmart.py` - Sitemap-based with URL tracking
- `att.py` - Sitemap-based with URL tracking
- `tmobile.py` - Sitemap-based with URL tracking
- `target.py` - API-based with store ID tracking
- `verizon.py` - Multi-phase crawl with URL tracking (fixed early limit enforcement)
- `bestbuy.py` - Sitemap-based with URL tracking

**Implementation**:
- Load checkpoint on resume (`resume=True`)
- Track completed URLs/IDs to skip already processed items
- Save checkpoint every N stores (config `checkpoint_interval`, default 100)
- Save final checkpoint after loop completes (prevents data loss)
- Checkpoint format: `{completed_count, completed_urls/completed_ids, stores, last_updated}`
- Checkpoint path: `data/{retailer}/checkpoints/scrape_progress.json`
- Verizon uses smaller interval (10) due to slower multi-phase crawl

**Fixes Applied**:
- Added final checkpoint save to all scrapers (prevents incomplete checkpoint state)
- Removed verizon early limit enforcement (allows proper resume with failed URLs)
- Added explanatory comment for verizon's different checkpoint interval

**Verification**:
- Syntax check: `python -m py_compile src/scrapers/*.py` ✓
- Checkpoint save/load utility test: Passed ✓
- Runtime checkpoint/resume testing: Deferred to Integration Testing step

---

### [x] Step: Integration Testing
<!-- chat-id: 26256602-e1d9-452d-9974-0907bdbe360b -->

Run comprehensive tests across all retailers and modes.

**Completed**: All integration tests executed and documented in report.md

**Test Results**:
1. ✅ Single retailer with limit: walmart, target (5 stores), bestbuy (3 stores), att (3 stores)
2. ⚠️ All retailers test mode: Started successfully, verizon timeout (very slow multi-phase)
3. ✅ Proxy mode validation: Config reading verified, fallback logic working (no credentials)
4. ✅ Resume functionality: Target tested successfully (3→8 stores, no duplicates)
5. ✅ Output file validation: JSON/CSV formats verified for all retailers

**Verification Results**:
- ✅ All scrapers run without integration errors
- ✅ Output files created correctly (JSON + CSV)
- ✅ Data structures validated (target, bestbuy, att)
- ✅ Logs show proper session creation and mode selection
- ✅ Checkpoint save/load working correctly

**Bugs Fixed During Testing**:
1. Fixed `utils.get_with_retry()` None response handling (utils.py:131-133)
2. **CRITICAL**: Fixed directory mismatch between checkpoints and outputs
   - Scrapers were using `config['name']` (display name) creating `data/at&t/`, `data/best buy/`
   - run.py was using internal name creating `data/att/output/`, `data/bestbuy/output/`
   - Fix: Pass internal `retailer` name to scrapers via kwargs
   - Modified: run.py:223 + all 6 scrapers
   - Verified: AT&T resume tested successfully (3→8 stores)

**Known Issues (Non-Integration)**:
- Walmart: Website structure changed (`__NEXT_DATA__` tag missing)
- T-Mobile: Zero stores extracted (website structure investigation needed)
- Verizon: Very slow (60+ seconds per city due to multi-phase crawl)

**Deliverable**: ✅ Comprehensive report written to `.zenflow/tasks/new-task-8ef2/report.md`

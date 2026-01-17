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

### [ ] Step: Implement Reference Scraper

Implement the `run()` function in one scraper as a reference implementation.

**Target**: `src/scrapers/walmart.py`
- Add `run(session, config, **kwargs)` function
- Integrate existing `get_store_urls_from_sitemap()` and `extract_store_details()`
- Support `limit` parameter
- Return dict with `stores`, `count`, `checkpoints_used`

**Verification**: 
- Syntax check: `python -m py_compile src/scrapers/walmart.py`
- Read code to verify interface matches spec

---

### [ ] Step: Update run.py Integration

Modify `run_retailer_async()` to call scraper entry point and handle output.

**Changes in** `run.py:194-234`:
- Call `scraper_module.run(session, retailer_config, **kwargs)`
- Extract result dict (stores, count)
- Save outputs using `utils.save_to_json()` and `utils.save_to_csv()`
- Update return value with actual counts
- Add error handling

**Verification**:
- Syntax check: `python -m py_compile run.py`
- Test with walmart: `python run.py --retailer walmart --limit 5 --verbose`
- Check output files: `ls -lh data/walmart/output/`

---

### [ ] Step: Update Remaining Scrapers

Implement `run()` function in the remaining 5 scrapers.

**Files**:
- `src/scrapers/bestbuy.py`
- `src/scrapers/target.py`
- `src/scrapers/tmobile.py`
- `src/scrapers/att.py`
- `src/scrapers/verizon.py`

**Pattern**: Follow walmart.py implementation
- Use existing helper functions
- Support limit parameter
- Return standardized dict

**Verification**:
- Syntax check all: `python -m py_compile src/scrapers/*.py`
- Test each with limit: `python run.py --retailer {name} --limit 5`

---

### [ ] Step: Add Checkpoint Support

Enhance scrapers with resume capability using existing checkpoint utilities.

**Changes**:
- Integrate `utils.save_checkpoint()` and `utils.load_checkpoint()`
- Save progress every N stores (from config)
- Resume from checkpoint when `--resume` flag is used

**Verification**:
- Test resume: Start scraping, interrupt (Ctrl+C), resume with `--resume`
- Check checkpoint files: `ls data/{retailer}/checkpoints/`

---

### [ ] Step: Integration Testing

Run comprehensive tests across all retailers and modes.

**Test Cases**:
1. Single retailer with limit: `python run.py --retailer walmart --limit 10`
2. All retailers test mode: `python run.py --all --test`
3. Different proxy modes (if credentials available)
4. Resume functionality
5. Output file validation

**Verification**:
- All scrapers run without errors
- Output files created for each retailer
- Data structure matches expected format
- Logs show session usage (direct vs proxy)

**Deliverable**: Write report to `.zenflow/tasks/new-task-8ef2/report.md`

#!/bin/bash
# PostToolUse hook: Validate store schema after scraper edits
# Only fires when editing files in src/scrapers/ (not _base.py or __init__.py)
# Non-blocking — emits systemMessage reminder, never denies the edit.

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // .tool_input.command // empty')

# Only trigger for scraper module edits
if ! echo "$file_path" | grep -qE 'src/scrapers/[a-z]+\.py$'; then
    exit 0
fi

# Skip base/init files
basename=$(basename "$file_path")
if [[ "$basename" == _* ]] || [[ "$basename" == "__init__.py" ]]; then
    exit 0
fi

retailer="${basename%.py}"

# Resolve project directory (hook may run from any cwd)
project_dir="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
if [ -z "$project_dir" ]; then
    exit 0
fi

# Resolve to absolute path for grep
if [[ "$file_path" != /* ]]; then
    file_path="$project_dir/$file_path"
fi

test_file="$project_dir/tests/test_scrapers/test_${retailer}.py"

messages=()

# Check that the scraper has a run() function
if ! grep -q 'def run(' "$file_path" 2>/dev/null; then
    messages+=("Scraper $retailer is missing the required run() function signature")
fi

# Check for validate_store_data usage
if ! grep -q 'validate_store_data\|validate_stores_batch' "$file_path" 2>/dev/null; then
    messages+=("Consider using validate_store_data() from src/shared/validation.py")
fi

# Check for delay enforcement (multiple patterns exist in the codebase)
if ! grep -qE 'random_delay|get_delay_for_mode|select_delays|time\.sleep|delay' "$file_path" 2>/dev/null; then
    messages+=("No delay between requests detected — add random_delay() to respect rate limits")
fi

# Check if test file exists
if [ ! -f "$test_file" ]; then
    messages+=("No test file found at tests/test_scrapers/test_${retailer}.py")
fi

if [ ${#messages[@]} -gt 0 ]; then
    combined=$(printf '%s. ' "${messages[@]}")
    echo "{\"systemMessage\": \"Schema check ($retailer): $combined\"}"
fi

exit 0

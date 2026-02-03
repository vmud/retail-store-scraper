#!/bin/bash
# PostToolUse hook: Run pylint on edited Python files
# Exit 0 always (non-blocking), output warnings to stderr

# Read hook input from stdin
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

# Only lint Python files
if [[ "$file_path" == *.py ]]; then
    # Check if file exists
    if [[ -f "$file_path" ]]; then
        # Run pylint with errors only, capture output
        lint_output=$(pylint --errors-only --output-format=text "$file_path" 2>&1)
        lint_exit=$?

        if [[ $lint_exit -ne 0 ]] && [[ -n "$lint_output" ]]; then
            # Output lint warnings as system message
            echo "{\"systemMessage\": \"⚠️ Lint errors in $file_path:\\n$lint_output\"}"
        fi
    fi
fi

# Always exit 0 - this is a non-blocking warning hook
exit 0

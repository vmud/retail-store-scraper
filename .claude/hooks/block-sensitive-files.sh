#!/bin/bash
# PreToolUse hook: Block edits to sensitive files
# Exit 2 to block, exit 0 to allow

# Read hook input from stdin
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

# Define sensitive file patterns
sensitive_patterns=(
    '\.env$'
    '\.env\.'
    'credentials\.json$'
    'service-account.*\.json$'
    '.*\.lock$'
    'package-lock\.json$'
    'poetry\.lock$'
    'requirements\.txt\.lock$'
)

# Check if file matches any sensitive pattern
for pattern in "${sensitive_patterns[@]}"; do
    if echo "$file_path" | grep -qE "$pattern"; then
        # Output denial reason and exit with blocking code
        echo "{\"hookSpecificOutput\": {\"hookEventName\": \"PreToolUse\", \"permissionDecision\": \"deny\", \"permissionDecisionReason\": \"Editing sensitive file '$file_path' requires explicit user confirmation. Use --force or manually edit this file.\"}}"
        exit 0  # Exit 0 with deny decision, not exit 2
    fi
done

# Allow the edit
exit 0

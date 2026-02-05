#!/bin/bash
# PostToolUse hook (Write): Remind about docs when creating new files in critical paths.
# Only fires for new files (not overwrites of existing ones).

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

[ -z "$file_path" ] && exit 0

# Check if this is a newly tracked file (not already in git)
# If git knows about it, this is an overwrite — skip the reminder
if git ls-files --error-unmatch "$file_path" &>/dev/null; then
    exit 0
fi

# New scraper file
if echo "$file_path" | grep -qE 'src/scrapers/[a-z_]+\.py$'; then
    name=$(basename "$file_path" .py)
    if [ "$name" != "__init__" ]; then
        echo "{\"systemMessage\": \"New scraper file created: $name. Remember to update the retailer table in README.md and the architecture/scraper list in CLAUDE.md.\"}"
        exit 0
    fi
fi

# New shared module
if echo "$file_path" | grep -qE 'src/shared/[a-z_]+\.py$'; then
    name=$(basename "$file_path" .py)
    if [ "$name" != "__init__" ]; then
        echo "{\"systemMessage\": \"New shared module created: $name. Consider updating the project structure in README.md and architecture section in CLAUDE.md.\"}"
        exit 0
    fi
fi

# New CI/CD workflow
if echo "$file_path" | grep -qE '\.github/workflows/.*\.yml$'; then
    name=$(basename "$file_path")
    echo "{\"systemMessage\": \"New CI/CD workflow created: $name. Update the CI/CD pipeline list in README.md.\"}"
    exit 0
fi

# New config file
if echo "$file_path" | grep -qE 'config/[a-z_]+_config\.py$'; then
    name=$(basename "$file_path" _config.py)
    echo "{\"systemMessage\": \"New retailer config created: $name. Ensure README.md and CLAUDE.md reflect the new retailer.\"}"
    exit 0
fi

exit 0

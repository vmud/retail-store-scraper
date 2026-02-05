#!/bin/bash
# PreToolUse hook (Bash): Warn before committing when docs may be stale.
# Non-blocking — emits systemMessage reminder, never denies the commit.

input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // empty')

# Only run on git commit commands
if ! echo "$command" | grep -qE '\bgit commit\b'; then
    exit 0
fi

# Get staged files (empty = nothing to check)
staged=$(git diff --cached --name-only 2>/dev/null)
if [ -z "$staged" ]; then
    exit 0
fi

# Patterns that affect README.md (public-facing structure)
readme_triggers=(
    'src/scrapers/'
    'src/shared/'
    'run.py'
    'config/retailers.yaml'
    '.github/workflows/'
    'Dockerfile'
    'docker-compose.yml'
    'requirements.txt'
    'deploy/'
    'scripts/'
)

# Patterns that affect CLAUDE.md (architecture & dev patterns)
claude_triggers=(
    'src/scrapers/'
    'src/shared/'
    'src/setup/'
    'run.py'
    'config/'
    'tests/'
    '.github/workflows/'
)

readme_affected=false
claude_affected=false
readme_staged=false
claude_staged=false
trigger_files=""

while IFS= read -r file; do
    [ -z "$file" ] && continue

    if [ "$file" = "README.md" ]; then
        readme_staged=true
    fi
    if [ "$file" = "CLAUDE.md" ]; then
        claude_staged=true
    fi

    for pattern in "${readme_triggers[@]}"; do
        if [[ "$file" == $pattern* ]]; then
            readme_affected=true
            trigger_files="$trigger_files $file"
            break
        fi
    done
    for pattern in "${claude_triggers[@]}"; do
        if [[ "$file" == $pattern* ]]; then
            claude_affected=true
            break
        fi
    done
done <<< "$staged"

warnings=""

if [ "$readme_affected" = true ] && [ "$readme_staged" = false ]; then
    warnings="README.md may need updating — staged changes include infrastructure files (${trigger_files## })."
fi

if [ "$claude_affected" = true ] && [ "$claude_staged" = false ]; then
    if [ -n "$warnings" ]; then
        warnings="$warnings CLAUDE.md may also need updating for architecture/pattern changes."
    else
        warnings="CLAUDE.md may need updating — staged changes include architecture files."
    fi
fi

if [ -n "$warnings" ]; then
    # Escape for JSON
    warnings=$(echo "$warnings" | sed 's/"/\\"/g')
    echo "{\"systemMessage\": \"$warnings\"}"
fi

exit 0

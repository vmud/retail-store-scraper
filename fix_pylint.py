#!/usr/bin/env python3
"""Script to automatically fix common pylint issues."""

import re
import sys
from pathlib import Path


def fix_long_lines_in_file(filepath):
    """Fix long lines by breaking them appropriately."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    fixed_lines = []

    for line in lines:
        if len(line) <= 100:
            fixed_lines.append(line)
            continue

        # Fix long user agent strings
        if '"Mozilla/' in line and 'AppleWebKit' in line:
            indent = len(line) - len(line.lstrip())
            # Convert to multi-line string with parentheses
            match = re.match(r'(\s*)"(Mozilla.+)"([,\]])', line)
            if match:
                fixed_lines.append(f'{match.group(1)}("{match.group(2)[:60]}"')
                fixed_lines.append(f'{" " * (indent + 1)}"{match.group(2)[60:]}")' + match.group(3))
                continue

        fixed_lines.append(line)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))


def fix_fstring_logging(filepath):
    """Replace f-string logging with lazy % formatting."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern: logging.method(f"text {var}")
    # Replace with: logging.method("text %s", var)
    pattern = r'logging\.(debug|info|warning|error|critical)\(f"([^"]+)"\)'

    def replacer(match):
        level = match.group(1)
        fstring = match.group(2)

        # Extract variables from f-string
        vars_in_fstring = re.findall(r'\{([^}]+)\}', fstring)

        if not vars_in_fstring:
            # No variables, just remove f prefix
            return f'logging.{level}("{fstring}")'

        # Replace {var} with %s
        msg = re.sub(r'\{[^}]+\}', '%s', fstring)

        # Build the replacement
        vars_str = ', '.join(vars_in_fstring)
        return f'logging.{level}("{msg}", {vars_str})'

    content = re.sub(pattern, replacer, content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def fix_open_encoding(filepath):
    """Add encoding='utf-8' to all open() calls.
    
    WARNING: This function is disabled due to regex limitations.
    The pattern r'\bopen\(([^)]+)\)' fails on nested parentheses.
    
    Example problem:
    - Input: open(os.path.join(dir, file), 'r')
    - Pattern matches: os.path.join(dir, file  (stops at first ')')
    - Result: open(os.path.join(dir, file, encoding="utf-8"), 'r')
    - This is WRONG: encoding added to join() instead of open()
    
    Proper parsing would require:
    1. AST-based analysis, OR
    2. Balanced parenthesis counting in regex, OR
    3. Manual review
    
    Manual review is required for such changes.
    """
    # DISABLED: This transformation is unsafe with nested function calls
    # Use AST-based tools or manual review instead
    pass


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python fix_pylint.py <file_or_directory>")
        sys.exit(1)

    path = Path(sys.argv[1])

    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = list(path.rglob('*.py'))
    else:
        print(f"Error: {path} is not a file or directory")
        sys.exit(1)

    for filepath in files:
        if 'venv' in str(filepath) or '.venv' in str(filepath):
            continue

        print(f"Processing {filepath}...")
        try:
            fix_fstring_logging(filepath)
            fix_open_encoding(filepath)
        except Exception as e:
            print(f"Error processing {filepath}: {e}")


if __name__ == '__main__':
    main()

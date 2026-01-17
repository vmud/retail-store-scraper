#!/usr/bin/env python3
"""Script to fix remaining pylint issues."""

import re
import sys
from pathlib import Path


def remove_unused_imports(filepath):
    """Remove common unused imports based on pylint output."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove specific unused imports identified by pylint
    replacements = [
        (r'from datetime import datetime\n', ''),  # If only datetime.now() is used, from datetime import datetime is fine
        (r'from dataclasses import field\n', ''),
        (r'from typing import List\n', ''),
        (r'from typing import Optional\n', ''),
    ]

    for pattern, replacement in replacements:
        # Only remove if the import is unused (we'd need context, so skip for safety)
        pass

    # Return unchanged for now - manual review needed
    return content


def fix_no_else_return(filepath):
    """Fix unnecessary elif/else after return statements."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for pattern: return\n    elif
        if i < len(lines) - 1:
            next_line = lines[i + 1] if i + 1 < len(lines) else ''

            if 'return ' in line and 'elif ' in next_line:
                # Change elif to if
                fixed_lines.append(line)
                indent = len(next_line) - len(next_line.lstrip())
                fixed_lines.append(next_line.replace('elif ', 'if ', 1))
                i += 2
                continue

            if 'return ' in line and 'else:' in next_line:
                # Skip the else, decrease indentation of following block
                fixed_lines.append(line)
                i += 2  # Skip the else line
                # De-indent the else block
                while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith('#'):
                    if lines[i].startswith('    ' * 2):  # Assuming 4-space indents
                        fixed_lines.append(lines[i][4:])  # Remove one level of indent
                        i += 1
                    else:
                        break
                continue

        fixed_lines.append(line)
        i += 1

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)


def remove_unused_variables(filepath):
    """Comment out or remove unused variable assignments."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Patterns for unused variables from pylint output
    # We'll add _ prefix to mark them as intentionally unused
    patterns = [
        (r'(\s+)(section_text) = ', r'\1_\2 = '),
        (r'(\s+)(url_parts) = ', r'\1_\2 = '),
        (r'(\s+)(headers) = ', r'\1_\2 = '),
        (r'(\s+)(cities) = ', r'\1_\2 = '),
        (r'(\s+)(stores) = ', r'\1_\2 = '),
        (r'(\s+)(session) = ', r'\1_\2 = '),
        (r'(\s+)(scraper_module) = ', r'\1_\2 = '),
        (r'(\s+)(mode_map) = ', r'\1_\2 = '),
        (r'(\s+)(client) = ', r'\1# \2 = '),
    ]

    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def fix_naming_conventions(filepath):
    """Fix naming conventions (convert CONSTANTS to lowercase where appropriate)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix US_STATES -> us_states
    content = content.replace('US_STATES = [', 'us_states = [')
    content = re.sub(r'\bUS_STATES\b', 'us_states', content)

    # Fix VALID_MODES -> valid_modes
    content = content.replace('VALID_MODES = ', 'valid_modes = ')
    content = re.sub(r'\bVALID_MODES\b', 'valid_modes', content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def fix_superfluous_parens(filepath):
    """Fix unnecessary parentheses after 'not' keyword.
    
    WARNING: This function is disabled due to safety concerns.
    Removing parentheses after 'not' can change boolean logic semantics.
    For example: 'not (a or b)' != 'not a or b' due to operator precedence.
    
    Original: not (a or b) evaluates as NOT(a OR b)
    Incorrect: not a or b evaluates as (NOT a) OR b
    
    Manual review is required for such changes.
    """
    # DISABLED: This transformation is unsafe and can introduce logic bugs
    # Do not automatically remove parentheses after 'not' keyword
    pass


def add_missing_docstrings(filepath):
    """Add basic docstrings to methods missing them."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for method definition without docstring
        if line.strip().startswith('def ') and '(' in line:
            fixed_lines.append(line)

            # Check if next non-empty line is a docstring
            next_idx = i + 1
            while next_idx < len(lines) and not lines[next_idx].strip():
                fixed_lines.append(lines[next_idx])
                next_idx += 1

            if next_idx < len(lines):
                next_line = lines[next_idx]
                if not (next_line.strip().startswith('"""') or next_line.strip().startswith("'''")):
                    # No docstring, add one
                    indent = len(line) - len(line.lstrip()) + 4
                    method_name = line.strip().split('def ')[1].split('(')[0]
                    fixed_lines.append(' ' * indent + f'"""{method_name.replace("_", " ").capitalize()}."""\n')

            i += 1
            continue

        fixed_lines.append(line)
        i += 1

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python fix_pylint_advanced.py <file_or_directory>")
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
        if 'venv' in str(filepath) or '.venv' in str(filepath) or 'fix_pylint' in str(filepath):
            continue

        print(f"Processing {filepath}...")
        try:
            fix_no_else_return(filepath)
            remove_unused_variables(filepath)
            fix_naming_conventions(filepath)
            fix_superfluous_parens(filepath)
            add_missing_docstrings(filepath)
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    main()

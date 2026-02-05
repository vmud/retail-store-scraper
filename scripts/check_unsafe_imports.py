#!/usr/bin/env python3
"""Pre-commit hook to ban known-unsafe imports.

This script scans Python files for imports that are known security risks
and provides safe alternatives. Used as a pre-commit hook to catch issues
before they reach CI.

Usage:
    python scripts/check_unsafe_imports.py [file1.py file2.py ...]

Exit codes:
    0 - No unsafe imports found
    1 - Unsafe imports detected
"""

import ast
import sys
from pathlib import Path
from typing import NamedTuple


class UnsafeImport(NamedTuple):
    """Represents an unsafe import finding."""

    file: str
    line: int
    module: str
    suggestion: str


# Map of banned module imports to their safe alternatives
# These are checked against import statements
BANNED_IMPORTS: dict[str, str] = {
    # XML parsing - vulnerable to XXE attacks
    "xml.etree.ElementTree": "Use defusedxml.ElementTree instead",
    "xml.etree.cElementTree": "Use defusedxml.ElementTree instead",
    "xml.dom.minidom": "Use defusedxml for XML parsing",
    "xml.dom.pulldom": "Use defusedxml for XML parsing",
    "xml.sax": "Use defusedxml for XML parsing",
    "xml.parsers.expat": "Use defusedxml for XML parsing",
    # Serialization - arbitrary code execution risk
    "pickle": "Use json for serialization (pickle allows arbitrary code execution)",
    "cPickle": "Use json for serialization (pickle allows arbitrary code execution)",
    "shelve": "Use json or sqlite3 for persistent storage",
    "marshal": "Use json for serialization",
}

# Dangerous builtin function calls
BANNED_BUILTINS: dict[str, str] = {
    "eval": "Never use eval() - use ast.literal_eval for safe literal parsing",
    "exec": "Never use exec() - refactor to avoid dynamic code execution",
    "compile": "Avoid compile() with untrusted input",
}

# Dangerous method calls on modules (e.g., os.system)
# Format: (module_name, method_name) -> suggestion
BANNED_METHOD_CALLS: dict[tuple[str, str], str] = {
    ("os", "system"): "Use subprocess.run with shell=False instead of os.system()",
    ("os", "popen"): "Use subprocess.run or subprocess.Popen instead of os.popen()",
}


def check_file(filepath: str) -> list[UnsafeImport]:
    """Check a single file for unsafe imports.

    Args:
        filepath: Path to the Python file to check.

    Returns:
        List of UnsafeImport findings.
    """
    findings: list[UnsafeImport] = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"Warning: Could not read {filepath}: {e}", file=sys.stderr)
        return findings

    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError as e:
        print(f"Warning: Syntax error in {filepath}: {e}", file=sys.stderr)
        return findings

    for node in ast.walk(tree):
        # Check import statements: import xml.etree.ElementTree
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                if module_name in BANNED_IMPORTS:
                    findings.append(UnsafeImport(
                        file=filepath,
                        line=node.lineno,
                        module=module_name,
                        suggestion=BANNED_IMPORTS[module_name],
                    ))

        # Check from imports: from xml.etree import ElementTree
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_name = node.module
                # Direct match on the module
                if module_name in BANNED_IMPORTS:
                    findings.append(UnsafeImport(
                        file=filepath,
                        line=node.lineno,
                        module=module_name,
                        suggestion=BANNED_IMPORTS[module_name],
                    ))
                # Check if importing a submodule that completes a banned path
                # e.g., "from xml.etree import ElementTree" should match "xml.etree.ElementTree"
                for alias in node.names:
                    full_path = f"{module_name}.{alias.name}"
                    if full_path in BANNED_IMPORTS:
                        findings.append(UnsafeImport(
                            file=filepath,
                            line=node.lineno,
                            module=full_path,
                            suggestion=BANNED_IMPORTS[full_path],
                        ))

        # Check for dangerous function/method calls
        elif isinstance(node, ast.Call):
            # Check builtin calls: eval(), exec()
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name in BANNED_BUILTINS:
                    findings.append(UnsafeImport(
                        file=filepath,
                        line=node.lineno,
                        module=f"{func_name}()",
                        suggestion=BANNED_BUILTINS[func_name],
                    ))

            # Check method calls: os.system(), os.popen()
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    module_name = node.func.value.id
                    method_name = node.func.attr
                    key = (module_name, method_name)
                    if key in BANNED_METHOD_CALLS:
                        findings.append(UnsafeImport(
                            file=filepath,
                            line=node.lineno,
                            module=f"{module_name}.{method_name}()",
                            suggestion=BANNED_METHOD_CALLS[key],
                        ))

    return findings


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for findings).
    """
    if len(sys.argv) < 2:
        print("Usage: check_unsafe_imports.py <file1.py> [file2.py ...]")
        return 0

    all_findings: list[UnsafeImport] = []

    for filepath in sys.argv[1:]:
        if not filepath.endswith(".py"):
            continue
        if not Path(filepath).exists():
            print(f"Warning: File not found: {filepath}", file=sys.stderr)
            continue

        findings = check_file(filepath)
        all_findings.extend(findings)

    if all_findings:
        print("\n" + "=" * 60)
        print("SECURITY: Unsafe imports detected!")
        print("=" * 60 + "\n")

        for finding in all_findings:
            print(f"  {finding.file}:{finding.line}")
            print(f"    Found: {finding.module}")
            print(f"    Fix:   {finding.suggestion}")
            print()

        print("=" * 60)
        print(f"Total: {len(all_findings)} unsafe import(s) found")
        print("=" * 60 + "\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

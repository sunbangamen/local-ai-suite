#!/usr/bin/env python3
"""
Automated Test Counter for Local AI Suite
Uses AST to accurately count test functions across all test files.
"""

import ast
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class TestFile:
    path: str
    test_count: int
    test_names: List[str]
    line_numbers: List[int]


class TestCounter(ast.NodeVisitor):
    """AST visitor to count test functions."""

    def __init__(self):
        self.tests: List[Tuple[str, int]] = []

    def visit_FunctionDef(self, node):
        if node.name.startswith("test_"):
            self.tests.append((node.name, node.lineno))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        if node.name.startswith("test_"):
            self.tests.append((node.name, node.lineno))
        self.generic_visit(node)


def count_tests_in_file(filepath: str) -> TestFile:
    """Count tests in a single file using AST."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filepath)

        counter = TestCounter()
        counter.visit(tree)

        return TestFile(
            path=filepath,
            test_count=len(counter.tests),
            test_names=[name for name, _ in counter.tests],
            line_numbers=[lineno for _, lineno in counter.tests],
        )
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return TestFile(path=filepath, test_count=0, test_names=[], line_numbers=[])


def find_test_files(base_dir: str = ".") -> List[str]:
    """Find all test files in the project."""
    test_files = []

    # Service test directories
    services_dir = Path(base_dir) / "services"
    if services_dir.exists():
        for service_dir in services_dir.iterdir():
            if service_dir.is_dir():
                tests_dir = service_dir / "tests"
                if tests_dir.exists():
                    test_files.extend(tests_dir.rglob("test_*.py"))

    # Root tests directory
    tests_dir = Path(base_dir) / "tests"
    if tests_dir.exists():
        test_files.extend(tests_dir.rglob("test_*.py"))

    return [str(f) for f in test_files]


def generate_report(base_dir: str = ".") -> Dict[str, any]:
    """Generate comprehensive test count report."""
    test_files = find_test_files(base_dir)

    results = {}
    total_tests = 0

    # Count tests by service
    services = {
        "rag": [],
        "embedding": [],
        "api_gateway": [],
        "mcp_server": [],
        "memory": [],
        "other": [],
    }

    for filepath in test_files:
        test_file = count_tests_in_file(filepath)
        total_tests += test_file.test_count

        # Categorize by service
        rel_path = Path(filepath).relative_to(base_dir)
        path_str = str(rel_path)

        if "services/rag" in path_str:
            services["rag"].append(test_file)
        elif "services/embedding" in path_str:
            services["embedding"].append(test_file)
        elif "services/mcp-server" in path_str:
            services["mcp_server"].append(test_file)
        elif "services/memory" in path_str or "tests/memory" in path_str:
            services["memory"].append(test_file)
        elif "tests/integration" in path_str or "api_gateway" in path_str:
            services["api_gateway"].append(test_file)
        else:
            services["other"].append(test_file)

    return {
        "total_tests": total_tests,
        "services": services,
        "all_files": [count_tests_in_file(f) for f in test_files],
    }


def print_report(report: Dict):
    """Print formatted test count report."""
    print("=" * 70)
    print("LOCAL AI SUITE - TEST COUNT REPORT")
    print("=" * 70)
    print()

    print(f"📊 TOTAL TESTS: {report['total_tests']}")
    print()

    print("📁 TESTS BY SERVICE:")
    print("-" * 70)

    services = report["services"]
    for service_name, test_files in services.items():
        if not test_files:
            continue

        service_total = sum(tf.test_count for tf in test_files)
        print(f"\n  {service_name.upper()}: {service_total} tests")

        for test_file in test_files:
            if test_file.test_count > 0:
                rel_path = Path(test_file.path).name
                print(f"    - {rel_path}: {test_file.test_count} tests")

    print()
    print("=" * 70)
    print()

    # Detailed breakdown
    print("📋 DETAILED TEST LIST:")
    print("-" * 70)

    for service_name, test_files in services.items():
        if not test_files:
            continue

        service_total = sum(tf.test_count for tf in test_files)
        if service_total == 0:
            continue

        print(f"\n{service_name.upper()}:")
        for test_file in test_files:
            if test_file.test_count > 0:
                print(f"\n  File: {test_file.path}")
                for name, lineno in zip(test_file.test_names, test_file.line_numbers):
                    print(f"    L{lineno:4d}: {name}")

    print()
    print("=" * 70)


def main():
    """Main entry point."""
    # Assume script is in scripts/ directory
    base_dir = Path(__file__).parent.parent

    report = generate_report(base_dir)
    print_report(report)

    # Save JSON report
    import json
    output_file = base_dir / "docs" / "test_count_report.json"
    output_file.parent.mkdir(exist_ok=True)

    # Convert TestFile objects to dicts for JSON serialization
    json_report = {
        "total_tests": report["total_tests"],
        "services": {
            service: [
                {
                    "path": tf.path,
                    "test_count": tf.test_count,
                    "test_names": tf.test_names,
                    "line_numbers": tf.line_numbers,
                }
                for tf in test_files
            ]
            for service, test_files in report["services"].items()
        }
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(json_report, f, indent=2, ensure_ascii=False)

    print(f"✅ Report saved to: {output_file}")


if __name__ == "__main__":
    main()

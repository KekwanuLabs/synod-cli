"""Test runner module for Synod - Auto-detect and run project tests.

Supports multiple test frameworks:
- Python: pytest, unittest
- JavaScript/TypeScript: jest, vitest, mocha, npm test
- Go: go test
- Rust: cargo test
- Ruby: rspec, minitest
- PHP: phpunit
- Java: maven, gradle
"""

import subprocess
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Tuple


@dataclass
class TestResult:
    """Result of running tests."""

    framework: str
    command: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    output: str = ""
    exit_code: int = 0
    failure_details: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if all tests passed."""
        return self.exit_code == 0 and self.failed == 0 and self.errors == 0

    @property
    def total(self) -> int:
        """Total number of tests."""
        return self.passed + self.failed + self.skipped + self.errors

    def summary(self) -> str:
        """Get a one-line summary."""
        if self.success:
            return f"{self.passed} passed"
        parts = []
        if self.failed:
            parts.append(f"{self.failed} failed")
        if self.errors:
            parts.append(f"{self.errors} errors")
        if self.passed:
            parts.append(f"{self.passed} passed")
        if self.skipped:
            parts.append(f"{self.skipped} skipped")
        return ", ".join(parts)


@dataclass
class TestFramework:
    """Definition of a test framework."""

    name: str
    detect_files: List[str]  # Files that indicate this framework
    detect_commands: List[str]  # Commands to check (e.g., pytest in PATH)
    run_command: List[str]  # Command to run tests
    run_in_dir: Optional[str] = None  # Subdirectory to run in (e.g., for monorepos)


# Supported test frameworks in priority order
FRAMEWORKS = [
    # Python
    TestFramework(
        name="pytest",
        detect_files=["pytest.ini", "pyproject.toml", "setup.py", "conftest.py"],
        detect_commands=["pytest"],
        run_command=["pytest", "-v", "--tb=short"],
    ),
    TestFramework(
        name="unittest",
        detect_files=["test_*.py", "tests/test_*.py"],
        detect_commands=["python"],
        run_command=["python", "-m", "unittest", "discover", "-v"],
    ),
    # JavaScript/TypeScript
    TestFramework(
        name="jest",
        detect_files=["jest.config.js", "jest.config.ts", "jest.config.mjs"],
        detect_commands=["npx"],
        run_command=["npx", "jest", "--verbose"],
    ),
    TestFramework(
        name="vitest",
        detect_files=["vitest.config.ts", "vitest.config.js"],
        detect_commands=["npx"],
        run_command=["npx", "vitest", "run"],
    ),
    TestFramework(
        name="mocha",
        detect_files=["mocharc.json", ".mocharc.js", ".mocharc.yaml"],
        detect_commands=["npx"],
        run_command=["npx", "mocha"],
    ),
    TestFramework(
        name="npm test",
        detect_files=["package.json"],
        detect_commands=["npm"],
        run_command=["npm", "test"],
    ),
    # Go
    TestFramework(
        name="go test",
        detect_files=["go.mod", "go.sum"],
        detect_commands=["go"],
        run_command=["go", "test", "-v", "./..."],
    ),
    # Rust
    TestFramework(
        name="cargo test",
        detect_files=["Cargo.toml"],
        detect_commands=["cargo"],
        run_command=["cargo", "test"],
    ),
    # Ruby
    TestFramework(
        name="rspec",
        detect_files=[".rspec", "spec/spec_helper.rb"],
        detect_commands=["rspec"],
        run_command=["rspec", "--format", "documentation"],
    ),
    TestFramework(
        name="minitest",
        detect_files=["Rakefile", "test/test_helper.rb"],
        detect_commands=["rake"],
        run_command=["rake", "test"],
    ),
    # PHP
    TestFramework(
        name="phpunit",
        detect_files=["phpunit.xml", "phpunit.xml.dist"],
        detect_commands=["phpunit"],
        run_command=["phpunit", "--verbose"],
    ),
    # Java
    TestFramework(
        name="maven",
        detect_files=["pom.xml"],
        detect_commands=["mvn"],
        run_command=["mvn", "test"],
    ),
    TestFramework(
        name="gradle",
        detect_files=["build.gradle", "build.gradle.kts"],
        detect_commands=["gradle", "./gradlew"],
        run_command=["./gradlew", "test"],
    ),
]


def detect_framework(workspace: Optional[Path] = None) -> Optional[TestFramework]:
    """Detect the test framework used in the workspace.

    Args:
        workspace: Path to workspace (defaults to cwd)

    Returns:
        Detected TestFramework or None
    """
    workspace = workspace or Path.cwd()

    for framework in FRAMEWORKS:
        # Check for detection files
        for pattern in framework.detect_files:
            if "*" in pattern:
                # Glob pattern
                if list(workspace.glob(pattern)):
                    # Also check command is available
                    if _check_command_available(framework.detect_commands):
                        return framework
            else:
                # Exact file
                if (workspace / pattern).exists():
                    if _check_command_available(framework.detect_commands):
                        return framework

    return None


def _check_command_available(commands: List[str]) -> bool:
    """Check if any of the commands are available in PATH."""
    for cmd in commands:
        if shutil.which(cmd):
            return True
    return False


def _parse_pytest_output(output: str) -> Tuple[int, int, int, int, List[str]]:
    """Parse pytest output to extract test counts and failures."""
    passed = failed = skipped = errors = 0
    failures = []

    lines = output.split("\n")
    in_failure = False
    current_failure = []

    for line in lines:
        # Look for summary line like "5 passed, 2 failed, 1 skipped"
        if "passed" in line or "failed" in line or "error" in line:
            import re

            # Match patterns like "5 passed", "2 failed", "1 error"
            passed_match = re.search(r"(\d+) passed", line)
            failed_match = re.search(r"(\d+) failed", line)
            skipped_match = re.search(r"(\d+) skipped", line)
            error_match = re.search(r"(\d+) error", line)

            if passed_match:
                passed = int(passed_match.group(1))
            if failed_match:
                failed = int(failed_match.group(1))
            if skipped_match:
                skipped = int(skipped_match.group(1))
            if error_match:
                errors = int(error_match.group(1))

        # Capture failure details
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            failures.append(line)
        elif "AssertionError" in line or "Error:" in line:
            failures.append(line)

    return passed, failed, skipped, errors, failures


def _parse_jest_output(output: str) -> Tuple[int, int, int, int, List[str]]:
    """Parse Jest output to extract test counts."""
    passed = failed = skipped = errors = 0
    failures = []

    import re

    # Jest summary: "Tests: 2 failed, 5 passed, 7 total"
    tests_match = re.search(
        r"Tests:\s*(?:(\d+) failed,\s*)?(?:(\d+) skipped,\s*)?(?:(\d+) passed,\s*)?(\d+) total",
        output,
    )
    if tests_match:
        failed = int(tests_match.group(1) or 0)
        skipped = int(tests_match.group(2) or 0)
        passed = int(tests_match.group(3) or 0)

    # Capture FAIL lines
    for line in output.split("\n"):
        if line.strip().startswith("FAIL ") or "✕" in line:
            failures.append(line.strip())

    return passed, failed, skipped, errors, failures


def _parse_go_output(output: str) -> Tuple[int, int, int, int, List[str]]:
    """Parse go test output."""
    passed = failed = skipped = errors = 0
    failures = []

    for line in output.split("\n"):
        if line.startswith("--- PASS:"):
            passed += 1
        elif line.startswith("--- FAIL:"):
            failed += 1
            failures.append(line)
        elif line.startswith("--- SKIP:"):
            skipped += 1
        elif "FAIL" in line and not line.startswith("---"):
            failures.append(line)

    return passed, failed, skipped, errors, failures


def _parse_generic_output(output: str, exit_code: int) -> Tuple[int, int, int, int, List[str]]:
    """Generic parser for unknown frameworks."""
    # Just use exit code to determine pass/fail
    if exit_code == 0:
        return 1, 0, 0, 0, []
    else:
        return 0, 1, 0, 0, [line for line in output.split("\n") if "error" in line.lower() or "fail" in line.lower()][:10]


def run_tests(
    workspace: Optional[Path] = None,
    framework: Optional[TestFramework] = None,
    extra_args: Optional[List[str]] = None,
    timeout: int = 300,
) -> TestResult:
    """Run tests in the workspace.

    Args:
        workspace: Path to workspace (defaults to cwd)
        framework: Specific framework to use (auto-detect if None)
        extra_args: Additional arguments to pass to test command
        timeout: Timeout in seconds

    Returns:
        TestResult with outcome details
    """
    workspace = workspace or Path.cwd()

    # Detect framework if not specified
    if framework is None:
        framework = detect_framework(workspace)

    if framework is None:
        return TestResult(
            framework="unknown",
            command="",
            output="No test framework detected. Supported: pytest, jest, go test, cargo test, etc.",
            exit_code=1,
        )

    # Build command
    command = framework.run_command.copy()
    if extra_args:
        command.extend(extra_args)

    # Determine working directory
    cwd = workspace
    if framework.run_in_dir:
        cwd = workspace / framework.run_in_dir

    # Run tests
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        exit_code = result.returncode

    except subprocess.TimeoutExpired:
        return TestResult(
            framework=framework.name,
            command=" ".join(command),
            output=f"Tests timed out after {timeout} seconds",
            exit_code=124,
        )
    except FileNotFoundError:
        return TestResult(
            framework=framework.name,
            command=" ".join(command),
            output=f"Command not found: {command[0]}",
            exit_code=127,
        )
    except Exception as e:
        return TestResult(
            framework=framework.name,
            command=" ".join(command),
            output=f"Error running tests: {e}",
            exit_code=1,
        )

    # Parse output based on framework
    if framework.name == "pytest":
        passed, failed, skipped, errors, failures = _parse_pytest_output(output)
    elif framework.name in ("jest", "vitest"):
        passed, failed, skipped, errors, failures = _parse_jest_output(output)
    elif framework.name == "go test":
        passed, failed, skipped, errors, failures = _parse_go_output(output)
    else:
        passed, failed, skipped, errors, failures = _parse_generic_output(output, exit_code)

    return TestResult(
        framework=framework.name,
        command=" ".join(command),
        passed=passed,
        failed=failed,
        skipped=skipped,
        errors=errors,
        output=output,
        exit_code=exit_code,
        failure_details=failures,
    )


def get_supported_frameworks() -> List[str]:
    """Get list of supported test framework names."""
    return [f.name for f in FRAMEWORKS]

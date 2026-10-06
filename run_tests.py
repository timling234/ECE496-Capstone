"""Run every unittest module under tests/, including non-package subfolders."""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def collect_tests(directory):
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    files = sorted(set(directory.rglob("test_*.py")) | set(directory.rglob("*_test.py")))
    for path in files:
        name = "asap_tests_" + "__".join(path.relative_to(directory).with_suffix("").parts)
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
            suite.addTests(loader.loadTestsFromModule(module))
        except Exception as error:
            # Import failures must count as failed verification, not skipped tests.
            def import_failure(error=error):
                raise error
            suite.addTest(unittest.FunctionTestCase(import_failure, description=f"Import {path.name}"))
    return suite


# FR-10: Developer verification harness (independent implementation)
def main(directory=None):
    suite = collect_tests(Path(directory) if directory else ROOT / "tests")
    if suite.countTestCases() == 0:
        print("No automated tests found.", file=sys.stderr)
        return 1
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

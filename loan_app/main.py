"""Application entry point for the loan calculator."""

import sys
import unittest

from cli import run_cli


def main() -> None:
    if "--test" in sys.argv:
        suite = unittest.defaultTestLoader.loadTestsFromName("tests")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
    run_cli()


if __name__ == "__main__":
    main()
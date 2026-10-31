"""Verifier-side unittest runner (stdlib only).

Usage: python3 pyrunner.py <module> [<module> ...]   (run from the workdir root)
Prints one line per test: "RESULT PASS <module>.<Class>.<test>" or "RESULT FAIL ...".
A module that fails to import prints nothing for its tests, so they count as failed.
"""
import sys
import traceback
import unittest


class _Result(unittest.TextTestResult):
    def _emit(self, test, ok):
        print(f"RESULT {'PASS' if ok else 'FAIL'} {test.id()}", flush=True)

    def addSuccess(self, test):
        super().addSuccess(test)
        self._emit(test, True)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._emit(test, False)

    def addError(self, test, err):
        super().addError(test, err)
        if isinstance(test, unittest.TestCase):
            self._emit(test, False)

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self._emit(test, False)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._emit(test, False)

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._emit(test, False)


def main(modules):
    sys.path.insert(0, ".")
    loader = unittest.TestLoader()
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2, resultclass=_Result)
    for name in modules:
        try:
            suite = loader.loadTestsFromName(name)
        except Exception:
            print(f"IMPORT ERROR in {name}:", flush=True)
            traceback.print_exc(file=sys.stdout)
            continue
        runner.run(suite)


if __name__ == "__main__":
    main(sys.argv[1:])

import os
import subprocess
import sys
import tempfile
import unittest

from prmrate.batch import run_batch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def golden(dirname, batch):
    base = os.path.join(ROOT, dirname, batch)
    with open(base + ".in.dat", encoding="ascii", newline="") as f:
        lines = f.read().splitlines()
    with open(base + ".out.dat", "rb") as f:
        expected = f.read()
    return base, lines, expected


class GoldenFileTest(unittest.TestCase):
    def check(self, dirname, batch):
        _, lines, expected = golden(dirname, batch)
        actual = "".join(l + "\n" for l in run_batch(lines)).encode("ascii")
        if actual != expected:
            exp, act = expected.decode().splitlines(), actual.decode().splitlines()
            for i, (e, a) in enumerate(zip(exp, act)):
                if e != a:
                    self.fail(f"{batch} line {i + 1}:\n expected {e!r}\n actual   {a!r}")
            self.fail(f"{batch}: expected {len(exp)} lines, got {len(act)}")

    def test_mainframe_sample_rn0315(self):
        self.check("legacy/golden", "RN0315")

    def test_adjustments_and_edges_ad0401(self):
        self.check("tests/golden", "AD0401")

    def test_volume_run_vol001(self):
        self.check("tests/golden", "VOL001")

    def test_missing_trailer_nt0501(self):
        self.check("tests/golden", "NT0501")

    def test_trailer_count_mismatch_bc0502(self):
        self.check("tests/golden", "BC0502")

    def test_cli_writes_byte_identical_file(self):
        base, _, expected = golden("tests/golden", "VOL001")
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "RATEOUT.dat")
            proc = subprocess.run([sys.executable, "-m", "prmrate.cli", base + ".in.dat", out],
                                  cwd=ROOT, capture_output=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode())
            with open(out, "rb") as f:
                self.assertEqual(f.read(), expected)


if __name__ == "__main__":
    unittest.main()

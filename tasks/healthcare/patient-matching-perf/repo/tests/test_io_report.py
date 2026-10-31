import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

from mpi import PairScorer, clusters, link
from mpi.cli import main
from mpi.io_csv import read_records, write_records
from mpi.report import worklist_summary
from mpi.synth import generate

from .fixtures import SMALL


class IoTest(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "r.csv")
            write_records(p, SMALL)
            self.assertEqual(read_records(p), SMALL)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "r.csv")
            write_records(p, SMALL)
            buf = StringIO()
            with redirect_stdout(buf):
                main(["link", p, "-o", os.path.join(d, "m.csv")])
            out = json.loads(buf.getvalue())
            self.assertEqual(out["candidate_groups"], 2)
            self.assertTrue(os.path.exists(os.path.join(d, "m.csv")))


class ReportTest(unittest.TestCase):
    def test_summary(self):
        s = worklist_summary(SMALL, clusters(SMALL, link(SMALL, PairScorer())))
        self.assertEqual(s["records_in_groups"], 5)
        self.assertEqual(s["cross_source_groups"], 2)
        self.assertEqual(s["group_sizes"], {2: 1, 3: 1})


class SynthTest(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(generate(30, seed=1), generate(30, seed=1))
        recs, truth = generate(30, seed=1)
        self.assertEqual(len(recs), sum(len(t) for t in truth))


if __name__ == "__main__":
    unittest.main()

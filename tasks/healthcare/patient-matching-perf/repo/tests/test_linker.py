import unittest

from mpi import MasterPatientIndex, Match, PairScorer, clusters, link
from mpi.synth import generate

from .fixtures import SMALL


class LinkTest(unittest.TestCase):
    def test_small_set(self):
        matches = link(SMALL, PairScorer())
        self.assertEqual([(m.left, m.right) for m in matches],
                         [("R000001", "R000002"), ("R000001", "R000003"), ("R000004", "R000005")])
        self.assertTrue(all(isinstance(m, Match) for m in matches))

    def test_input_order_irrelevant(self):
        self.assertEqual(link(list(reversed(SMALL)), PairScorer()), link(SMALL, PairScorer()))

    def test_clusters(self):
        groups = clusters(SMALL, link(SMALL, PairScorer()))
        self.assertEqual(groups[0], ["R000001", "R000002", "R000003"])
        self.assertIn(["R000004", "R000005"], groups)
        self.assertIn(["R000006"], groups)
        self.assertEqual(sum(len(g) for g in groups), len(SMALL))

    def test_synthetic_recall(self):
        records, truth = generate(60, seed=7)
        found = {(m.left, m.right) for m in link(records, PairScorer())}
        true_pairs = {tuple(sorted((a, b))) for ids in truth for i, a in enumerate(ids) for b in ids[i + 1:]}
        self.assertGreater(len(found & true_pairs) / max(1, len(true_pairs)), 0.6)


class MasterPatientIndexTest(unittest.TestCase):
    def test_online_matches(self):
        mpi = MasterPatientIndex(PairScorer())
        self.assertEqual(mpi.add(SMALL[0]), [])
        self.assertEqual([(m.left, m.right) for m in mpi.add(SMALL[1])], [("R000001", "R000002")])
        res = mpi.add(SMALL[2])
        self.assertEqual([(m.left, m.right) for m in res], [("R000001", "R000003")])
        self.assertEqual(len(mpi), 3)
        self.assertIs(mpi.get("R000002"), SMALL[1])

    def test_duplicate_id_rejected(self):
        mpi = MasterPatientIndex(PairScorer())
        mpi.add(SMALL[0])
        with self.assertRaises(ValueError):
            mpi.add(SMALL[0])


if __name__ == "__main__":
    unittest.main()

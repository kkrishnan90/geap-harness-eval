import unittest

from tests.csv import make_csv, stop_row

from routebatch import parse_batch
from routebatch.planner import PlanningError, loading_order, parcels_per_route, route_ids

ROWS = [
    stop_row("A1", "R-01", 1, 2),
    stop_row("A2", "R-01", 2, 1),
    stop_row("B1", "R-02", 1, 4),
    stop_row("C1", "R-03", 1, 1),
    stop_row("D1", "R-04", 1, 3),
    stop_row("E1", "R-05", 1, 2),
    stop_row("E2", "R-05", 2, 2),
]


def _batch(rows=ROWS):
    return parse_batch(make_csv(rows))


class PlannerTest(unittest.TestCase):
    def test_route_ids(self):
        self.assertEqual(sorted(route_ids(_batch())), ["R-01", "R-02", "R-03", "R-04", "R-05"])

    def test_loading_order_reverses_sequence(self):
        self.assertEqual(loading_order(_batch(), "R-05"), ["E2", "E1"])

    def test_sequence_gap_rejected(self):
        rows = ROWS[:1] + [stop_row("A3", "R-01", 3)]
        with self.assertRaises(PlanningError):
            loading_order(_batch(rows), "R-01")

    def test_parcels_per_route(self):
        self.assertEqual(parcels_per_route(_batch())["R-05"], 4)


if __name__ == "__main__":
    unittest.main()

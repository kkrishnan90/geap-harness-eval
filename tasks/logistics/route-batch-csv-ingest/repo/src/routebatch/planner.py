"""Per-route views over a RouteBatch."""

from collections import defaultdict


class PlanningError(ValueError):
    pass


def route_ids(batch):
    """Distinct route ids in the batch."""
    return {s.route_id for s in batch.stops}


def stops_for_route(batch, route_id):
    stops = sorted((s for s in batch.stops if s.route_id == route_id), key=lambda s: s.seq)
    seqs = [s.seq for s in stops]
    if seqs != list(range(1, len(seqs) + 1)):
        raise PlanningError(f"route {route_id}: sequence must be 1..n, got {seqs}")
    return stops


def loading_order(batch, route_id):
    """Van loading order: last stop loaded first."""
    return [s.stop_id for s in reversed(stops_for_route(batch, route_id))]


def parcels_per_route(batch):
    totals = defaultdict(int)
    for s in batch.stops:
        totals[s.route_id] += s.parcels
    return dict(totals)

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Stop:
    stop_id: str
    route_id: str
    seq: int
    postcode: str
    lat: float
    lon: float
    window: Optional[Tuple[int, int]]  # minutes after midnight, [start, end)
    parcels: int
    notes: str = ""


@dataclass
class RouteBatch:
    source: str
    delimiter: str
    stops: List[Stop] = field(default_factory=list)

    def by_id(self, stop_id):
        for s in self.stops:
            if s.stop_id == stop_id:
                return s
        raise KeyError(stop_id)

"""Store directory. In production this is synced nightly from the store master."""

from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Store:
    store_id: str
    name: str
    tz: ZoneInfo
    currency: str


_STORES = {
    s.store_id: s
    for s in (
        Store("US-NYC-014", "Manhattan 34th St", ZoneInfo("America/New_York"), "USD"),
        Store("US-LAX-002", "Los Angeles Grove", ZoneInfo("America/Los_Angeles"), "USD"),
        Store("DE-BER-001", "Berlin Alexanderplatz", ZoneInfo("Europe/Berlin"), "EUR"),
        Store("GB-LON-007", "London Oxford St", ZoneInfo("Europe/London"), "GBP"),
        Store("JP-TYO-003", "Tokyo Shibuya", ZoneInfo("Asia/Tokyo"), "JPY"),
        Store("AU-SYD-001", "Sydney Pitt St", ZoneInfo("Australia/Sydney"), "AUD"),
        Store("IN-BLR-005", "Bengaluru Indiranagar", ZoneInfo("Asia/Kolkata"), "INR"),
    )
}


def get_store(store_id: str) -> Store:
    try:
        return _STORES[store_id]
    except KeyError:
        raise KeyError(f"unknown store {store_id!r}") from None


def all_stores():
    return sorted(_STORES.values(), key=lambda s: s.store_id)

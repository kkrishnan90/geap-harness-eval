"""Postcode to rating zone. The sorting hub is in postcode region 4."""

from dataclasses import dataclass

# First digit of the 5-digit postcode -> zone.
_REGION_ZONE = {
    "4": 1,
    "3": 2, "5": 2,
    "2": 3, "6": 3,
    "1": 4, "7": 4,
    "0": 5, "8": 5, "9": 5,
}

# Islands and other delivery areas served by subcontractors.
REMOTE_POSTCODES = frozenset({
    "18565", "25845", "25846", "25847", "25849", "25859", "25863", "25869",
    "25938", "25946", "25980", "25992", "25996", "25997", "25999", "26465",
    "26474", "26486", "26548", "26571", "26579", "26757", "27498", "83256",
})


@dataclass(frozen=True)
class Zone:
    number: int
    remote: bool


def normalize_postcode(postcode):
    pc = str(postcode).strip().replace(" ", "")
    if len(pc) != 5 or not pc.isdigit():
        raise ValueError(f"invalid postcode {postcode!r}")
    return pc


def zone_for_postcode(postcode):
    pc = normalize_postcode(postcode)
    return Zone(_REGION_ZONE[pc[0]], pc in REMOTE_POSTCODES)

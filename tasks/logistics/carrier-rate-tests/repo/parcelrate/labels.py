"""Shipping label text helpers (thermal printer, 4x6 inch, 38 chars/line)."""

import textwrap

LINE_WIDTH = 38


def address_block(name, street, postcode, city, country="DE"):
    lines = [name.strip(), street.strip(), f"{postcode.strip()} {city.strip().upper()}"]
    if country != "DE":
        lines.append(country.upper())
    out = []
    for line in lines:
        out.extend(textwrap.wrap(line, LINE_WIDTH) or [""])
    return "\n".join(out)


def service_banner(zone, remote):
    banner = f"ZONE {zone}"
    if remote:
        banner += " / REMOTE"
    return banner.center(LINE_WIDTH, "*")

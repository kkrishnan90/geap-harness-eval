# Domestic parcel tariff 2026-Q3 (customer sheet)

Prices in EUR, excluding VAT. See `parcelrate/rates.py` for the implementation.

| Zone | First 0.5 kg | Each additional 0.5 kg |
| --- | --- | --- |
| 1 | 4.90 | 0.60 |
| 2 | 5.40 | 0.70 |
| 3 | 5.90 | 0.85 |
| 4 | 6.60 | 1.00 |
| 5 | 7.40 | 1.20 |

Zones are derived from the first digit of the destination postcode
(hub region 4 = zone 1). Remote delivery areas (islands) carry a surcharge.

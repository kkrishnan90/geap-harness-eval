"""Error codes shared with the channel gateway.

The numeric values are persisted in the repair queue and mapped to customer
facing texts by the gateway. Never renumber or rename an existing member.
"""

from enum import Enum


class ErrorCode(Enum):
    OK = 0
    EMPTY = 10
    INVALID_CHARACTERS = 11
    UNKNOWN_COUNTRY = 12
    INVALID_LENGTH = 13
    INVALID_CHECKSUM = 14
    INVALID_BIC = 20
    BIC_COUNTRY_MISMATCH = 21
    INVALID_AMOUNT = 30
    UNSUPPORTED_CURRENCY = 31
    NON_SEPA_COUNTRY = 32
    MISSING_FIELD = 40

#ifndef BOND_STORE_H
#define BOND_STORE_H

/* Bonded phone keys (max 8, least recently used entry is replaced). Persisted to the
 * emulated EEPROM by the NVM task; here only the RAM image. */

#include <stdbool.h>
#include <stdint.h>

#define BOND_STORE_MAX 8

void bond_store_clear(void);
bool bond_store_contains(const uint8_t addr[6]);
/* Adds or refreshes a bond. Returns the slot index used. */
int bond_store_add(const uint8_t addr[6]);
bool bond_store_remove(const uint8_t addr[6]);
int bond_store_count(void);

#endif

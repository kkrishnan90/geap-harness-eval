#include "bond_store.h"

#include <string.h>

typedef struct {
    uint8_t addr[6];
    uint32_t last_use;
    bool used;
} bond_slot_t;

static bond_slot_t slots[BOND_STORE_MAX];
static uint32_t clock_tick;

static int find(const uint8_t addr[6])
{
    for (int i = 0; i < BOND_STORE_MAX; i++) {
        if (slots[i].used && memcmp(slots[i].addr, addr, 6) == 0) {
            return i;
        }
    }
    return -1;
}

void bond_store_clear(void)
{
    memset(slots, 0, sizeof slots);
    clock_tick = 0;
}

bool bond_store_contains(const uint8_t addr[6])
{
    return find(addr) >= 0;
}

int bond_store_add(const uint8_t addr[6])
{
    int idx = find(addr);
    if (idx < 0) {
        idx = 0;
        for (int i = 0; i < BOND_STORE_MAX; i++) {
            if (!slots[i].used) {
                idx = i;
                break;
            }
            if (slots[i].last_use < slots[idx].last_use) {
                idx = i;
            }
        }
        memcpy(slots[idx].addr, addr, 6);
        slots[idx].used = true;
    }
    slots[idx].last_use = ++clock_tick;
    return idx;
}

bool bond_store_remove(const uint8_t addr[6])
{
    int idx = find(addr);
    if (idx < 0) {
        return false;
    }
    slots[idx].used = false;
    return true;
}

int bond_store_count(void)
{
    int n = 0;
    for (int i = 0; i < BOND_STORE_MAX; i++) {
        n += slots[i].used ? 1 : 0;
    }
    return n;
}

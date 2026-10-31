#!/usr/bin/env bash
# Verifier for retail/inventory-reservation-race. Usage: run.sh <workdir> <results_json>
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
lib_init "$@"
lib_overlay
cd "$WORKDIR" || exit 0
lib_java src/test/java/testkit src/main/java src/test/java \
  com.northwind.commerce.inventory.InventoryRepositoryTest \
  com.northwind.commerce.inventory.ReservationServiceTest \
  com.northwind.commerce.checkout.CheckoutServiceTest \
  com.northwind.commerce.pricing.PriceCalculatorTest \
  com.northwind.commerce.inventory.ReservationConcurrencyTest

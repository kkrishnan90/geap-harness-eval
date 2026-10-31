package com.meridian.ledger;

import com.meridian.ledger.core.Account;
import com.meridian.ledger.core.AccountType;
import com.meridian.ledger.core.EntryBuilder;
import com.meridian.ledger.core.Ledger;
import com.meridian.ledger.core.Side;
import com.meridian.ledger.core.UnbalancedEntryException;
import com.meridian.ledger.fx.FxConverter;
import com.meridian.ledger.fx.RateTable;
import com.meridian.ledger.money.Money;
import testkit.Test;

import java.math.BigDecimal;
import java.time.LocalDate;

import static testkit.Assert.*;

public class LedgerInvariantTest {
    @Test
    public void oneCentImbalanceRejected() {
        Ledger l = Ledger.inEur();
        Account cash = l.open(Account.of("1000", "Cash EUR", AccountType.ASSET, "EUR"));
        Account fees = l.open(Account.of("4000", "Fee income", AccountType.INCOME, "EUR"));
        EntryBuilder b = new EntryBuilder(l, new FxConverter(new RateTable()), "X1", LocalDate.of(2025, 1, 2))
                .line(cash, Side.DEBIT, Money.of("100.00", "EUR"), new BigDecimal("100.00"))
                .line(fees, Side.CREDIT, Money.of("99.99", "EUR"), new BigDecimal("99.99"));
        assertThrows(UnbalancedEntryException.class, b::post);
        assertEquals(0, l.entries().size());
    }

    @Test
    public void oneCentImbalanceAcrossCurrenciesRejected() {
        Ledger l = Ledger.inEur();
        Account cash = l.open(Account.of("1000", "Cash EUR", AccountType.ASSET, "EUR"));
        Account usd = l.open(Account.of("1010", "Nostro USD", AccountType.ASSET, "USD"));
        EntryBuilder b = new EntryBuilder(l, new FxConverter(new RateTable()), "X2", LocalDate.of(2025, 1, 2))
                .line(usd, Side.DEBIT, Money.of("108.50", "USD"), new BigDecimal("100.01"))
                .line(cash, Side.CREDIT, Money.of("100.00", "EUR"), new BigDecimal("100.00"));
        assertThrows(UnbalancedEntryException.class, b::post);
    }
}

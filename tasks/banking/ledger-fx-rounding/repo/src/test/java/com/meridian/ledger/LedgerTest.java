package com.meridian.ledger;

import com.meridian.ledger.core.Account;
import com.meridian.ledger.core.AccountType;
import com.meridian.ledger.core.EntryBuilder;
import com.meridian.ledger.core.Ledger;
import com.meridian.ledger.core.LedgerException;
import com.meridian.ledger.core.UnbalancedEntryException;
import com.meridian.ledger.fx.FxConverter;
import com.meridian.ledger.fx.RateTable;
import com.meridian.ledger.money.Money;
import com.meridian.ledger.report.TrialBalance;
import testkit.Test;

import java.math.BigDecimal;
import java.time.LocalDate;

import static testkit.Assert.*;

public class LedgerTest {
    static final LocalDate D = LocalDate.of(2025, 1, 15);
    Ledger ledger = Ledger.inEur();
    Account cash = ledger.open(Account.of("1000", "Cash EUR", AccountType.ASSET, "EUR"));
    Account nostro = ledger.open(Account.of("1010", "Nostro USD", AccountType.ASSET, "USD"));
    Account fees = ledger.open(Account.of("4000", "Fee income", AccountType.INCOME, "EUR"));
    FxConverter fx = new FxConverter(new RateTable().put("USD", "EUR", "0.9200"));

    @Test
    public void balancedEntryUpdatesBalances() {
        new EntryBuilder(ledger, fx, "E1", D).debit(nostro, Money.of("1000.00", "USD"))
                .credit(cash, Money.of("920.00", "EUR")).post();
        assertAmount("1000.00", ledger.balance(nostro).getAmount(), "USD balance");
        assertAmount("920.00", ledger.balance(nostro).getFunctional(), "EUR value");
        assertAmount("-920.00", ledger.balance(cash).getFunctional(), "cash");
        assertTrue(TrialBalance.of(ledger).isBalanced());
    }

    @Test
    public void grosslyUnbalancedEntryRejected() {
        EntryBuilder b = new EntryBuilder(ledger, fx, "E2", D).debit(cash, Money.of("100.00", "EUR"))
                .credit(fees, Money.of("95.00", "EUR"));
        assertThrows(UnbalancedEntryException.class, b::post);
        assertEquals(0, ledger.entries().size());
        assertAmount("0", ledger.balance(cash).getFunctional(), "unchanged");
    }

    @Test
    public void wrongCurrencyRejected() {
        EntryBuilder b = new EntryBuilder(ledger, fx, "E3", D).debit(nostro, Money.of("100.00", "EUR"))
                .credit(cash, Money.of("100.00", "EUR"));
        assertThrows(LedgerException.class, b::post);
    }

    @Test
    public void unopenedAccountRejected() {
        Account other = Account.of("9999", "Suspense", AccountType.ASSET, "EUR");
        EntryBuilder b = new EntryBuilder(ledger, fx, "E4", D).debit(other, Money.of("1.00", "EUR"))
                .credit(cash, Money.of("1.00", "EUR"));
        assertThrows(LedgerException.class, b::post);
    }

    @Test
    public void unroundedFunctionalAmountRejected() {
        EntryBuilder b = new EntryBuilder(ledger, fx, "E5", D)
                .line(cash, com.meridian.ledger.core.Side.DEBIT, Money.of("1.005", "EUR"), new BigDecimal("1.005"))
                .line(fees, com.meridian.ledger.core.Side.CREDIT, Money.of("1.005", "EUR"), new BigDecimal("1.005"));
        assertThrows(LedgerException.class, b::post);
    }

    @Test
    public void duplicateAccountRejected() {
        assertThrows(LedgerException.class, () -> ledger.open(Account.of("1000", "Again", AccountType.ASSET, "EUR")));
    }
}

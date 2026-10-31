package com.meridian.ledger;

import com.meridian.ledger.core.Account;
import com.meridian.ledger.core.AccountType;
import com.meridian.ledger.core.EntryBuilder;
import com.meridian.ledger.core.JournalEntry;
import com.meridian.ledger.core.Ledger;
import com.meridian.ledger.core.Side;
import com.meridian.ledger.fx.FxConverter;
import com.meridian.ledger.fx.RateTable;
import com.meridian.ledger.money.Money;
import com.meridian.ledger.reval.RevaluationService;
import com.meridian.ledger.report.TrialBalance;
import testkit.Test;

import java.time.LocalDate;
import java.util.List;

import static testkit.Assert.*;

public class RevaluationTest {
    @Test
    public void simpleGainOnUsdNostro() {
        Ledger ledger = Ledger.inEur();
        Account cash = ledger.open(Account.of("1000", "Cash EUR", AccountType.ASSET, "EUR"));
        Account nostro = ledger.open(Account.of("1010", "Nostro USD", AccountType.ASSET, "USD"));
        Account equity = ledger.open(Account.of("3000", "Retained earnings", AccountType.EQUITY, "USD"));
        Account fxResult = ledger.open(Account.of("7900", "Unrealised FX result", AccountType.INCOME, "EUR"));
        new EntryBuilder(ledger, new FxConverter(new RateTable().put("USD", "EUR", "0.9200")), "B1", LocalDate.of(2025, 1, 10))
                .debit(nostro, Money.of("1000.00", "USD")).credit(cash, Money.of("920.00", "EUR")).post();

        List<JournalEntry> reval = new RevaluationService(ledger, fxResult)
                .revalue(new RateTable().put("USD", "EUR", "0.9300"), LocalDate.of(2025, 1, 31));
        assertEquals(1, reval.size());
        JournalEntry e = reval.get(0);
        assertEquals(Side.DEBIT, e.getPostings().get(0).getSide());
        assertAmount("10.00", e.getPostings().get(0).getFunctionalAmount(), "account leg");
        assertEquals(Side.CREDIT, e.getPostings().get(1).getSide());
        assertAmount("930.00", ledger.balance(nostro).getFunctional(), "revalued");
        assertAmount("1000.00", ledger.balance(nostro).getAmount(), "USD unchanged");
        assertAmount("-10.00", ledger.balance(fxResult).getFunctional(), "FX gain");
        assertAmount("0", ledger.balance(equity).getFunctional(), "non-monetary untouched");
        assertTrue(TrialBalance.of(ledger).isBalanced());
    }

    @Test
    public void nothingToRevalueWhenRateUnchanged() {
        Ledger ledger = Ledger.inEur();
        Account cash = ledger.open(Account.of("1000", "Cash EUR", AccountType.ASSET, "EUR"));
        Account nostro = ledger.open(Account.of("1020", "Nostro GBP", AccountType.ASSET, "GBP"));
        Account fxResult = ledger.open(Account.of("7900", "Unrealised FX result", AccountType.INCOME, "EUR"));
        RateTable r = new RateTable().put("GBP", "EUR", "1.1650");
        new EntryBuilder(ledger, new FxConverter(r), "B1", LocalDate.of(2025, 1, 10))
                .debit(nostro, Money.of("200.00", "GBP")).credit(cash, Money.of("233.00", "EUR")).post();
        assertTrue(new RevaluationService(ledger, fxResult).revalue(r, LocalDate.of(2025, 1, 31)).isEmpty());
    }

    @Test
    public void fxResultAccountMustBeFunctional() {
        Ledger ledger = Ledger.inEur();
        Account usd = ledger.open(Account.of("7901", "FX USD", AccountType.INCOME, "USD"));
        assertThrows(IllegalArgumentException.class, () -> new RevaluationService(ledger, usd));
    }
}

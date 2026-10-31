package com.meridian.ledger;

import com.meridian.ledger.core.Account;
import com.meridian.ledger.core.AccountType;
import com.meridian.ledger.core.EntryBuilder;
import com.meridian.ledger.core.JournalEntry;
import com.meridian.ledger.core.Ledger;
import com.meridian.ledger.core.Posting;
import com.meridian.ledger.core.Side;
import com.meridian.ledger.fx.FxConverter;
import com.meridian.ledger.fx.RateTable;
import com.meridian.ledger.money.Money;
import com.meridian.ledger.reval.RevaluationService;
import com.meridian.ledger.report.TrialBalance;
import testkit.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static testkit.Assert.*;

/** January close for the treasury book, figures agreed with group finance. */
public class RevaluationScenarioTest {
    Ledger ledger = Ledger.inEur();
    Account cash = ledger.open(Account.of("1000", "Cash EUR", AccountType.ASSET, "EUR"));
    Account usd = ledger.open(Account.of("1010", "Nostro USD Citi NY", AccountType.ASSET, "USD"));
    Account jpy = ledger.open(Account.of("1030", "Nostro JPY MUFG", AccountType.ASSET, "JPY"));
    Account deposits = ledger.open(Account.of("2010", "Customer deposits USD", AccountType.LIABILITY, "USD"));
    Account fxResult = ledger.open(Account.of("7900", "Unrealised FX result", AccountType.INCOME, "EUR"));

    void book(String id, int day, String eurUsd, String eurJpy, Account acct, Side side, Money amount) {
        RateTable r = new RateTable().put("EUR", "USD", eurUsd).put("EUR", "JPY", eurJpy);
        FxConverter fx = new FxConverter(r);
        Money eur = fx.convert(amount, ledger.getFunctionalCurrency());
        EntryBuilder b = new EntryBuilder(ledger, fx, id, LocalDate.of(2025, 1, day));
        if (side == Side.DEBIT) b.debit(acct, amount).credit(cash, eur); else b.credit(acct, amount).debit(cash, eur);
        b.post();
    }

    List<JournalEntry> januaryClose() {
        book("B1", 6, "1.0850", "161.20", usd, Side.DEBIT, Money.of("1000000.00", "USD"));
        book("B2", 14, "1.0920", "161.20", usd, Side.DEBIT, Money.of("2500.00", "USD"));
        book("B3", 22, "1.0790", "161.20", usd, Side.CREDIT, Money.of("700.00", "USD"));
        book("B4", 6, "1.0850", "161.20", deposits, Side.CREDIT, Money.of("50000.00", "USD"));
        book("B5", 6, "1.0850", "161.20", jpy, Side.DEBIT, Money.of("1000000", "JPY"));
        RateTable closing = new RateTable().put("EUR", "USD", "1.0700").put("EUR", "JPY", "158.35");
        return new RevaluationService(ledger, fxResult).revalue(closing, LocalDate.of(2025, 1, 31));
    }

    static Posting leg(JournalEntry e, Account a) {
        for (Posting p : e.getPostings()) if (p.getAccount().equals(a)) return p;
        throw new AssertionError("no leg for " + a + " in " + e);
    }

    @Test
    public void bookingUsesExactConversion() {
        januaryClose();
        assertAmount("921658.99", ledger.entries().get(0).getPostings().get(0).getFunctionalAmount(), "B1");
        assertAmount("1001800.00", ledger.balance(usd).getAmount(), "USD nostro");
    }

    @Test
    public void usdNostroRevaluedToClosingRate() {
        List<JournalEntry> reval = januaryClose();
        assertEquals(3, reval.size(), reval.toString());
        JournalEntry e = reval.get(0);
        Posting acct = leg(e, usd), pnl = leg(e, fxResult);
        assertEquals(Side.DEBIT, acct.getSide());
        assertAmount("12962.06", acct.getFunctionalAmount(), "USD revaluation");
        assertEquals(Side.CREDIT, pnl.getSide());
        assertAmount("12962.06", pnl.getFunctionalAmount(), "FX result leg");
        assertAmount("936261.68", ledger.balance(usd).getFunctional(), "USD nostro in EUR");
    }

    @Test
    public void jpyAndLiabilityRevalued() {
        List<JournalEntry> reval = januaryClose();
        Posting j = leg(reval.get(1), jpy);
        assertAmount("111.65", j.getFunctionalAmount(), "JPY gain");
        assertAmount("6315.12", ledger.balance(jpy).getFunctional(), "JPY in EUR");
        Posting d = leg(reval.get(2), deposits);
        assertEquals(Side.CREDIT, d.getSide());
        assertAmount("646.02", d.getFunctionalAmount(), "deposit loss");
        assertEquals(Side.DEBIT, leg(reval.get(2), fxResult).getSide());
        assertAmount("-46728.97", ledger.balance(deposits).getFunctional(), "deposits in EUR");
    }

    @Test
    public void everyEntryBalancesExactlyAndTrialBalanceTies() {
        januaryClose();
        for (JournalEntry e : ledger.entries()) {
            assertEquals(0, e.functionalDebits().compareTo(e.functionalCredits()), "entry " + e);
        }
        TrialBalance tb = TrialBalance.of(ledger);
        assertAmount(tb.getTotalDebits().toPlainString(), tb.getTotalCredits(), "trial balance");
        assertAmount("12427.69", ledger.balance(fxResult).getFunctional().negate(), "net FX result");
    }

    @Test
    public void residualFunctionalBalanceIsClearedWhenAccountIsFlat() {
        book("B1", 6, "1.0850", "161.20", usd, Side.DEBIT, Money.of("1000.00", "USD"));
        book("B2", 20, "1.0700", "161.20", usd, Side.CREDIT, Money.of("1000.00", "USD"));
        BigDecimal carried = ledger.balance(usd).getFunctional();
        assertTrue(carried.signum() != 0, "precondition: residual EUR value " + carried);
        List<JournalEntry> reval = new RevaluationService(ledger, fxResult)
                .revalue(new RateTable().put("EUR", "USD", "1.0700"), LocalDate.of(2025, 1, 31));
        assertEquals(1, reval.size(), reval.toString());
        assertAmount("0", ledger.balance(usd).getFunctional(), "cleared");
        assertTrue(TrialBalance.of(ledger).isBalanced());
    }
}

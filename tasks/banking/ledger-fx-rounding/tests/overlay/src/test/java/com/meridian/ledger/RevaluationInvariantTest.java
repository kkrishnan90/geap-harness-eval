package com.meridian.ledger;

import com.meridian.ledger.core.Account;
import com.meridian.ledger.core.AccountBalance;
import com.meridian.ledger.core.AccountType;
import com.meridian.ledger.core.EntryBuilder;
import com.meridian.ledger.core.JournalEntry;
import com.meridian.ledger.core.Ledger;
import com.meridian.ledger.core.Posting;
import com.meridian.ledger.fx.FxConverter;
import com.meridian.ledger.fx.RateTable;
import com.meridian.ledger.money.Money;
import com.meridian.ledger.money.Rounding;
import com.meridian.ledger.reval.RevaluationService;
import com.meridian.ledger.report.TrialBalance;
import testkit.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Currency;
import java.util.List;
import java.util.Random;

import static testkit.Assert.*;

/** Three months of randomised (but seeded, hence deterministic) treasury activity. */
public class RevaluationInvariantTest {
    static final String[] CCYS = {"USD", "GBP", "JPY", "CHF", "KWD", "USD"};
    static final double[] MID = {1.08, 0.85, 160.0, 0.95, 0.33, 1.08}; // units per EUR

    static String rate(Random rnd, int i) {
        double v = MID[i] * (0.95 + 0.1 * rnd.nextDouble());
        int decimals = 4 + rnd.nextInt(3);
        return new BigDecimal(v).setScale(decimals, java.math.RoundingMode.DOWN).toPlainString();
    }

    /** Randomly quote either EUR/XXX or XXX/EUR (treasury does both for some desks). */
    static void quote(RateTable t, Random rnd, int i, java.util.Map<String, String[]> record) {
        String r = rate(rnd, i);
        if (rnd.nextBoolean()) {
            t.put("EUR", CCYS[i], r);
            record.put(CCYS[i], new String[] {"reverse", r});
        } else {
            String inv = BigDecimal.ONE.divide(new BigDecimal(r), 6, java.math.RoundingMode.DOWN).toPlainString();
            t.put(CCYS[i], "EUR", inv);
            record.put(CCYS[i], new String[] {"direct", inv});
        }
    }

    static Money randomAmount(Random rnd, String ccy) {
        int fd = Rounding.minorUnits(Currency.getInstance(ccy));
        long minor = 1 + (long) (rnd.nextDouble() * Math.pow(10, 5 + rnd.nextInt(4)));
        return Money.of(BigDecimal.valueOf(minor, fd), Currency.getInstance(ccy));
    }

    /** Independent reference: exact multiply by a direct quote, exact division by a reverse quote, half-even. */
    static BigDecimal toEur(BigDecimal amount, String ccy, java.util.Map<String, String[]> quotes) {
        String[] q = quotes.get(ccy);
        BigDecimal r = new BigDecimal(q[1]);
        BigDecimal v = q[0].equals("direct") ? amount.multiply(r) : amount.divide(r, java.math.MathContext.DECIMAL128);
        return v.setScale(2, java.math.RoundingMode.HALF_EVEN);
    }

    @Test(timeoutMillis = 60_000)
    public void trialBalanceTiesAfterEveryClose() {
        Random rnd = new Random(20250131L);
        Ledger ledger = Ledger.inEur();
        Account cash = ledger.open(Account.of("1000", "Cash EUR", AccountType.ASSET, "EUR"));
        List<Account> fxAccounts = new ArrayList<>();
        for (int i = 0; i < CCYS.length; i++) {
            AccountType type = i == CCYS.length - 1 ? AccountType.LIABILITY : AccountType.ASSET;
            fxAccounts.add(ledger.open(Account.of("1" + (100 + i), "FX " + CCYS[i] + " " + i, type, CCYS[i])));
        }
        Account fxResult = ledger.open(Account.of("7900", "Unrealised FX result", AccountType.INCOME, "EUR"));
        RevaluationService reval = new RevaluationService(ledger, fxResult);

        int revaluationEntries = 0;
        for (int month = 1; month <= 3; month++) {
            for (int n = 0; n < 150; n++) {
                int i = rnd.nextInt(CCYS.length);
                RateTable booking = new RateTable();
                java.util.Map<String, String[]> bq = new java.util.HashMap<>();
                quote(booking, rnd, i, bq);
                FxConverter fx = new FxConverter(booking);
                Account acct = fxAccounts.get(i);
                Money amt = randomAmount(rnd, CCYS[i]);
                Money eur = fx.convert(amt, ledger.getFunctionalCurrency());
                assertAmount(toEur(amt.getAmount(), CCYS[i], bq).toPlainString(), eur.getAmount(), "booking conversion " + amt);
                EntryBuilder b = new EntryBuilder(ledger, fx, "M" + month + "-" + n, LocalDate.of(2025, month, 1 + n % 28));
                boolean inflow = rnd.nextInt(10) < 6;
                if (acct.getType() == AccountType.LIABILITY) inflow = !inflow;
                if (inflow) b.debit(acct, amt).credit(cash, eur); else b.credit(acct, amt).debit(cash, eur);
                b.post();
            }
            RateTable closing = new RateTable();
            java.util.Map<String, String[]> cq = new java.util.HashMap<>();
            for (int i = 0; i < CCYS.length; i++) if (i != CCYS.length - 1) quote(closing, rnd, i, cq);
            LocalDate close = LocalDate.of(2025, month, 28);
            revaluationEntries += reval.revalue(closing, close).size();

            for (JournalEntry e : ledger.entries()) {
                assertEquals(0, e.functionalDebits().compareTo(e.functionalCredits()), "unbalanced " + e);
            }
            TrialBalance tb = TrialBalance.of(ledger);
            assertAmount(tb.getTotalDebits().toPlainString(), tb.getTotalCredits(), "trial balance month " + month);
            BigDecimal sum = BigDecimal.ZERO;
            for (AccountBalance ab : ledger.balances()) sum = sum.add(ab.getFunctional());
            assertAmount("0", sum, "sum of functional balances month " + month);

            for (Account a : fxAccounts) {
                AccountBalance ab = ledger.balance(a);
                BigDecimal expected = toEur(ab.getAmount(), a.getCurrency().getCurrencyCode(), cq);
                assertAmount(expected.toPlainString(), ab.getFunctional(), "carried value of " + a);
            }
            for (JournalEntry e : ledger.entries()) {
                for (Posting p : e.getPostings()) {
                    assertTrue(p.getFunctionalAmount().stripTrailingZeros().scale() <= 2, "unrounded " + p);
                }
            }
        }
        assertTrue(revaluationEntries >= 12, "expected revaluation activity, got " + revaluationEntries);
    }
}

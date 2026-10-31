package com.meridian.ledger;

import com.meridian.ledger.coa.ChartOfAccountsLoader;
import com.meridian.ledger.core.Account;
import com.meridian.ledger.core.AccountType;
import com.meridian.ledger.core.EntryBuilder;
import com.meridian.ledger.core.Ledger;
import com.meridian.ledger.fx.FxConverter;
import com.meridian.ledger.fx.RateTable;
import com.meridian.ledger.money.Money;
import com.meridian.ledger.report.StatementFormatter;
import com.meridian.ledger.report.TrialBalance;
import testkit.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.List;

import static testkit.Assert.*;

public class ReportingTest {
    static Ledger chart() throws Exception {
        Ledger l = Ledger.inEur();
        new ChartOfAccountsLoader().openAll(l, Files.readString(Path.of("src/test/resources/chart-of-accounts.csv")));
        return l;
    }

    @Test
    public void loadsChartOfAccounts() throws Exception {
        Ledger l = chart();
        assertEquals(11, l.accounts().size());
        assertEquals("JPY", l.account("1030").getCurrency().getCurrencyCode());
        assertEquals(AccountType.LIABILITY, l.account("2010").getType());
    }

    @Test
    public void chartRejectsBadLines() {
        ChartOfAccountsLoader c = new ChartOfAccountsLoader();
        assertThrows(IllegalArgumentException.class, () -> c.parse("1;Cash;ASSET"));
        assertThrows(IllegalArgumentException.class, () -> c.parse("1;Cash;ASSETS;EUR"));
        assertThrows(IllegalArgumentException.class, () -> c.parse("1;Cash;ASSET;XYZ"));
        List<Account> ok = c.parse("# comment\n\n 1 ; Cash ; asset ; EUR \n");
        assertEquals("Cash", ok.get(0).getName());
    }

    @Test
    public void trialBalanceColumns() throws Exception {
        Ledger l = chart();
        FxConverter fx = new FxConverter(new RateTable().put("EUR", "USD", "1.0850"));
        new EntryBuilder(l, fx, "FEE-1", LocalDate.of(2025, 2, 3)).debit(l.account("1000"), Money.of("150.00", "EUR"))
                .credit(l.account("4000"), Money.of("150.00", "EUR")).post();
        new EntryBuilder(l, fx, "FEE-2", LocalDate.of(2025, 2, 4)).debit(l.account("6100"), Money.of("20.00", "EUR"))
                .credit(l.account("1000"), Money.of("20.00", "EUR")).post();
        TrialBalance tb = TrialBalance.of(l);
        assertEquals(3, tb.getRows().size());
        assertAmount("150.00", tb.getTotalDebits(), "debits");
        assertAmount("150.00", tb.getTotalCredits(), "credits");
        assertTrue(tb.isBalanced());
    }

    @Test
    public void statementRunningBalance() throws Exception {
        Ledger l = chart();
        FxConverter fx = new FxConverter(new RateTable());
        new EntryBuilder(l, fx, "FEE-1", LocalDate.of(2025, 2, 3)).debit(l.account("1000"), Money.of("150.00", "EUR"))
                .credit(l.account("4000"), Money.of("150.00", "EUR")).post();
        new EntryBuilder(l, fx, "FEE-2", LocalDate.of(2025, 2, 4)).debit(l.account("6100"), Money.of("20.00", "EUR"))
                .credit(l.account("1000"), Money.of("20.00", "EUR")).post();
        String s = new StatementFormatter().format(l, l.account("1000"));
        assertTrue(s.startsWith("Statement 1000 Cash EUR (EUR)"), s);
        assertTrue(s.contains("FEE-2") && s.contains("-20.00") && s.contains("130.00"), s);
    }
}

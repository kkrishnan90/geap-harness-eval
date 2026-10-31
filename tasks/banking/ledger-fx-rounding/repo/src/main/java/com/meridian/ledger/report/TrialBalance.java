package com.meridian.ledger.report;

import com.meridian.ledger.core.AccountBalance;
import com.meridian.ledger.core.Ledger;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Functional-currency trial balance: debit-balance accounts vs credit-balance accounts. */
public final class TrialBalance {
    public static final class Row {
        public final String accountCode;
        public final String accountName;
        public final BigDecimal debit;
        public final BigDecimal credit;

        Row(String code, String name, BigDecimal debit, BigDecimal credit) {
            this.accountCode = code;
            this.accountName = name;
            this.debit = debit;
            this.credit = credit;
        }
    }

    private final List<Row> rows;
    private final BigDecimal totalDebits;
    private final BigDecimal totalCredits;

    private TrialBalance(List<Row> rows, BigDecimal d, BigDecimal c) {
        this.rows = rows;
        this.totalDebits = d;
        this.totalCredits = c;
    }

    public static TrialBalance of(Ledger ledger) {
        List<Row> rows = new ArrayList<>();
        BigDecimal d = BigDecimal.ZERO, c = BigDecimal.ZERO;
        for (AccountBalance b : ledger.balances()) {
            BigDecimal f = b.getFunctional();
            if (f.signum() == 0) continue;
            if (f.signum() > 0) {
                rows.add(new Row(b.getAccount().getCode(), b.getAccount().getName(), f, BigDecimal.ZERO));
                d = d.add(f);
            } else {
                rows.add(new Row(b.getAccount().getCode(), b.getAccount().getName(), BigDecimal.ZERO, f.negate()));
                c = c.add(f.negate());
            }
        }
        return new TrialBalance(Collections.unmodifiableList(rows), d, c);
    }

    public List<Row> getRows() { return rows; }
    public BigDecimal getTotalDebits() { return totalDebits; }
    public BigDecimal getTotalCredits() { return totalCredits; }
    public boolean isBalanced() { return totalDebits.compareTo(totalCredits) == 0; }
}

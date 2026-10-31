package com.meridian.ledger.report;

import com.meridian.ledger.core.Account;
import com.meridian.ledger.core.JournalEntry;
import com.meridian.ledger.core.Ledger;
import com.meridian.ledger.core.Posting;

import java.math.BigDecimal;
import java.util.Locale;

/** Plain-text account statement used by the reconciliation team (fixed-width, 72 columns). */
public final class StatementFormatter {
    public String format(Ledger ledger, Account account) {
        StringBuilder sb = new StringBuilder();
        sb.append(String.format(Locale.ROOT, "Statement %s %s (%s)%n", account.getCode(), account.getName(),
                account.getCurrency().getCurrencyCode()));
        BigDecimal running = BigDecimal.ZERO;
        for (JournalEntry e : ledger.entries()) {
            for (Posting p : e.getPostings()) {
                if (!p.getAccount().equals(account)) continue;
                running = running.add(p.signedAmount());
                sb.append(String.format(Locale.ROOT, "%-10s %-24.24s %14s %14s%n", e.getDate(), e.getId(),
                        p.signedAmount().toPlainString(), running.toPlainString()));
            }
        }
        sb.append(String.format(Locale.ROOT, "%-35s %29s%n", "Closing balance", running.toPlainString()));
        return sb.toString();
    }
}

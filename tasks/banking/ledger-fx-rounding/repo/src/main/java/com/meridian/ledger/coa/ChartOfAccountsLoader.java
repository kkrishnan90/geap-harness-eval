package com.meridian.ledger.coa;

import com.meridian.ledger.core.Account;
import com.meridian.ledger.core.AccountType;
import com.meridian.ledger.core.Ledger;

import java.util.ArrayList;
import java.util.Currency;
import java.util.List;

/**
 * Loads the chart of accounts from the finance-ops CSV export:
 * {@code code;name;type;currency}, '#' comments, blank lines ignored.
 */
public final class ChartOfAccountsLoader {
    public List<Account> parse(String csv) {
        List<Account> out = new ArrayList<>();
        int lineNo = 0;
        for (String raw : csv.split("\\R")) {
            lineNo++;
            String line = raw.strip();
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] f = line.split(";", -1);
            if (f.length != 4) throw new IllegalArgumentException("line " + lineNo + ": expected 4 fields");
            AccountType type;
            try {
                type = AccountType.valueOf(f[2].strip().toUpperCase());
            } catch (IllegalArgumentException e) {
                throw new IllegalArgumentException("line " + lineNo + ": unknown type " + f[2]);
            }
            Currency ccy;
            try {
                ccy = Currency.getInstance(f[3].strip());
            } catch (IllegalArgumentException e) {
                throw new IllegalArgumentException("line " + lineNo + ": unknown currency " + f[3]);
            }
            out.add(new Account(f[0].strip(), f[1].strip(), type, ccy));
        }
        return out;
    }

    public void openAll(Ledger ledger, String csv) {
        for (Account a : parse(csv)) ledger.open(a);
    }
}

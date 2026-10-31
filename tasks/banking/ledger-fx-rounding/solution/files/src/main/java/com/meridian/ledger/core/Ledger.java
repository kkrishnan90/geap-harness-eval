package com.meridian.ledger.core;

import com.meridian.ledger.money.Rounding;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.Currency;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Double-entry general ledger kept in one functional currency. Every accepted entry has
 * equal debit and credit totals in functional currency, so the trial balance always balances.
 */
public final class Ledger {
    private final Currency functionalCurrency;
    private final Map<String, Account> accounts = new LinkedHashMap<>();
    private final List<JournalEntry> entries = new ArrayList<>();
    private final Map<String, BigDecimal[]> balances = new HashMap<>();

    public Ledger(Currency functionalCurrency) { this.functionalCurrency = functionalCurrency; }

    public static Ledger inEur() { return new Ledger(Currency.getInstance("EUR")); }

    public Currency getFunctionalCurrency() { return functionalCurrency; }

    public Account open(Account account) {
        if (accounts.putIfAbsent(account.getCode(), account) != null) {
            throw new LedgerException("account already open: " + account.getCode());
        }
        balances.put(account.getCode(), new BigDecimal[] {BigDecimal.ZERO, BigDecimal.ZERO});
        return account;
    }

    public Account account(String code) {
        Account a = accounts.get(code);
        if (a == null) throw new LedgerException("unknown account " + code);
        return a;
    }

    public Collection<Account> accounts() { return Collections.unmodifiableCollection(accounts.values()); }

    public List<JournalEntry> entries() { return Collections.unmodifiableList(entries); }

    public void post(JournalEntry entry) {
        if (entry.getPostings().size() < 2) throw new LedgerException(entry.getId() + ": needs at least two postings");
        int fd = Rounding.minorUnits(functionalCurrency);
        for (Posting p : entry.getPostings()) {
            if (!accounts.containsKey(p.getAccount().getCode())) {
                throw new LedgerException(entry.getId() + ": account not open " + p.getAccount().getCode());
            }
            if (!p.getAmount().getCurrency().equals(p.getAccount().getCurrency())) {
                throw new LedgerException(entry.getId() + ": " + p.getAmount().getCurrency()
                        + " posting on " + p.getAccount().getCurrency() + " account " + p.getAccount().getCode());
            }
            if (p.getAmount().signum() < 0 || p.getFunctionalAmount().signum() < 0) {
                throw new LedgerException(entry.getId() + ": negative amount on " + p.getAccount().getCode());
            }
            if (p.getFunctionalAmount().stripTrailingZeros().scale() > fd) {
                throw new LedgerException(entry.getId() + ": functional amount not rounded " + p.getFunctionalAmount());
            }
        }
        BigDecimal diff = entry.functionalDebits().subtract(entry.functionalCredits());
        if (diff.signum() != 0) {
            throw new UnbalancedEntryException(entry.getId() + ": debits - credits = " + diff.toPlainString());
        }
        for (Posting p : entry.getPostings()) {
            BigDecimal[] b = balances.get(p.getAccount().getCode());
            b[0] = b[0].add(p.signedAmount());
            b[1] = b[1].add(p.signedFunctional());
        }
        entries.add(entry);
    }

    public AccountBalance balance(Account account) {
        BigDecimal[] b = balances.get(account.getCode());
        if (b == null) throw new LedgerException("unknown account " + account.getCode());
        return new AccountBalance(account, b[0], b[1]);
    }

    public List<AccountBalance> balances() {
        List<AccountBalance> out = new ArrayList<>();
        for (Account a : accounts.values()) out.add(balance(a));
        return out;
    }
}

package com.meridian.ledger.core;

import com.meridian.ledger.fx.FxConverter;
import com.meridian.ledger.money.Money;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

/**
 * Builds journal entries whose functional amounts are derived from booking-date rates.
 * Lines on functional-currency accounts carry their own amount as functional amount.
 */
public final class EntryBuilder {
    private final Ledger ledger;
    private final FxConverter converter;
    private final String id;
    private final LocalDate date;
    private String description = "";
    private final List<Posting> postings = new ArrayList<>();

    public EntryBuilder(Ledger ledger, FxConverter converter, String id, LocalDate date) {
        this.ledger = ledger;
        this.converter = converter;
        this.id = id;
        this.date = date;
    }

    public EntryBuilder description(String d) { this.description = d; return this; }

    public EntryBuilder debit(Account account, Money amount) { return line(account, Side.DEBIT, amount); }

    public EntryBuilder credit(Account account, Money amount) { return line(account, Side.CREDIT, amount); }

    /** A line with an explicit functional amount (e.g. settlement at a contracted rate). */
    public EntryBuilder line(Account account, Side side, Money amount, BigDecimal functional) {
        postings.add(new Posting(account, side, amount, functional));
        return this;
    }

    private EntryBuilder line(Account account, Side side, Money amount) {
        Money functional = converter.convert(amount, ledger.getFunctionalCurrency());
        postings.add(new Posting(account, side, amount, functional.getAmount()));
        return this;
    }

    public JournalEntry build() { return new JournalEntry(id, date, description, postings); }

    public JournalEntry post() {
        JournalEntry e = build();
        ledger.post(e);
        return e;
    }
}

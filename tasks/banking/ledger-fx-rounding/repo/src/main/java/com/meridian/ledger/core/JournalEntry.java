package com.meridian.ledger.core;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Objects;

public final class JournalEntry {
    private final String id;
    private final LocalDate date;
    private final String description;
    private final List<Posting> postings;

    public JournalEntry(String id, LocalDate date, String description, List<Posting> postings) {
        this.id = Objects.requireNonNull(id);
        this.date = Objects.requireNonNull(date);
        this.description = description == null ? "" : description;
        this.postings = List.copyOf(postings);
    }

    public String getId() { return id; }
    public LocalDate getDate() { return date; }
    public String getDescription() { return description; }
    public List<Posting> getPostings() { return postings; }

    public BigDecimal functionalDebits() {
        BigDecimal s = BigDecimal.ZERO;
        for (Posting p : postings) if (p.getSide() == Side.DEBIT) s = s.add(p.getFunctionalAmount());
        return s;
    }

    public BigDecimal functionalCredits() {
        BigDecimal s = BigDecimal.ZERO;
        for (Posting p : postings) if (p.getSide() == Side.CREDIT) s = s.add(p.getFunctionalAmount());
        return s;
    }

    @Override
    public String toString() { return "JournalEntry{" + id + " " + date + " " + postings + "}"; }
}

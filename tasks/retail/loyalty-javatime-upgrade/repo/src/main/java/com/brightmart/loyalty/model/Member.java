package com.brightmart.loyalty.model;

import java.util.Date;
import java.util.Objects;

/** A BrightMart Rewards member. */
public final class Member {
    private final String memberId;
    private final Date enrolledAt;

    public Member(String memberId, Date enrolledAt) {
        this.memberId = Objects.requireNonNull(memberId, "memberId");
        this.enrolledAt = new Date(Objects.requireNonNull(enrolledAt, "enrolledAt").getTime());
    }

    public String memberId() { return memberId; }

    public Date enrolledAt() { return new Date(enrolledAt.getTime()); }
}

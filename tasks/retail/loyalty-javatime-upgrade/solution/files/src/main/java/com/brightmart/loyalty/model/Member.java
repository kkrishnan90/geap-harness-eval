package com.brightmart.loyalty.model;

import java.time.LocalDate;
import java.time.ZoneId;
import java.util.Objects;

/** A BrightMart Rewards member. */
public final class Member {
    private final String memberId;
    private final LocalDate enrolledOn;
    private final ZoneId homeZone;

    public Member(String memberId, LocalDate enrolledOn, ZoneId homeZone) {
        this.memberId = Objects.requireNonNull(memberId, "memberId");
        this.enrolledOn = Objects.requireNonNull(enrolledOn, "enrolledOn");
        this.homeZone = Objects.requireNonNull(homeZone, "homeZone");
    }

    public String memberId() { return memberId; }

    public LocalDate enrolledOn() { return enrolledOn; }

    public ZoneId homeZone() { return homeZone; }
}

package com.meridianre.policy.model;

import java.io.Serializable;
import java.math.BigDecimal;
import java.util.Objects;

/** One insured peril with limit and deductible (amounts in policy currency). */
public final class Coverage implements Serializable {
    private static final long serialVersionUID = 7L;

    private final String code;
    private final BigDecimal limit;
    private final BigDecimal deductible;
    private final BigDecimal rate;   // premium rate per unit of limit

    public Coverage(String code, BigDecimal limit, BigDecimal deductible, BigDecimal rate) {
        this.code = code;
        this.limit = limit;
        this.deductible = deductible;
        this.rate = rate;
    }

    public String code() { return code; }
    public BigDecimal limit() { return limit; }
    public BigDecimal deductible() { return deductible; }
    public BigDecimal rate() { return rate; }

    @Override public boolean equals(Object o) {
        return o instanceof Coverage c && code.equals(c.code) && limit.compareTo(c.limit) == 0
                && deductible.compareTo(c.deductible) == 0 && rate.compareTo(c.rate) == 0;
    }
    @Override public int hashCode() { return Objects.hash(code, limit.stripTrailingZeros(), deductible.stripTrailingZeros()); }
    @Override public String toString() { return "Coverage[" + code + " " + limit + "]"; }
}

package com.harborline.motor;

import static testkit.Assert.*;

import com.harborline.motor.rating.PremiumBreakdown;
import com.harborline.motor.rating.PremiumCalculator;
import com.harborline.motor.rating.RatingRequest;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import testkit.Test;

public class PremiumRoundingPolicyTest {
    private static BigDecimal d(String s) { return new BigDecimal(s); }

    private final PremiumCalculator calc = new PremiumCalculator();

    private PremiumBreakdown rate(String base, List<String> factors, String min, String region, int n) {
        List<BigDecimal> fs = new ArrayList<>();
        for (String f : factors) fs.add(d(f));
        return calc.calculate(new RatingRequest(d(base), fs, d(min), region, n));
    }

    private static BigDecimal sum(List<BigDecimal> xs) {
        BigDecimal s = BigDecimal.ZERO;
        for (BigDecimal x : xs) s = s.add(x);
        return s;
    }

    @Test
    public void netRoundedOnceNotPerFactor() {
        PremiumBreakdown b = rate("333.33", List.of("1.15", "1.07", "1.333"), "150.00", "GB", 1);
        assertAmount("546.75", b.netPremium(), "net");
        PremiumBreakdown c = rate("412.17", List.of("1.15", "1.07", "1.333"), "150.00", "GB", 1);
        assertAmount("676.06", c.netPremium(), "net");
    }

    @Test
    public void netUsesBankersRounding() {
        PremiumBreakdown b = rate("200.25", List.of("0.5"), "50.00", "GB", 1);
        assertAmount("100.12", b.netPremium(), "net 100.125");
        assertAmount("12.01", b.tax(), "tax");
        assertAmount("112.13", b.grossPremium(), "gross");
    }

    @Test
    public void taxUsesBankersRounding() {
        PremiumBreakdown b = rate("249.50", List.of(), "150.00", "IE", 1);
        assertAmount("7.48", b.tax(), "tax 7.485");
        assertAmount("256.98", b.grossPremium(), "gross");
    }

    @Test
    public void taxComputedOnRoundedNet() {
        PremiumBreakdown b = rate("300.04", List.of("1.0625"), "150.00", "GB", 1);
        assertAmount("318.79", b.netPremium(), "net");
        assertAmount("38.25", b.tax(), "tax");
        assertAmount("357.04", b.grossPremium(), "gross");
    }

    @Test
    public void taxComputedOnMinimumPremium() {
        PremiumBreakdown b = rate("100.00", List.of("0.5"), "150.00", "GB", 1);
        assertAmount("150.00", b.netPremium(), "net");
        assertAmount("18.00", b.tax(), "tax");
        assertAmount("168.00", b.grossPremium(), "gross");
    }

    @Test
    public void thirdsPutRemainderOnFirstInstalment() {
        assertEquals(List.of(d("33.34"), d("33.33"), d("33.33")), PremiumCalculator.split(d("100.00"), 3));
    }

    @Test
    public void instalmentsRoundDownNotNearest() {
        List<BigDecimal> six = PremiumCalculator.split(d("100.00"), 6);
        assertEquals(List.of(d("16.70"), d("16.66"), d("16.66"), d("16.66"), d("16.66"), d("16.66")), six);
        List<BigDecimal> seven = PremiumCalculator.split(d("1000.00"), 7);
        assertAmount("142.90", seven.get(0), "first");
        for (int i = 1; i < 7; i++) assertAmount("142.85", seven.get(i), "instalment " + i);
    }

    @Test
    public void monthlyPlanSumsToGross() {
        PremiumBreakdown b = rate("540.01", List.of(), "150.00", "GB", 12);
        assertAmount("604.81", b.grossPremium(), "gross");
        assertEquals(12, b.instalments().size());
        assertAmount("50.41", b.instalments().get(0), "first");
        assertAmount("50.40", b.instalments().get(11), "last");
        assertAmount("604.81", sum(b.instalments()), "sum");
    }

    @Test
    public void randomisedPortfolioInvariants() {
        Random rnd = new Random(20260301L);
        String[] regions = {"GB", "IE", "IM", "GB-JSY"};
        for (int i = 0; i < 2000; i++) {
            BigDecimal base = BigDecimal.valueOf(5000 + rnd.nextInt(150000), 2);
            List<BigDecimal> fs = new ArrayList<>();
            int nf = rnd.nextInt(5);
            for (int k = 0; k < nf; k++) fs.add(BigDecimal.valueOf(500 + rnd.nextInt(1500), 3));
            String region = regions[rnd.nextInt(regions.length)];
            int n = 1 + rnd.nextInt(12);
            BigDecimal min = d("150.00");
            PremiumBreakdown b = calc.calculate(new RatingRequest(base, fs, min, region, n));

            BigDecimal net = base;
            for (BigDecimal f : fs) net = net.multiply(f);
            net = net.setScale(2, RoundingMode.HALF_EVEN);
            if (net.compareTo(min) < 0) net = min;
            BigDecimal rate = region.equals("IE") ? d("0.03") : region.equals("GB-JSY") ? d("0.00") : d("0.12");
            BigDecimal tax = net.multiply(rate).setScale(2, RoundingMode.HALF_EVEN);
            String ctx = "case " + i + " base=" + base + " factors=" + fs + " region=" + region + " n=" + n;
            assertAmount(net.toPlainString(), b.netPremium(), ctx + " net");
            assertAmount(tax.toPlainString(), b.tax(), ctx + " tax");
            assertAmount(net.add(tax).toPlainString(), b.grossPremium(), ctx + " gross");
            assertEquals(n, b.instalments().size(), ctx);
            assertAmount(b.grossPremium().toPlainString(), sum(b.instalments()), ctx + " instalment sum");
            BigDecimal last = b.instalments().get(n - 1);
            for (int k = 1; k < n; k++) assertAmount(last.toPlainString(), b.instalments().get(k), ctx + " equal tail");
            BigDecimal diff = b.instalments().get(0).subtract(last);
            assertTrue(diff.signum() >= 0 && diff.compareTo(BigDecimal.valueOf(n - 1, 2)) <= 0, ctx + " first instalment excess " + diff);
        }
    }
}

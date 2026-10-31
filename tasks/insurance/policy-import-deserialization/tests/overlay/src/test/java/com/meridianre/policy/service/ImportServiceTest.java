package com.meridianre.policy.service;

import com.meridianre.policy.io.PolicyExporter;
import com.meridianre.policy.io.PolicyImporter;
import com.meridianre.policy.repo.PolicyRepository;
import com.meridianre.policy.model.Coverage;
import com.meridianre.policy.model.LineOfBusiness;
import com.meridianre.policy.model.Party;
import com.meridianre.policy.model.Policy;
import com.meridianre.policy.model.PolicyBatch;
import com.meridianre.policy.model.PolicyStatus;
import testkit.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import static testkit.Assert.*;

public class ImportServiceTest {
    static Policy policy(String number, LineOfBusiness line, PolicyStatus status) {
        Party holder = new Party("P-" + number, "Holder of " + number, "DE");
        return new Policy(number, line, holder, LocalDate.of(2026, 1, 1), LocalDate.of(2027, 1, 1), "EUR", status,
                List.of(new Coverage("FIRE", new BigDecimal("1000000.00"), new BigDecimal("5000.00"), new BigDecimal("0.0012")),
                        new Coverage("FLOOD", new BigDecimal("250000.00"), new BigDecimal("10000.00"), new BigDecimal("0.0040"))));
    }

    static PolicyBatch batch(int n) {
        List<Policy> list = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            list.add(policy(String.format("PR-2026-%06d", i + 1), LineOfBusiness.PROPERTY, PolicyStatus.BOUND));
        }
        return new PolicyBatch("B-20260301-01", "PAS-LEGACY", list);
    }

    private static ImportService service(PolicyRepository repo) {
        return new ImportService(new PolicyImporter(), new PolicyValidator(), repo);
    }

    @Test
    public void validBatchImported() {
        PolicyRepository repo = new PolicyRepository();
        ImportReport r = service(repo).upload("broker-17", new PolicyExporter().export(batch(5)));
        assertTrue(r.accepted());
        assertEquals(5, r.imported());
        assertEquals(5, repo.size());
        assertTrue(repo.find("PR-2026-000003").isPresent());
    }

    @Test
    public void invalidPoliciesReportedNotStored() {
        PolicyRepository repo = new PolicyRepository();
        List<Policy> list = new ArrayList<>(batch(2).policies());
        list.add(new Policy("bad", LineOfBusiness.MOTOR, new Party("X", "Y", "FR"), LocalDate.of(2026, 5, 1),
                LocalDate.of(2026, 4, 1), "JPY", PolicyStatus.QUOTED, List.of()));
        ImportReport r = service(repo).upload("broker-17", new PolicyExporter().export(new PolicyBatch("B2", "PAS", list)));
        assertTrue(r.accepted());
        assertEquals(2, r.imported());
        assertEquals(4, r.rejected().get("bad").size());
        assertEquals(2, repo.size());
    }

    @Test
    public void unreadableUploadFailsCleanly() {
        PolicyRepository repo = new PolicyRepository();
        ImportService s = service(repo);
        ImportReport r = s.upload("broker-9", new byte[] {1, 2, 3});
        assertFalse(r.accepted());
        assertEquals(0, repo.size());
        assertTrue(s.auditLog().get(0).startsWith("broker-9 REJECTED"));
    }

    @Test
    public void validatorChecksCoverages() {
        Policy p = new Policy("PR-2026-000001", LineOfBusiness.PROPERTY, new Party("1", "A", "DE"),
                LocalDate.of(2026, 1, 1), LocalDate.of(2027, 1, 1), "EUR", PolicyStatus.BOUND,
                List.of(new Coverage("FIRE", new BigDecimal("100"), new BigDecimal("100"), new BigDecimal("1.5"))));
        assertEquals(List.of("FIRE: deductible out of range", "FIRE: rate out of range"), new PolicyValidator().validate(p));
    }
}

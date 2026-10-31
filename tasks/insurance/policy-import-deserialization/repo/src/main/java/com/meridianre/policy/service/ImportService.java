package com.meridianre.policy.service;

import com.meridianre.policy.io.ImportException;
import com.meridianre.policy.io.PolicyImporter;
import com.meridianre.policy.model.Policy;
import com.meridianre.policy.model.PolicyBatch;
import com.meridianre.policy.repo.PolicyRepository;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Broker portal "legacy batch upload" use case. */
public final class ImportService {
    private final PolicyImporter importer;
    private final PolicyValidator validator;
    private final PolicyRepository repository;
    private final List<String> auditLog = new ArrayList<>();

    public ImportService(PolicyImporter importer, PolicyValidator validator, PolicyRepository repository) {
        this.importer = importer;
        this.validator = validator;
        this.repository = repository;
    }

    public ImportReport upload(String broker, byte[] blob) {
        PolicyBatch batch;
        try {
            batch = importer.read(blob);
        } catch (ImportException e) {
            audit(broker, "REJECTED " + e.getMessage());
            return ImportReport.failed(e.getMessage());
        }
        Map<String, List<String>> rejected = new LinkedHashMap<>();
        List<Policy> ok = new ArrayList<>();
        for (Policy p : batch.policies()) {
            List<String> problems = validator.validate(p);
            if (problems.isEmpty()) ok.add(p);
            else rejected.put(p.policyNumber(), problems);
        }
        ok.forEach(repository::upsert);
        audit(broker, "IMPORTED " + batch.batchId() + " ok=" + ok.size() + " rejected=" + rejected.size());
        return new ImportReport(true, batch.batchId(), ok.size(), rejected, null);
    }

    private synchronized void audit(String broker, String what) { auditLog.add(broker + " " + what); }

    public synchronized List<String> auditLog() { return List.copyOf(auditLog); }
}

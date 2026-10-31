"""Data steward work-list summary."""

from collections import Counter


def worklist_summary(records, groups):
    by_id = {r.record_id: r for r in records}
    multi = [g for g in groups if len(g) > 1]
    cross_source = sum(1 for g in multi if len({by_id[i].source for i in g}) > 1)
    sizes = Counter(len(g) for g in multi)
    return {
        "records": len(records),
        "candidate_groups": len(multi),
        "records_in_groups": sum(len(g) for g in multi),
        "cross_source_groups": cross_source,
        "group_sizes": dict(sorted(sizes.items())),
    }

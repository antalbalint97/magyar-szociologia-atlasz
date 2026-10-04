"""Person-mention resolution diagnostics (#5): what resolved, how, and where.

A single resolution rate hides the bias that matters for network analysis: sites with
richer markup resolve more mentions, which shows up later as denser networks. Every
figure here is therefore also broken down by source site and page type.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from ..models.enums import EntityType, MentionResolutionStatus

FULL_NAME = {"NAME_EXACT", "SAME_NORMALIZED_NAME", "ALTERNATE_NAME_MATCH"}


def _rate(n: int, d: int) -> float | None:
    return round(n / d, 3) if d else None


def mention_stats(ds) -> dict[str, Any]:
    mentions = list(ds.mentions.values())
    if not mentions:
        return {}
    persons = {p.canonical_id: p.label for p in ds.by_type(EntityType.PERSON)}
    resolved = [m for m in mentions if m.resolution.status.resolved]
    open_ = [m for m in mentions if not m.resolution.status.resolved]
    by_source: dict[str, Counter] = defaultdict(Counter)
    by_page: dict[str, Counter] = defaultdict(Counter)
    for m in mentions:
        st = m.resolution.status.value
        doc = ds.documents.get(m.document_ids[0]) if m.document_ids else None
        page = doc.source_type.value if doc is not None else "unknown"
        for bucket in (by_source[m.source_id], by_page[page]):
            bucket["total"] += 1
            bucket[st] += 1
            bucket["resolved"] += int(m.resolution.status.resolved)

    def table(groups: dict[str, Counter]) -> dict[str, dict[str, Any]]:
        return {k: dict(sorted(v.items())) | {"resolution_rate": _rate(v["resolved"], v["total"])}
                for k, v in sorted(groups.items())}

    same_name = [m for m in open_ if any(set(c.signals) & FULL_NAME and not c.rejected for c in m.candidates)]
    per_person = Counter(c.person_id for m in same_name for c in m.candidates
                         if set(c.signals) & FULL_NAME and not c.rejected)
    rates = [v["resolved"] / v["total"] for v in by_source.values() if v["total"] >= 20]
    return {
        "total": len(mentions),
        "resolved": len(resolved),
        "not_resolved": len(open_),
        "resolution_rate": _rate(len(resolved), len(mentions)),
        "by_status": dict(sorted(Counter(m.resolution.status.value for m in mentions).items())),
        "resolved_by_method": dict(sorted(Counter(m.resolution.method for m in resolved).items())),
        "review_required": sum(1 for m in mentions if m.resolution.status is MentionResolutionStatus.REVIEW_REQUIRED),
        "no_candidate": sum(1 for m in mentions if m.resolution.status is MentionResolutionStatus.UNRESOLVED),
        "with_multiple_viable_candidates": sum(
            1 for m in mentions if any("MULTIPLE_CANDIDATES" in c.negative_signals for c in m.candidates)),
        "manually_resolved": sum(1 for m in mentions if m.resolution.status is MentionResolutionStatus.MANUAL_CONFIRMED),
        "rejected_candidates": sum(1 for m in mentions for c in m.candidates if c.rejected),
        "not_resolved_sharing_a_person_name": len(same_name),
        "persons_with_most_unresolved_same_name_mentions": [
            {"person_id": pid, "label": persons.get(pid, pid), "mentions": n} for pid, n in per_person.most_common(15)],
        "not_resolved_reasons": dict(Counter(_reason_class(m.resolution.reason) for m in open_).most_common()),
        "by_source": table(by_source),
        "by_page_type": table(by_page),
        "source_rate_spread": round(max(rates) - min(rates), 3) if len(rates) > 1 else None,
    }


def _reason_class(reason: str | None) -> str:
    if not reason:
        return "unspecified"
    if reason.startswith("blocked: "):
        return reason
    if reason.startswith("no rule satisfied"):
        return "no rule satisfied"
    return reason.split(";")[0]

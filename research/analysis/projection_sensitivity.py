"""How much of a co-participation graph is the data, and how much is the way it was projected? (#17)

The Person-Project graph (bipartite) is what the pages state. The Person-Person graph is a *derived projection*
of it: two persons are tied when they are listed on the same project. A project of n persons adds n(n-1)/2
ties, so the projection is a function of the project sizes as much as of who collaborates. This script
measures that dependence on one release, and the dependence on the identity decisions the edges rest on.

    python research/analysis/projection_sensitivity.py data/releases/<release> [--json] [--seeds 10]

Three things are varied, one at a time, against the same baseline (the ``default`` edges, unweighted):

* the **weighting** of the projection: ``unweighted`` (1 per tied pair), ``project_count`` (shared projects),
  ``size_discounted`` (each shared project adds 1/(n-1), Newman 2001);
* the **identity policy** of the edges (readiness.variant_memberships): every edge, only edges with an anchored
  or certain identification, only projects whose stated participants are all in the graph. The precision side;
  the recall side is a separate, labelled **upper bound** (readiness.review_candidates_accepted): every review
  mention that has exactly one candidate Person is taken as that Person. It is not a version of the data;
* the **large projects**, removed from k = 8, 9, 10 persons. This is a sensitivity check, never a correction:
  a large project is data, not an error.

Everything printed is an aggregate. No person is named, listed or ranked: the output says how far two ways of
scoring agree (Spearman rank correlation; overlap of the top decile), not who scores highest. The run is
deterministic: nodes and edges are inserted in sorted order, Louvain is seeded, nothing is timestamped.

Reading it: a rank correlation near 1 means the choice does not matter for that score; a low one means a
finding about 'central' persons would be a finding about the choice. The same goes for communities: a high
agreement with the institute partition means the communities largely restate who works where.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

from szocatlas.validation.readiness import (
    LARGE_PROJECT_THRESHOLDS, ReleaseData, review_candidates_accepted, variant_memberships)

WEIGHTINGS = ("unweighted", "project_count", "size_discounted")
TOP_SHARE = 0.1
Membership = dict[str, set[str]]
REVIEW_KINDS = ("another institute", "another institute, common surname", "same institute, common surname",
                "same institute", "a link or name conflict")


def review_kind(candidate: dict[str, object]) -> str:
    """The kind of review item a candidate is, read from the signals the resolver recorded (a description, not a
    decision): the page is on another institute's site or on the Person's own, the surname is on the common-surname
    list, or the page's own link contradicts the stated name."""
    signals, negative = set(candidate.get("signals", [])), set(candidate.get("negative_signals", []))
    if negative & {"LINK_NAME_MISMATCH", "LINKS_OTHER_PROFILE"}:
        return "a link or name conflict"
    where = "same institute" if signals & {"SAME_INSTITUTE", "SOURCE_UNIT_MEMBER"} else "another institute"
    return f"{where}, common surname" if "COMMON_SURNAME" in negative else where


# ------------------------------------------------------------------ the projection
def projection(mem: Membership, weighting: str, *, drop_from: int | None = None) -> nx.Graph:
    """Co-participation graph of a project -> Persons table.

    ``unweighted``: weight 1 per tied pair. ``project_count``: the number of shared projects.
    ``size_discounted``: each shared project of n persons adds 1/(n-1). ``drop_from=k`` leaves out the projects
    with k or more persons; their persons stay in the graph (as isolates unless another project ties them)."""
    weight: dict[tuple[str, str], float] = defaultdict(float)
    nodes: set[str] = set()
    for pid in sorted(mem):
        members = sorted(mem[pid])
        nodes.update(members)
        n = len(members)
        if n < 2 or (drop_from is not None and n >= drop_from):
            continue
        add = {"unweighted": 0.0, "project_count": 1.0, "size_discounted": 1.0 / (n - 1)}[weighting]
        for a, b in itertools.combinations(members, 2):
            weight[(a, b)] += add
    g = nx.Graph()
    g.add_nodes_from(sorted(nodes))
    for (a, b), w in sorted(weight.items()):
        w = 1.0 if weighting == "unweighted" else w
        g.add_edge(a, b, weight=w, distance=1.0 / w)
    return g


def bipartite_degree(mem: Membership) -> dict[str, int]:
    """Projects per Person, every project counted (a project with one Person included)."""
    out: Counter = Counter()
    for members in mem.values():
        out.update(members)
    return dict(out)


# ------------------------------------------------------------------ agreement between scorings
def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1  # ties share the mean rank
        i = j + 1
    return ranks


def spearman(a: dict[str, float], b: dict[str, float]) -> float | None:
    """Rank correlation over the Persons scored in both; None when either side has no spread."""
    keys = sorted(set(a) & set(b))
    if len(keys) < 3:
        return None
    ra, rb = _ranks([round(a[k], 9) for k in keys]), _ranks([round(b[k], 9) for k in keys])
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va, vb = sum((x - ma) ** 2 for x in ra), sum((y - mb) ** 2 for y in rb)
    return round(cov / math.sqrt(va * vb), 3) if va and vb else None


def top_set(scores: dict[str, float], universe: set[str], share: float = TOP_SHARE) -> set[str]:
    """The best-scoring ``share`` of ``universe``: every Person at or above the cut-off score, so a tie at the
    cut-off keeps all tied Persons rather than choosing among them. A zero score is never in the top."""
    if not universe:
        return set()
    k = max(1, math.ceil(share * len(universe)))
    ranked = sorted((round(scores.get(p, 0.0), 9) for p in universe), reverse=True)
    cut = ranked[k - 1]
    return {p for p in universe if cut > 0 and round(scores.get(p, 0.0), 9) >= cut}


def agreement(a: dict[str, float], b: dict[str, float], universe: set[str]) -> dict[str, object]:
    """Spearman rho and the overlap (Jaccard) of the top deciles of two scorings of the same Persons."""
    ta, tb = top_set(a, universe), top_set(b, universe)
    union = ta | tb
    return {"spearman": spearman({p: a.get(p, 0.0) for p in universe}, {p: b.get(p, 0.0) for p in universe}),
            "top_decile_jaccard": round(len(ta & tb) / len(union), 3) if union else None,
            "top_decile_sizes": [len(ta), len(tb)]}


def nmi(a: dict[str, object], b: dict[str, object]) -> float | None:
    """Normalised mutual information of two labellings over the Persons labelled in both (arithmetic mean)."""
    keys = sorted(set(a) & set(b))
    n = len(keys)
    if n < 2:
        return None
    ca, cb = Counter(a[k] for k in keys), Counter(b[k] for k in keys)
    joint = Counter((a[k], b[k]) for k in keys)

    def entropy(c: Counter) -> float:
        return -sum(v / n * math.log(v / n) for v in c.values())

    ha, hb = entropy(ca), entropy(cb)
    if ha == 0 and hb == 0:
        return 1.0
    if ha == 0 or hb == 0:
        return 0.0
    mi = sum(v / n * math.log((v / n) / ((ca[x] / n) * (cb[y] / n))) for (x, y), v in joint.items())
    return round(mi / ((ha + hb) / 2), 3)


# ------------------------------------------------------------------ communities
def louvain(g: nx.Graph, seed: int = 0) -> dict[str, int]:
    """Person -> community id, on the Persons that have a tie. Seeded; ids are renumbered by size then by the
    smallest member id, so an unchanged partition always prints the same."""
    core = g.subgraph(n for n in g if g.degree(n) > 0)
    if core.number_of_edges() == 0:
        return {}
    parts = nx.community.louvain_communities(core, weight="weight", seed=seed)
    parts = sorted((sorted(p) for p in parts), key=lambda p: (-len(p), p[0]))
    return {person: i for i, p in enumerate(parts) for person in p}


def community_profile(g: nx.Graph, site: dict[str, str], unit: dict[str, str], seeds: int) -> dict[str, object]:
    part = louvain(g, 0)
    if not part:
        return {"communities": 0}
    groups: dict[int, set[str]] = defaultdict(set)
    for person, c in part.items():
        groups[c].add(person)
    sizes = sorted((len(v) for v in groups.values()), reverse=True)
    core = g.subgraph(part)
    by_site: dict[str, set[str]] = defaultdict(set)
    for person in part:
        by_site[site.get(person, "other")].add(person)
    others = [louvain(g, s) for s in range(1, seeds)]
    return {
        "persons": len(part),
        "communities": len(groups),
        "largest_community_share": round(sizes[0] / len(part), 3),
        "modularity": round(nx.community.modularity(core, list(groups.values()), weight="weight"), 3),
        "modularity_of_the_institute_partition": round(nx.community.modularity(core, list(by_site.values()),
                                                                               weight="weight"), 3),
        "nmi_with_institute": nmi(part, {p: site.get(p, "other") for p in part}),
        "nmi_with_unit": nmi(part, {p: unit[p] for p in part if p in unit}),
        "persons_with_one_unit": sum(1 for p in part if p in unit),
        "seed_stability_min_nmi": min((nmi(part, o) for o in others), default=None),
    }


# ------------------------------------------------------------------ one release
def labels(rel: ReleaseData) -> tuple[dict[str, str], dict[str, str]]:
    """Person -> institute (its source site; 'multi', a group of its own, when it has profiles on more than one: a
    partition needs one label per Person) and -> its one unit (only Persons with exactly one MEMBER_OF unit; the
    others are left out of the unit comparison)."""
    site = {pid: next(iter(s)) if len(s) == 1 else "multi" for pid, s in rel.person_sites.items()}
    units: dict[str, set[str]] = defaultdict(set)
    for r in rel.by_type["MEMBER_OF"]:
        if r["source_id"] in rel.persons and r["target_id"] in rel.units:
            units[r["source_id"]].add(r["target_id"])
    return site, {p: next(iter(u)) for p, u in units.items() if len(u) == 1}


def structure(g: nx.Graph, sites: dict[str, set[str]]) -> dict[str, object]:
    """Size and shape of a projection. A tie is across institutes when the two Persons share no source site
    (the definition of readiness C4: a Person with profiles on two sites belongs to both)."""
    comps = sorted((len(c) for c in nx.connected_components(g.subgraph(n for n in g if g.degree(n) > 0))), reverse=True)
    tied = sum(comps)
    across = sum(1 for a, b in g.edges if sites.get(a, set()).isdisjoint(sites.get(b, set())))
    return {"persons_with_edge": g.number_of_nodes(), "persons_in_ties": tied, "ties": g.number_of_edges(),
            "ties_across_institutes": across, "components": len(comps),
            "largest_component": comps[0] if comps else 0,
            "largest_component_share": round(comps[0] / tied, 3) if tied else None}


def scorings(g: nx.Graph) -> dict[str, dict[str, float]]:
    weighted = g.number_of_edges() > 0 and any(d["weight"] != 1.0 for _, _, d in g.edges(data=True))
    return {"degree": dict(g.degree()), "strength": dict(g.degree(weight="weight")),
            "betweenness": nx.betweenness_centrality(g, weight="distance" if weighted else None)}


def sensitivity(release: Path, seeds: int = 10) -> dict[str, object]:
    rel = ReleaseData(release)
    site, unit = labels(rel)
    variants = variant_memberships(rel)
    base = variants["default"]
    out: dict[str, object] = {"release_id": rel.manifest.get("release_id") or release.name,
                              "source_set_digest": (rel.manifest.get("source_set") or {}).get("digest")}
    if not base:
        return out | {"note": "no Person has a project edge in this release"}
    universe = {p for ms in base.values() for p in ms}
    graphs = {w: projection(base, w) for w in WEIGHTINGS}
    sc = {w: scorings(g) for w, g in graphs.items()}
    bip = {p: float(v) for p, v in bipartite_degree(base).items()}
    sizes = Counter(len(ms) for ms in base.values())

    def share_by_weighting(k: int) -> dict[str, float | None]:
        """Share of the total tie weight that comes from projects of k or more persons."""
        per_project = {"project_count": lambda n: n * (n - 1) / 2, "size_discounted": lambda n: n / 2}
        out_k: dict[str, float | None] = {}
        for w, f in per_project.items():
            total = sum(f(n) * c for n, c in sizes.items() if n >= 2)
            out_k[w] = round(sum(f(n) * c for n, c in sizes.items() if n >= k) / total, 3) if total else None
        return out_k

    # 1. what the weightings do to the same graph
    def weight_total(g: nx.Graph) -> float:
        return sum(d["weight"] for _, _, d in g.edges(data=True))

    def cross(g: nx.Graph, differs) -> float | None:
        total = weight_total(g)
        wt = sum(d["weight"] for a, b, d in g.edges(data=True) if differs(a, b)) if total else 0
        return round(wt / total, 3) if total else None

    institutes_differ = lambda a, b: rel.person_sites.get(a, set()).isdisjoint(rel.person_sites.get(b, set()))  # noqa: E731
    units_differ = lambda a, b: unit[a] != unit[b]  # noqa: E731

    unit_pairs = {p for p in universe if p in unit}
    out["bipartite"] = {
        "persons": len(universe), "projects_with_person": len(base),
        "project_size_distribution": {str(k): v for k, v in sorted(sizes.items())},
        "projects_per_person_distribution": {str(k): v for k, v in sorted(Counter(int(v) for v in bip.values()).items())},
    }
    out["weightings"] = {
        w: {**structure(g, rel.person_sites), "total_weight": round(weight_total(g), 3),
            "weight_across_institutes": cross(g, institutes_differ),
            "weight_across_units_among_persons_with_one_unit": cross(
                g.subgraph(unit_pairs).copy(), units_differ) if unit_pairs else None,
            "weight_from_projects_with_k_or_more_persons": {
                f">={k}": share_by_weighting(k).get(w) if w != "unweighted" else None for k in LARGE_PROJECT_THRESHOLDS}}
        for w, g in graphs.items()}

    # 2. do the scorings agree on the same persons?
    s = {w: sc[w] for w in WEIGHTINGS}
    pairs = {
        "degree vs strength (project_count)": (s["unweighted"]["degree"], s["project_count"]["strength"]),
        "degree vs strength (size_discounted)": (s["unweighted"]["degree"], s["size_discounted"]["strength"]),
        "strength (project_count) vs strength (size_discounted)": (s["project_count"]["strength"],
                                                                    s["size_discounted"]["strength"]),
        "degree vs projects per person (bipartite)": (s["unweighted"]["degree"], bip),
        "strength (size_discounted) vs projects per person (bipartite)": (s["size_discounted"]["strength"], bip),
        "betweenness (hops) vs betweenness (1/project_count)": (s["unweighted"]["betweenness"],
                                                                s["project_count"]["betweenness"]),
        "betweenness (hops) vs betweenness (1/size_discounted)": (s["unweighted"]["betweenness"],
                                                                  s["size_discounted"]["betweenness"]),
        "betweenness (1/project_count) vs betweenness (1/size_discounted)": (
            s["project_count"]["betweenness"], s["size_discounted"]["betweenness"]),
    }
    out["scoring_agreement"] = {k: agreement(a, b, universe) for k, (a, b) in pairs.items()}
    # Under 1/(n-1) every project adds exactly 1 to the strength of each of its persons, so the strength is the
    # number of projects with two or more persons: the discounted projection adds nothing to the bipartite degree.
    two_plus = Counter(p for ms in base.values() if len(ms) >= 2 for p in ms)
    out["size_discounted_strength_equals_projects_with_two_or_more_persons"] = all(
        abs(sc["size_discounted"]["strength"].get(p, 0.0) - two_plus.get(p, 0)) < 1e-9 for p in universe)

    # 3. identity policy and large-project removal, each against the default unweighted graph
    base_g = graphs["unweighted"]
    base_part = louvain(base_g, 0)

    def against_baseline(mem: Membership, drop_from: int | None = None) -> dict[str, object]:
        g = projection(mem, "unweighted", drop_from=drop_from)
        gs = projection(mem, "size_discounted", drop_from=drop_from)
        sc_v = scorings(g)
        part = louvain(g, 0)
        return {**structure(g, rel.person_sites),
                "persons_of_the_baseline_present": len(universe & set(g)),
                "degree_vs_baseline": agreement(base_g_scores["degree"], sc_v["degree"], universe),
                "strength_size_discounted_vs_baseline": agreement(
                    sc["size_discounted"]["strength"], scorings(gs)["strength"], universe),
                "communities_nmi_with_baseline": nmi(base_part, part) if part else None}

    base_g_scores = sc["unweighted"]
    out["identity_policy"] = {name: against_baseline(m) for name, m in variants.items() if name != "default"}
    accepted, accepted_info = review_candidates_accepted(rel)
    out["identity_upper_bound"] = {"all single-candidate statements accepted": {**accepted_info, **against_baseline(accepted)}}
    for kind in REVIEW_KINDS:  # where the bound comes from: one kind of review statement at a time
        only, only_info = review_candidates_accepted(rel, accept=lambda c, k=kind: review_kind(c) == k)
        if only_info["pairs"]:
            out["identity_upper_bound"][f"only: {kind}"] = {**only_info, **against_baseline(only)}
    out["large_projects_removed"] = {f">={k}": {"projects_removed": sum(1 for ms in base.values() if len(ms) >= k),
                                                **against_baseline(base, drop_from=k)}
                                     for k in LARGE_PROJECT_THRESHOLDS}

    # 4. do the communities restate the institutes?
    comm: dict[str, object] = {}
    for w in WEIGHTINGS:
        comm[f"default, {w}"] = community_profile(graphs[w], site, unit, seeds)
    for name, m in variants.items():
        if name != "default":
            comm[f"{name}, unweighted"] = community_profile(projection(m, "unweighted"), site, unit, seeds)
    for k in LARGE_PROJECT_THRESHOLDS:
        comm[f"large projects (>={k}) removed, unweighted"] = community_profile(
            projection(base, "unweighted", drop_from=k), site, unit, seeds)
    out["communities"] = comm
    out["persons_by_institute"] = dict(sorted(Counter(site.get(p, "other") for p in universe).items()))
    return out


# ------------------------------------------------------------------ output
def _fmt(v: object) -> str:
    if v is None:
        return "-"
    return f"{v:.3f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def render(rep: dict[str, object]) -> str:
    L = [f"# Projection sensitivity: `{rep['release_id']}`", "",
         f"Source-set digest `{rep.get('source_set_digest')}`. Aggregates only: no Person is named or ranked. "
         "Command: `python research/analysis/projection_sensitivity.py data/releases/<release>`.", ""]
    if "note" in rep:
        return "\n".join(L + [str(rep["note"]), ""])
    b = rep["bipartite"]
    L += ["## Bipartite layer (primary)", "",
          f"{b['persons']} Persons with a project edge on {b['projects_with_person']} Projects with a Person.", "",
          "Project size (Persons per project: projects): "
          + ", ".join(f"{k}: {v}" for k, v in b["project_size_distribution"].items()) + ".", "",
          "Projects per Person (projects: Persons): "
          + ", ".join(f"{k}: {v}" for k, v in b["projects_per_person_distribution"].items()) + ".", ""]
    L += ["## Weightings of the projection", "",
          "| weighting | ties | total weight | components | largest component | weight across institutes "
          "| weight across units | weight from projects of >=8 / >=9 / >=10 persons |", "|---|---|---|---|---|---|---|---|"]
    for w, v in rep["weightings"].items():
        big = v["weight_from_projects_with_k_or_more_persons"]
        L.append(f"| {w} | {v['ties']} | {_fmt(v['total_weight'])} | {v['components']} | {v['largest_component']} "
                 f"| {_fmt(v['weight_across_institutes'])} | {_fmt(v['weight_across_units_among_persons_with_one_unit'])} "
                 f"| {' / '.join(_fmt(big[f'>={k}']) for k in LARGE_PROJECT_THRESHOLDS)} |")
    L += ["", "Weight across institutes / units is the share of the total tie weight on ties between Persons who share "
          "no source site (readiness C4; a Person with profiles on two sites belongs to both) / who have different "
          "units (only Persons with exactly one unit). The last column is the share of the total weight that comes "
          "from the projects of that size.", ""]
    L += ["## Do the scorings agree? (default edges, same Persons)", "",
          "| two scorings of the same Persons | Spearman rho | top-decile overlap (Jaccard) | top-decile sizes |",
          "|---|---|---|---|"]
    for k, v in rep["scoring_agreement"].items():
        L.append(f"| {k} | {_fmt(v['spearman'])} | {_fmt(v['top_decile_jaccard'])} | {v['top_decile_sizes']} |")
    L += ["", "Size-discounted strength equals the number of projects with two or more persons: "
          f"{rep['size_discounted_strength_equals_projects_with_two_or_more_persons']}.", ""]
    for key, title in (("identity_policy", "Identity policy against the default edges"),
                       ("identity_upper_bound", "Review queue accepted (an upper bound, not a version of the data)"),
                       ("large_projects_removed", "Large projects removed (sensitivity, not a correction)")):
        L += [f"## {title}", ""]
        if key == "identity_upper_bound":
            L += ["Every stated name still in REVIEW_REQUIRED that has exactly one viable candidate Person is taken as that "
                  "Person, as if a reviewer had confirmed all of them. It bounds from above what the review queue could "
                  "add under that one rule. A reviewer rejects some (a common surname, a name that contradicts the page's "
                  "own link), a name with several candidates is left out, and none of this is in any release: it is the "
                  "recall-side counterpart of the strict policy above. The rows 'only: ...' accept one kind of review "
                  "statement at a time (by the signals the resolver recorded) to show where the bound comes from.", ""]
        L += ["| version | persons with edge | ties | ties across institutes | components | largest component "
              "| rho (degree) | top-decile overlap (degree) | rho (discounted strength) | community NMI with baseline |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for name, v in rep[key].items():
            d, s = v["degree_vs_baseline"], v["strength_size_discounted_vs_baseline"]
            label = name + (f" ({v['projects_removed']} projects)" if "projects_removed" in v else "") \
                + (f" ({v['new_edges']} new edge{'' if v['new_edges'] == 1 else 's'})" if "new_edges" in v else "")
            L.append(f"| {label} | {v['persons_with_edge']} | {v['ties']} | {v['ties_across_institutes']} | {v['components']} "
                     f"| {v['largest_component']} | {_fmt(d['spearman'])} | {_fmt(d['top_decile_jaccard'])} | {_fmt(s['spearman'])} "
                     f"| {_fmt(v['communities_nmi_with_baseline'])} |")
        L.append("")
        if key == "identity_upper_bound":
            for v in list(rep[key].values())[:1]:
                L += [f"{v['review_mention_records']} review mention records are {v['review_statements']} distinct "
                      f"(Project, stated name) statements still in review (the same name seen in two documents is one). "
                      f"By viable candidates: one Person {v['with_one_candidate']} (accepted), several "
                      f"{v['with_several_candidates']} (left out), none {v['with_no_viable_candidate']}. The {v['pairs']} "
                      f"(Project, Person) pairs add {v['new_edges']} edges that are new; {v['persons_gaining_a_first_edge']} "
                      f"Persons gain their first project edge and {v['projects_gaining_a_person']} Projects gain a Person.", ""]
    L += ["## Do the communities restate the institutes?", "",
          "Louvain, seeded, on the Persons with at least one tie. NMI is the normalised mutual information with the "
          "partition by institute (units: Persons with exactly one unit). The institute partition's own modularity is "
          "what 'communities = institutes' would score; seed stability is the lowest NMI between the seed-0 partition "
          "and the other seeds.", "",
          "| graph | persons | communities | largest share | modularity | modularity of the institute partition "
          "| NMI institute | NMI unit | seed stability |", "|---|---|---|---|---|---|---|---|---|"]
    for name, v in rep["communities"].items():
        if not v.get("communities"):
            L.append(f"| {name} | 0 | 0 | - | - | - | - | - | - |")
            continue
        L.append(f"| {name} | {v['persons']} | {v['communities']} | {_fmt(v['largest_community_share'])} "
                 f"| {_fmt(v['modularity'])} | {_fmt(v['modularity_of_the_institute_partition'])} "
                 f"| {_fmt(v['nmi_with_institute'])} | {_fmt(v['nmi_with_unit'])} | {_fmt(v['seed_stability_min_nmi'])} |")
    L += ["", "Persons with a project edge by institute: "
          + ", ".join(f"{k} {v}" for k, v in rep["persons_by_institute"].items()) + ".", ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("release", type=Path)
    ap.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    ap.add_argument("--seeds", type=int, default=10, help="Louvain seeds for the stability check (default 10)")
    args = ap.parse_args(argv)
    rep = sensitivity(args.release, seeds=args.seeds)
    print(json.dumps(rep, indent=2, ensure_ascii=False, sort_keys=True) if args.json else render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Institutional structure of a release (docs/research_questions.md, row 1).

Usage: python research/analysis/structure.py data/releases/<release>
"""

import sys
from collections import Counter
from pathlib import Path

from szocatlas.graph.export import to_networkx


def main(release: Path) -> None:
    g = to_networkx(release, relation_types={"AFFILIATED_WITH", "MEMBER_OF", "PART_OF"})
    label = {n: d.get("label", n) for n, d in g.nodes(data=True)}
    parent = {u: v for u, v, d in g.edges(data=True) if d["type"] == "PART_OF"}

    def top(n):
        seen = set()
        while n in parent and n not in seen:
            seen.add(n)
            n = parent[n]
        return n

    people_per_inst = Counter()
    for u, v, d in g.edges(data=True):
        if d["type"] == "AFFILIATED_WITH":
            people_per_inst[top(v)] += 1
    total = sum(people_per_inst.values()) or 1
    hhi = sum((c / total) ** 2 for c in people_per_inst.values())
    print(f"release: {release.name}  (observed affiliations only)")
    for inst, c in people_per_inst.most_common():
        print(f"{c:5d}  {label[inst]}")
    print(f"Herfindahl concentration over top-level institutions: {hhi:.3f}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))

# Research questions → data → measures

Metrics are chosen per question; none is computed "because it exists". The analysis layer
(`research/`) reads releases via `szocatlas.graph.export.to_networkx`, observed edges only
unless an analysis explicitly opts into derived ones.

| Question | Data it needs | Status | Measure (and why) |
|---|---|---|---|
| Which institutions structure the field? How centralised is it? | person–unit–institution affiliations, full institutional coverage | phase 1 (TK), more adapters next | share of researchers per institution; Herfindahl concentration; institution-projection degree via shared projects |
| How Budapest-centric is it? How do regional centres connect to Budapest? | institution `city`, co-project and co-authorship ties | needs regional adapters + MTMT | share of cross-city ties vs expected under random mixing (E–I index); bridging institutions |
| Which researchers bridge separate communities? | co-project, co-membership, later co-authorship | partial (projects) | betweenness / Burt constraint on the person projection — *brokerage* is the sociological claim, betweenness is only its proxy |
| Which institutions carry which methodological traditions? | USES_METHOD (derived), affiliations | phase 1, lexical | person–method bipartite network, method shares per institution; compare with publication-based classification later |
| How did computational social science / network science emerge? | dated projects, publications, group founding dates, historical affiliations | needs MTMT + archives | first appearance of methods per institution over time; diffusion through co-authorship |
| How does Roma research connect to the field? Is it one community? | topic edges, projects, affiliations, co-authorship | phase 1 partial | community detection on the subgraph of `roma_studies` researchers (+ neighbours); compare Pécs Romology vs Budapest clusters; do *not* presume one community |
| Genealogy of the Kemény school / network sociology | SUPERVISED_BY (doktori.hu), historical literature claims | not yet | descendant trees; tradition membership only with evidence types |
| Who connects sociology with economics, demography, political science…? | discipline of units (KRTK, NKI, PTI), co-project/co-authorship | partial | cross-discipline tie share per person |
| How have affiliations changed over time? | explicit intervals, archived snapshots | not yet | Sankey of institution-to-institution flows per period; turnover |
| How internationalised is the field? | publications (language, venue, co-author countries) | not yet | share of international co-authorship; venue language |
| Are theory and empirical communities segregated? | topic + method edges, co-authorship | partial | assortativity on topic/method attributes |
| Do elites reproduce themselves? | supervision, positions, academy membership | not yet | intergenerational position transition matrices along supervision chains |
| Which traditions disappeared, fragmented or merged? | multi-period community detection | not yet | community tracking across periods (Jaccard matching of Leiden partitions) |

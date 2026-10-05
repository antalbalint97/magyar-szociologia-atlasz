# Research analysis layer

Independent of the web app. Reads a release directory, never the live sites or Neo4j.

```python
from pathlib import Path
from szocatlas.graph.export import to_networkx
g = to_networkx(Path("data/releases/<release>"))            # observed edges only
g_all = to_networkx(Path("data/releases/<release>"), observed_only=False)
```

`analysis/structure.py` shows the pattern: every metric is tied to a question from
docs/research_questions.md and is reported with the release id it was computed on.

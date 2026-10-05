"""Generate docs/data_dictionary.md from the Pydantic models (``python -m szocatlas.datadict``)."""

from __future__ import annotations

import sys
from enum import Enum

from . import SCHEMA_VERSION
from .models import entities, enums, provenance
from .registry import REPO_ROOT

TARGET = REPO_ROOT / "docs" / "data_dictionary.md"


def _type(ann) -> str:
    if isinstance(ann, type):
        return ann.__name__
    s = repr(ann).replace("typing.", "").replace("szocatlas.models.", "")
    for mod in ("enums.", "entities.", "provenance.", "datetime.", "<class '", "'>"):
        s = s.replace(mod, "")
    return s.replace("|", "\\|")


def render() -> str:
    out = [f"# Data dictionary (schema {SCHEMA_VERSION})", "",
           "Generated from `src/szocatlas/models` by `python -m szocatlas.datadict`. Do not edit by hand.", ""]
    models = [provenance.SourceDocument, provenance.Evidence, provenance.EntityRef, provenance.Claim,
              provenance.SourceRecord, entities.Relation] + list(entities.ENTITY_CLASSES.values())
    for m in models:
        title = m.__name__
        if hasattr(m, "entity_type") and isinstance(getattr(m, "entity_type", None), Enum):
            title += f" (`{m.entity_type.value}`, id prefix `{entities.ID_PREFIX[m.entity_type]}_`)"
        out += [f"## {title}", "", (m.__doc__ or "").strip().split("\n\n")[0], "",
                "| field | type | required |", "|---|---|---|"]
        for name, f in m.model_fields.items():
            out.append(f"| `{name}` | `{_type(f.annotation)}` | {'yes' if f.is_required() else ''} |")
        out.append("")
    out += ["## Enumerations", ""]
    for name in sorted(dir(enums)):
        obj = getattr(enums, name)
        if isinstance(obj, type) and issubclass(obj, Enum) and obj.__module__ == enums.__name__:
            out.append(f"* **{name}**: " + ", ".join(f"`{m.value}`" for m in obj))
    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    TARGET.write_text(render(), encoding="utf-8")
    print(f"wrote {TARGET}", file=sys.stderr)

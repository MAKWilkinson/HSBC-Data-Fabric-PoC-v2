
# ---------------------------------------------------------------------------
# 4 · Graphing — mapping JSONs → Mermaid charts  (graph.py)
# ---------------------------------------------------------------------------

"""
Walks MAPPINGS_DIR for *.mapping.json files and writes a mirror .mmd file
under MERMAIDS_DIR, preserving the provider/consumer directory structure:

    mappings/<providing>/<consuming>/<name>.mapping.json
    mermaids/<providing>/<consuming>/<name>.mmd

Mermaid text is a VIEW over the stored mapping JSON — the JSON remains the
source of truth. Regeneration is cheap and idempotent: every run rewrites
the .mmd for every mapping found.

As with persistence.py, storage locations are module constants that tests
can reassign:

    graph.MERMAIDS_DIR = tmp_path / "mermaids"
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import persistence

import logging
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Storage locations
# ---------------------------------------------------------------------------

_MODULE_DIR = Path(__file__).resolve().parent

MERMAIDS_DIR = _MODULE_DIR / "mermaids"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def find_mapping_paths() -> list[Path]:
    """All *.mapping.json files under MAPPINGS_DIR, sorted for determinism."""
    if not persistence.MAPPINGS_DIR.is_dir():
        logger.warning("Mappings directory %s does not exist", persistence.MAPPINGS_DIR)
        return []
    return sorted(persistence.MAPPINGS_DIR.rglob("*.mapping.json"))


def load_mapping_doc(path: Path) -> dict[str, Any] | None:
    """Read one stored mapping as a plain dict; None if unreadable.

    Reads the raw JSON directly rather than going through
    persistence.load_mapping — rendering needs no live FileSchemas or
    staleness checks; it draws whatever was last persisted.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        logger.warning("Skipping unreadable mapping %s: %s", path, error)
        return None


def mermaid_path_for(mapping_path: Path) -> Path:
    """Mirror a mapping's path from MAPPINGS_DIR into MERMAIDS_DIR.

    mappings/a/b/x.mapping.json  →  mermaids/a/b/x.mmd
    """
    relative = mapping_path.relative_to(persistence.MAPPINGS_DIR)
    stem = relative.name.removesuffix(".mapping.json")
    return MERMAIDS_DIR / relative.parent / f"{stem}.mmd"


# ---------------------------------------------------------------------------
# Mermaid generation
# ---------------------------------------------------------------------------

def _mermaid_id(text: str) -> str:
    """Sanitise arbitrary names into Mermaid-safe node ids."""
    return re.sub(r"[^A-Za-z0-9_]", "_", text)


def _node(node_id: str, label: str) -> str:
    """One Mermaid node with a quoted label (safe for [], |, dots, etc)."""
    return f'{node_id}["{label}"]'


def mapping_to_mermaid(doc: dict[str, Any]) -> str:
    """Render one mapping doc as a field-lineage flowchart.

    Inbound fields on the left, outbound fields on the right, one edge per
    (source, outbound_field) pair labelled with the transformation type.
    UNMAPPED / sourceless fields still appear as nodes so gaps are visible,
    they just have no incoming edge.
    """
    in_src = doc["inbound_schema"]["source"]
    out_src = doc["outbound_schema"]["source"]
    field_mappings = doc.get("mappings", [])

    in_title = Path(in_src["message_file_name"]).stem
    out_title = Path(out_src["message_file_name"]).stem

    lines = ["flowchart LR"]

    # Inbound subgraph — every distinct source field, in first-seen order
    lines.append(f'  subgraph IN["{in_src["providing_system"]}: {in_title}"]')
    seen_sources: list[str] = []
    for m in field_mappings:
        for s in m.get("sources", []):
            if s not in seen_sources:
                seen_sources.append(s)
                lines.append(f"    {_node('in_' + _mermaid_id(s), s)}")
    lines.append("  end")

    # Outbound subgraph — every outbound field, mapped or not
    lines.append(f'  subgraph OUT["{out_src["providing_system"]}: {out_title}"]')
    for m in field_mappings:
        out_field = m.get("outbound_field", "")
        lines.append(f"    {_node('out_' + _mermaid_id(out_field), out_field)}")
    lines.append("  end")

    # Edges
    for m in field_mappings:
        if m.get("transformation") == "UNMAPPED" or not m.get("sources"):
            continue
        target = "out_" + _mermaid_id(m["outbound_field"])
        for s in m["sources"]:
            lines.append(f"  in_{_mermaid_id(s)} -->|{m['transformation']}| {target}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def graph_all_mappings(skip_unrelated: bool = True) -> list[Path]:
    """Find every stored mapping and write its mirror .mmd chart.

    Returns the list of paths written. Unrelated pairs are skipped by
    default — their diagrams are just two disconnected boxes.
    """
    written: list[Path] = []

    for mapping_path in find_mapping_paths():
        doc = load_mapping_doc(mapping_path)
        if doc is None:
            continue

        if skip_unrelated and not doc.get("related", False):
            logger.info("Skipping unrelated mapping %s", mapping_path.name)
            continue

        target = mermaid_path_for(mapping_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(mapping_to_mermaid(doc), encoding="utf-8")
        logger.info("Wrote %s", target)
        written.append(target)

    logger.info("Graphed %d mapping(s) into %s", len(written), MERMAIDS_DIR)
    return written
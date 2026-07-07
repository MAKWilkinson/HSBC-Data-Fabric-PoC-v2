# Schema-Lineage Pipeline

Always apply the `cortex-coding-standards` skill when working in this repo.

## What this project does

Traces how data literally transforms as it moves through a system: files arrive
(**inbound**), files leave (**outbound**). The tool extracts a detailed schema for every
file, then maps each outbound field back to the inbound field(s) it came from — renamed,
split, merged, derived, dropped, or passed through unchanged.

There is no shared canonical schema and no business ontology anymore. The goal is literal,
traceable field-level lineage, not a unified domain model.

Three goals, run as a pipeline:

1. **Ingest** — discover sample files with their context (providing system, consuming
   system, direction, message type).
2. **Extract** — loop through each sample file, pass it to an LLM, and extract a detailed
   schema (field names, types, nullability, formats, enums, nesting).
3. **Map** — for each outbound field, trace it back to the inbound field(s) it originated
   from (or flag it as newly introduced within the system), classifying what happened to
   it: passthrough, rename, split, merge, derive, or drop.

## Current state

**Mid-redesign.** The project originally aimed at a shared canonical schema built through
Combine → Conceptualize → Unify stages (`DomainKnowledge`, `Ontology`, `SemanticSchema`).
That approach has been dropped in favour of literal field-level lineage: no cross-source
canonicalisation, no business-concept layer.

Fallout still to work through:

- `datamodels.py` currently encodes the old approach. `SampleFile`, `FieldSchema`, and
  `FileSchema` still hold — extraction is unaffected by this change. `DomainKnowledge`,
  `Ontology`, and `SemanticSchema` are **deprecated, pending redesign**: don't build new
  code against them. The replacement is expected to be a single lineage/mapping model
  (roughly: output field → source field(s) + transformation type), but the exact shape
  hasn't been agreed yet — that's the next thing to design, one function at a time as
  usual.
- `domain.py` (cluster → alias → relate → merge) and `ontology.py` (business entities +
  relationships) are slated for removal. Their job is replaced by a new `lineage.py`
  doing field-level transformation mapping instead. Don't extend `domain.py` or
  `ontology.py` further.
- `semantic.py` will be repurposed to export/report the lineage mapping instead of a
  unified canonical schema — signatures will change here once the lineage data model is
  agreed.
- `ingestion.py`'s provider → consumer → files directory model is unaffected for now.

### Open design questions (not yet decided — flag before assuming)

- **Scope of "the system."** Is this tracing one specific system's boundary (its inbound
  files vs its outbound files), or many systems each with their own in/out sides? This
  changes what "direction" means on a `SampleFile` and how pairs get matched for mapping.
- **Matching granularity.** Is lineage computed per matched in/out file pair (e.g. same
  message type), or across the full set of inbound schemas for every outbound field?

When helping me:

- **Do not change function signatures or the data attributes in `datamodels.py`** unless I
  explicitly ask — this includes the deprecated ones, until we've agreed the replacement.
  Note that helper functions can be added to the data models for use elsewhere in the code.
- Fill in **one function at a time** unless I say otherwise.
- Preserve provenance: every field in the output must be traceable back to the raw file
  it came from — that property is the whole point now, more than ever.

## The data-flow contract

```
SampleFile  ->  FileSchema  ->  FieldLineage (pending design)
(ingest)        (extract)       (map: which inbound field(s) -> this outbound field, how)
```

`DomainKnowledge`, `Ontology`, and `SemanticSchema` are deprecated pending redesign — see
"Current state" above.

The throughline is that **context and provenance survive every step**:

- `SampleFile` carries the interaction hierarchy (providing system / consuming system /
  message type) so identical field names in different contexts stay distinct.
- `FileSchema` keeps a back-reference to its `source`.
- The mapping stage must record, per outbound field, which inbound field(s) and file(s)
  it traces back to, and what transformation happened along the way.

Net effect: any field in an outbound file can be traced back to the inbound field(s) it
came from, with the transformation made explicit. Keep this property intact when
implementing.

`FieldSchema` is recursive (`children`) so nested JSON survives extraction.

## Module map (`src/pipeline/`)

| File | Goal | Responsibility |
|---|---|---|
| `datamodels.py` | — | Shared dataclasses. `SampleFile` / `FieldSchema` / `FileSchema` are the frozen contract; `DomainKnowledge` / `Ontology` / `SemanticSchema` are deprecated pending redesign. |
| `config.py` | — | Config, LLM client, caching, artifact checkpointing. |
| `ingestion.py` | 1 | Discover + load sample files with context. |
| `extraction.py` | 2 | LLM schema extraction per file. |
| `domain.py` | *(deprecated)* | Old cluster → alias → relate → merge logic. Slated for removal. |
| `ontology.py` | *(deprecated)* | Old business-entity/ontology logic. Slated for removal. |
| `map.py` | 3 | transformation mapping tools between inbound and outbound files and schemas. |
| `semantic.py` | 4 | *(deprecated)* |
| `orchestrator.py` | *(deprecated)* | `run_pipeline()` chains the stages end to end. |

Functions taking an LLM `client` arg do so deliberately — no globals, so they stay
testable and a stub/cache can be injected during development.

## Stack

- Framework: none (library + CLI orchestrator)
- Key dependencies: [LLM SDK — to be decided]

## Commands

| Task | Command |
|---|---|
| Install deps | `uv sync` |
| Run tests | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Type check | `uv run pyright` |

## Project structure

src-layout: package lives at `src/pipeline/`. Tests will live in `tests/`.
Add `pythonpath = ["src"]` under `[tool.pytest.ini_options]`.

## Deviations from Cortex standards

[None — fully compliant]

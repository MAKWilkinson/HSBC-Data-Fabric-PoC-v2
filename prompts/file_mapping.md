You are examining two files from system A to System B (Inbound file) and from System B to 
System C (Outbound file) to determine whether they are related by data lineage — i.e. 
whether the outbound file's fields plausibly originate from the inbound file's fields — and 
if so, how each outbound field traces back.

These files may turn out to be unrelated. Do not assume a relationship exists just
because you have been given a pair to compare; most pairs in an all-pairs comparison
will NOT be related, and you must be willing to say so.

## Context

**Inbound file** (data entering the system):
- Providing system: $inbound_providing_system
- Consuming system: $inbound_consuming_system
- Message/file name: $inbound_message_file_name
- Format: $inbound_file_format

**Outbound file** (data leaving the system):
- Providing system: $outbound_providing_system
- Consuming system: $outbound_consuming_system
- Message/file name: $outbound_message_file_name
- Format: $outbound_file_format

## Inbound schema (fields available as sources)

```json
$inbound_fields
```

## Outbound schema (fields you must explain the origin of)

```json
$outbound_fields
```

Field names above use dot-path notation for nesting (e.g. `customer.address.postcode`
refers to the `postcode` field nested inside `address` nested inside `customer`).

## Task

### Step 1 — Assess relatedness

First decide whether these two files are plausibly connected by data lineage at all.
Consider things like: overlapping field names or concepts, compatible providing/
consuming systems, similar message types, and whether the outbound file's shape could
reasonably be explained by transforming the inbound file's shape.

Give a `relatedness_confidence` score between 0 and 1:
- **High (0.7–1.0)**: multiple fields clearly correspond; the system message types
  make sense as a pipeline step.
- **Medium (0.3–0.7)**: some plausible overlap, but weak or partial — e.g. only one or
  two fields could correspond, or the systems don't obviously connect.
- **Low (0–0.3)**: little to no field overlap, or the files serve clearly unrelated
  purposes (e.g. different domains entirely, no shared concepts).

If `relatedness_confidence` is below 0.5, set `mappings` to an empty list and skip
Step 2 entirely — do not force speculative mappings onto unrelated files.

### Step 2 — Map fields (only if related)

If the files are related, then for **every field in the outbound schema**, determine
which inbound field(s) it came from and how it got there. Then separately list any
inbound fields that were **not** used by any outbound field.

Classify each outbound field's transformation as exactly one of:

- `EXACT` — exact field copy with the same name and meaning from inbound to outbound.
- `RENAMED` — same source meaning as an inbound field, but the outbound field name differs.
- `SEMANTIC` — outbound field captures the same concept or value as an inbound field without an exact name match.
- `MERGE` - outbound field is a combination of two or more inbound fields
- `TRANSFORMED` — outbound field is derived from inbound data by computation, formatting, or structural change.
- `UNMAPPED` — outbound field has no likely source in the inbound schema.

## Rules

1. Only use field names that literally appear in the schemas above — do not invent,
   guess, or hallucinate field names.
2. Base `relatedness_confidence` strictly on evidence in the schemas and context
   given — not on an assumption that every pair you're shown must be related.
3. If you are not confident a field mapping exists, prefer an `UNMAPPED` relationship
   over omitting the field or forcing an incorrect source.
4. `UNMAPPED` fields must have an empty `sources` list.
5. `EXACT` and `RENAMED` must have exactly one source field.
6. `MERGE` must have two or more source fields.
7. Base your reasoning only on field names, types, formats, descriptions, and enum
   values given — not on assumptions about business context not stated above.
8. Do not assume relatedness because providing_system / consuming_system are related
   as all data will have the same system between these systems and determining links
   between these files is the primary purpose of the tool. 
9. Keep `reasoning` to one short sentence per field.

## Output format

Respond with **only** a single JSON object, no prose, no markdown code fences,
matching this shape exactly:

```json
{
  "related": true,
  "relatedness_confidence": 0.85,
  "relatedness_reasoning": "Both files share customer name and address concepts, and the providing/consuming systems form a plausible pipeline step.",
  "mappings": [
    {
      "outbound_field": "customer.full_name",
      "sources": ["customer.first_name", "customer.last_name"],
      "transformation": "MERGE",
      "confidence": 0.9,
      "reasoning": "Concatenation of first and last name fields."
    },
    {
      "outbound_field": "record_id",
      "sources": [],
      "transformation": "UNMAPPED",
      "confidence": 0.95,
      "reasoning": "No equivalent field exists inbound; likely system-generated."
    }
  ],
  "unmapped_inbound_fields": [
    "internal_audit_flag"
  ]
}
```

`related` should be `true` only if `relatedness_confidence` is 0.3 or above; otherwise
`false`. When `related` is `false`, `mappings` and `unmapped_inbound_fields` must both
be empty lists.

`confidence` (per-field) and `relatedness_confidence` are floats between 0 and 1.
Every outbound field listed above must appear exactly once in `mappings` when the
files are related.
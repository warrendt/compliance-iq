"""The mapping model is a structured-output schema, and Azure OpenAI is strict.

``ControlMapping`` is passed as ``response_format`` to Azure OpenAI. Strict
structured output requires every object in the schema to declare
``additionalProperties: false``; a bare ``dict`` annotation produces an open
object and the request fails with a 400 before the model ever runs.

That happened in production: ``attestation: Optional[dict]`` made *every*
mapping call fail, and the broad except turned each failure into a fallback, so
the engine reported "process control, no policy" for every control of every
framework while looking healthy. A mocked model cannot see this - the schema is
only rejected by the real service - so it is asserted directly here.
"""

import pytest

from app.models.mapping import ControlMapping


def _open_objects(schema, defs, path="root", seen=None):
    """Walk a JSON schema and yield objects that would accept unknown keys."""
    seen = seen if seen is not None else set()
    found = []

    if not isinstance(schema, dict):
        return found

    ref = schema.get("$ref")
    if ref:
        name = ref.rsplit("/", 1)[-1]
        if name in seen:
            return found
        seen.add(name)
        return _open_objects(defs.get(name, {}), defs, f"{path}->{name}", seen)

    if schema.get("type") == "object" or "properties" in schema:
        if schema.get("additionalProperties") is not False:
            found.append(path)

    for key in ("anyOf", "oneOf", "allOf"):
        for i, sub in enumerate(schema.get(key, [])):
            found += _open_objects(sub, defs, f"{path}.{key}[{i}]", seen)

    for name, sub in (schema.get("properties") or {}).items():
        found += _open_objects(sub, defs, f"{path}.{name}", seen)

    items = schema.get("items")
    if isinstance(items, dict):
        found += _open_objects(items, defs, f"{path}[]", seen)

    return found


def test_no_object_in_the_mapping_schema_accepts_unknown_keys():
    schema = ControlMapping.model_json_schema()
    defs = schema.get("$defs", {})
    open_objects = _open_objects(schema, defs)
    assert not open_objects, (
        "Azure OpenAI rejects the whole request when any object in the schema "
        "omits additionalProperties: false, and the resulting fallback looks "
        f"like a real answer. Open objects: {open_objects}"
    )


def test_the_attestation_citation_is_typed_not_a_free_dict():
    """A citation with arbitrary keys cannot be validated against a catalog."""
    schema = ControlMapping.model_json_schema()
    att = schema["properties"]["attestation"]
    refs = [s.get("$ref") for s in att.get("anyOf", []) if isinstance(s, dict)]
    assert any(r and "AttestationCitation" in r for r in refs), att

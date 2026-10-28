"""Small, explicit AutoSchemaKG development ladder with unchanged native stages.

Uses the pinned original prompts, preprocessing, process_stage and parsers.
HAWKI is a new provider condition: native generation arguments are recorded but
are not sent as unverified institutional parameters. Every physical request is
sent once. A native validation retry is blocked before any additional POST.
Nothing is dispatched at import. No reference or expected fixture data enters
the constructor. --schema-from reuses saved extraction without paid re-extraction.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Experiments.strict_autoschemakg.contract import verify_source
from Experiments.strict_autoschemakg.source_imports import verified_source_imports
from Tools.abschluss import run_benchie_semantic_hawki_oct13_v1 as institutional
from Tools.hawki import probe, evaluation_controls_v2 as capture

PROTOCOL = "autoschema-source-complexity-ladder:oct14-v1"
CATEGORIES = {"EE": "entity_relation", "EV": "event_entity", "VV": "event_relation"}
CONSTRAINTS = {
    "complete_explicit_facts": "Preserve each explicitly stated fact. Do not add facts that require external knowledge or an inference unsupported by this passage.",
    "grounded_events": "Describe only event occurrences explicitly supported by this passage. Keep different occurrences distinct. Preserve their stated participants, conditions, negation and temporal qualifiers without inventing missing details.",
    "explicit_event_relations": "Return an event-event relation only when the passage explicitly supports the relation between two event occurrences. Preserve the direction and the scope of the statement. Do not turn mere sentence order or co-occurrence into temporal or causal evidence. If no such relation is stated, return an empty array.",
}
CONCEPT_DIRECTION_CONTRACT = (
    "For a RELATION, each output phrase must denote the same directed relation, or a broader relation that preserves the original head and tail roles. "
    "Do not turn the head into the recipient of its own action. Do not imply an outcome absent from the input. "
    "When no faithful abstraction is available, keep the original relation phrase instead of inventing additional phrases. "
    "These rules override requests for a minimum number of phrases or different wording. "
    "For ENTITY and EVENT, keep the original type-or-related-concept task."
)
VV_EVENT_ID_DIRECTIVE = (
    "Use Head and Tail as those event IDs instead of rewriting event sentences. "
    "Relations must still be supported by original source. "
    "Different descriptions of same occurrence must not create new event identity. "
    "Return [] when no supported relation."
)
VV_DIRECTION_CONTRACT = (
    "Each Head Relation Tail statement must be entailed by the original source. "
    "Interpret the existing causal relation labels directionally: Head because Tail means that Tail is the reason or cause of Head. "
    "Head as a result Tail means that Head is the reason or cause of Tail. "
    "A causal connector introducing a reason therefore places the reason in Tail and the effect in Head; "
    "a connector introducing a result places the cause in Head and the result in Tail. "
    "Do not always put the cause first. Do not add temporal or causal claims that are not supported by the source."
)
VV_TEMPORAL_COVERAGE_CONTRACT = (
    "The causal definitions do not restrict the other relation types in the original task. "
    "Retain every explicitly stated temporal relation using the original temporal relation labels."
)
VV_FULL_PREDICATE_CONTRACT = (
    "Relation must be a complete predicate phrase that makes the literal statement Head [Relation] Tail unambiguous after event IDs are resolved. "
    "A discourse connector that requires an omitted preposition or an unstated sentence boundary is insufficient. "
    "Preserve the causal and temporal roles affirmed by the original source, and choose the predicate wording freely."
)
VV_REFERENCE_PROMPT = (
    "Extract every relationship explicitly supported by the original source between the catalog events. "
    "Each event ID refers to an event occurrence; its sentence label is a description, not a clause to splice into another sentence. "
    "Use exact event IDs as Head and Tail. Choose a free, complete Relation predicate so that the Head event [Relation] the Tail event preserves the source roles and qualifications. "
    "Do not infer timing from causation or causation from timing, mere order, or co-occurrence. "
    "Return [] only when no supported relationship exists. "
    "Return only a strict JSON array of objects with exactly Head, Relation, Tail string fields."
)
EE_SCOPE_CONTRACT = (
    "Each entity relation must be explicitly affirmed by the source or be a faithful paraphrase without additional conditions. "
    "Do not infer new timing from causation or causation from timing or co-occurrence. "
    "When a statement links or qualifies specific event occurrences, do not replace those events with unqualified participant links. "
    "Keep that event-scoped dependency in the event-event representation rather than inventing an entity relation."
)
EE_COVERAGE_CONTRACT = (
    "Retain every source-supported entity relation, including action and object facts described within events. "
    "Route only dependencies between whole event occurrences to the event-event representation. "
    "Technical participant bindings do not replace semantic entity claims; complete the original entity-relation extraction task after the bindings."
)
EE_ENTITY_ID_DIRECTIVE = (
    "Use Head and Tail as IDs from the actual EV participant catalog below. These IDs denote participants, not events or whole statements. "
    "Do not use event IDs or turn event descriptions into participant endpoints. Preserve freely named, source-supported Relation text. "
    "A dependency between specific event occurrences belongs in the event-event representation, not an unqualified link between participants. "
    "Catalog membership is not evidence for a relation. If a source-supported claim requires a referent absent from this limited catalog, "
    "retain its source wording as an unresolved endpoint rather than substituting another ID or silently omitting the claim. "
    "Only exact catalog IDs can be resolved by the caller; an unmatched endpoint leaves the run unresolved."
)
PARTICIPANT_BINDING_RELATION = "__bind_participant__"
PARTITION_REFERENT_CONTRACT = (
    "A participant catalog entry is a mention or role occurrence, not automatically a distinct source entity. "
    "Determine who or what each mention refers to from the full original source before choosing IDs. "
    "One actor or object participating in different events remains one referent when the source identifies the same entity. "
    "Event indices, slot IDs and spelling do not replace source coreference judgment. "
    "First decide the referent groups, then choose one known canonical ID per group and emit the total binding. "
    "Do not default every catalog occurrence to a self binding."
)
EE_PARTITION_DIRECTIVE = (
    "The catalog contains participant occurrences, each with its actual EV event context. Decide from the original source which occurrences denote the same referent; "
    "equal labels alone do not prove identity and different labels alone do not prove different referents. "
    "Return one strict JSON array using only the existing Head, Relation and Tail string fields. First include exactly one technical binding record for every catalog ID: "
    '{"Head":"occurrence ID","Relation":"__bind_participant__","Tail":"canonical occurrence ID"}. '
    "Each referent group must choose one known occurrence ID from that group as its canonical ID. Every group member points directly to that ID, and the canonical ID points to itself. "
    "Do not omit or duplicate an occurrence binding, use unknown IDs, create chains or non-identity cycles. These binding records are protocol metadata, not source relations. "
    "After the binding records, include the source-supported entity relations, with Head and Tail as exact catalog participant IDs and freely named Relation text. "
    "The caller restores the unchanged label of the chosen canonical EV participant to both EE endpoints and EV participant slots. "
    "Participant IDs do not denote events or whole statements. Event-scoped dependencies belong in the event-event representation, not unqualified participant links. "
    "Catalog membership is not evidence for a relation. This catalog can omit source referents; if a source-supported claim requires a missing referent, retain its source wording as an unresolved endpoint rather than substituting an ID or silently omitting the claim. "
    "Only known IDs can be resolved, and unresolved source identity must not be guessed."
)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON fields")
            result[key] = value
        return result
    def invalid(_):
        raise ValueError("Nonfinite JSON")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def unlinked(path):
    path = Path(path).absolute()
    if any(p.is_symlink() or getattr(p, "is_junction", lambda: False)() for p in (path, *path.parents)):
        raise ValueError("Linked paths are not supported")
    return path


def save(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()


def save_json(path, value):
    save(path, canonical(value))


def structural_relation_bindings(native, edges, clean_text):
    """Identify technical EV-derived labels by occurrence provenance, never by words.

    Native CSV cleaning is reused only to compare the native JSON and its CSV.
    A label shared with any extracted EE/VV predicate or any non-EV occurrence
    is excluded from deterministic preservation.
    """
    source_predicates = {
        clean_text(item["Relation"])
        for category in ("entity_relation_dict", "event_relation_dict")
        for item in native[category]
        if isinstance(item, dict) and isinstance(item.get("Relation"), str)
    }
    ev_pairs = {}
    for event_index, item in enumerate(native["event_entity_dict"]):
        if not isinstance(item, dict) or not isinstance(item.get("Event"), str) or not isinstance(item.get("Entity"), list):
            continue
        for entity_index, entity in enumerate(item["Entity"]):
            if isinstance(entity, str):
                pair = (clean_text(item["Event"]), clean_text(entity))
                ev_pairs.setdefault(pair, []).append({"event_entity_index": event_index, "entity_index": entity_index,
                    "original_event": item["Event"], "original_entity": entity})
    groups = {}
    for edge in edges:
        groups.setdefault(edge["relation"], []).append(edge)
    bindings = {}
    for label, occurrences in groups.items():
        if not label or label in source_predicates:
            continue
        if not all((edge[":START_ID"], edge[":END_ID"]) in ev_pairs for edge in occurrences):
            continue
        bindings[label] = {"label": label, "deterministic_concept": label,
            "origin_kind": "structural_relation_label_retention",
            "edges": deepcopy(occurrences), "EV_derivations": [
                {"edge": deepcopy(edge), "native_EV_items": deepcopy(ev_pairs[(edge[":START_ID"], edge[":END_ID"])])}
                for edge in occurrences], "source_predicate_collision": False,
            "claim": "Retain a converter-derived technical relation by native occurrence provenance; no semantic ontology gain"}
    return bindings


def source_relation_bindings(native, edges, clean_text, vv_resolver=None, ee_resolver=None):
    """Remove predicate abstraction only for labels with complete native provenance."""
    source_occurrences = {}
    if vv_resolver is not None and (vv_resolver.get("status") != "resolved" or
            vv_resolver.get("resolved_output") != native["event_relation_dict"]):
        raise ValueError("Native VV resolver provenance differs")
    if ee_resolver is not None and (ee_resolver.get("status") != "resolved" or
            ee_resolver.get("resolved_output") != native["entity_relation_dict"]):
        raise ValueError("Native EE resolver provenance differs")
    for category in ("entity_relation_dict", "event_relation_dict"):
        for index, item in enumerate(native[category]):
            if not isinstance(item, dict) or any(not isinstance(item.get(k), str) for k in ("Head", "Relation", "Tail")):
                continue
            triple = tuple(clean_text(item[k]) for k in ("Head", "Relation", "Tail"))
            evidence = {"origin_kind": "source_relation", "native_category": category, "native_index": index,
                "native_item": deepcopy(item), "native_validated_output": native.get(category.replace("_dict", "_output"))}
            if category == "event_relation_dict" and vv_resolver is not None:
                evidence["VV_id_parsed_item"] = deepcopy(vv_resolver["id_parsed_output"][index])
                evidence["VV_resolved_item"] = deepcopy(vv_resolver["resolved_output"][index])
                evidence["VV_binding_sha256"] = vv_resolver["binding_sha256"]
            if category == "entity_relation_dict" and ee_resolver is not None:
                evidence["EE_id_parsed_item"] = deepcopy(ee_resolver["id_parsed_output"][index])
                evidence["EE_resolved_item"] = deepcopy(ee_resolver["resolved_output"][index])
                evidence["EE_binding_sha256"] = ee_resolver["binding_sha256"]
            source_occurrences.setdefault(triple, []).append(evidence)
    ev_occurrences = {}
    for event_index, item in enumerate(native["event_entity_dict"]):
        if not isinstance(item, dict) or not isinstance(item.get("Event"), str) or not isinstance(item.get("Entity"), list):
            continue
        for entity_index, entity in enumerate(item["Entity"]):
            if isinstance(entity, str):
                pair = (clean_text(item["Event"]), clean_text(entity))
                ev_occurrences.setdefault(pair, []).append({"origin_kind": "EV_derived",
                    "event_entity_index": event_index, "entity_index": entity_index,
                    "original_event": item["Event"], "original_entity": entity})
    groups = {}
    for edge in edges:
        groups.setdefault(edge["relation"], []).append(edge)
    source_labels = {triple[1] for triple in source_occurrences}
    bindings = {}
    for label, occurrences in groups.items():
        if not label or label not in source_labels:
            continue
        proven, collision, rejected = [], False, False
        for edge in occurrences:
            triple = (edge[":START_ID"], edge["relation"], edge[":END_ID"])
            pair = (edge[":START_ID"], edge[":END_ID"])
            if triple in source_occurrences:
                collision = collision or pair in ev_occurrences
                proven.append({"edge": deepcopy(edge), "origin_kind": "source_relation",
                    "native_source_items": deepcopy(source_occurrences[triple]),
                    "also_matches_native_EV_pair": pair in ev_occurrences,
                    "native_EV_items": deepcopy(ev_occurrences.get(pair, []))})
            elif pair in ev_occurrences:
                collision = True
                proven.append({"edge": deepcopy(edge), "origin_kind": "EV_derived",
                    "native_EV_items": deepcopy(ev_occurrences[pair])})
            else:
                rejected = True
                break
        if rejected or not any(item["origin_kind"] == "source_relation" for item in proven):
            continue
        bindings[label] = {"label": label, "deterministic_concept": label,
            "origin_kind": "source_relation_label_retention", "edges": deepcopy(occurrences),
            "occurrence_provenance": proven, "source_structural_label_collision": collision,
            "claim": "Remove semantic predicate abstraction for verified native source-origin labels. Identity retention is not an ontology improvement"}
    return bindings


def original_relation_item(messages, template):
    """Invert the exact native template substitution, with no naming heuristic."""
    if template is None or template.count("[RELATION]") != 1 or len(messages) != 2:
        return None
    if messages[0] != {"role": "system", "content": "You are a helpful AI assistant."} or messages[1].get("role") != "user":
        return None
    prefix, suffix = template.split("[RELATION]")
    text = messages[1].get("content")
    if not isinstance(text, str) or not text.startswith(prefix) or not text.endswith(suffix):
        return None
    label = text[len(prefix):len(text) - len(suffix) if suffix else len(text)]
    return label if text == template.replace("[RELATION]", label) else None


def event_id_binding(ev_items):
    """Bind actual EV output occurrences to technical IDs without semantic merging."""
    rows, seen = [], set()
    for item in ev_items:
        if not isinstance(item, dict) or not isinstance(item.get("Event"), str) or not item["Event"]:
            raise ValueError("EV event identity is unresolved")
        event = item["Event"]
        if event in seen:
            raise ValueError("Duplicate EV labels cannot identify distinct occurrences")
        seen.add(event)
        rows.append({"id": f"e{len(rows) + 1}", "event": event})
    return rows


def entity_id_binding(ev_items):
    """Narrow actual-EV catalog, preserving every participant string and occurrence.

    Repeated labels are unresolved rather than treated as proof of shared
    identity. No case, article, word, language or semantic normalization occurs.
    """
    rows, seen = [], set()
    for event_index, item in enumerate(ev_items):
        if not isinstance(item, dict) or not isinstance(item.get("Entity"), list):
            raise ValueError("EV participant catalog is unresolved")
        for entity_index, entity in enumerate(item["Entity"]):
            if not isinstance(entity, str) or not entity:
                raise ValueError("EV participant catalog contains an invalid label")
            if entity in seen:
                raise ValueError("Repeated EV participant labels do not establish shared referent identity")
            seen.add(entity)
            rows.append({"id": f"c{len(rows) + 1}", "entity": entity,
                "event_index": event_index, "entity_index": entity_index})
    if not rows:
        raise ValueError("Empty EV participant catalog cannot support the strict EE binding condition")
    return rows


def validate_entity_id_materialization(binding, ev_items, clean_text, sanitize_xml_string):
    """Reject native CSV/XML format collisions, without semantic name matching."""
    event_labels = {sanitize_xml_string(clean_text(item["Event"])) for item in ev_items
        if isinstance(item, dict) and isinstance(item.get("Event"), str)}
    seen, projected = {}, []
    for item in binding:
        cleaned = clean_text(item["entity"])
        materialized = sanitize_xml_string(cleaned)
        if not materialized:
            raise ValueError("Participant label is lost under native CSV/XML formatting")
        if materialized in seen and seen[materialized] != item["id"]:
            raise ValueError("Distinct participant IDs collapse under native CSV/XML formatting")
        if materialized in event_labels:
            raise ValueError("Participant label collides with an actual event label under native formatting")
        seen[materialized] = item["id"]
        projected.append({"id": item["id"], "native_participant": item["entity"],
            "native_CSV_label": cleaned, "native_graph_label": materialized})
    return {"format_collision_free": True, "materialized_participants": projected,
        "claim": "Native CSV cleaning and XML sanitation only; no semantic identity or naming heuristic"}


def resolve_ee_entity_ids(id_items, binding):
    """Resolve exact known participant IDs, never drop unknown EE claims."""
    identities = {row["id"]: row["entity"] for row in binding}
    if not identities or len(identities) != len(binding):
        raise ValueError("EE participant ID binding is empty or ambiguous")
    resolved = []
    for item in id_items:
        if not isinstance(item, dict) or item.get("Head") not in identities or item.get("Tail") not in identities:
            raise ValueError("EE endpoint is not a known participant ID; claim remains unresolved")
        row = deepcopy(item)
        row["Head"], row["Tail"] = identities[item["Head"]], identities[item["Tail"]]
        resolved.append(row)
    return resolved


def participant_occurrence_catalog(ev_items):
    """Actual EV slots with event context; repeated labels are not identity claims."""
    rows = []
    for event_index, item in enumerate(ev_items):
        if not isinstance(item, dict) or not isinstance(item.get("Event"), str) or not isinstance(item.get("Entity"), list):
            raise ValueError("EV participant occurrence catalog is unresolved")
        for entity_index, entity in enumerate(item["Entity"]):
            if not isinstance(entity, str) or not entity:
                raise ValueError("EV participant occurrence contains an invalid label")
            rows.append({"id": f"c{len(rows) + 1}", "entity": entity, "event": item["Event"],
                "event_index": event_index, "entity_index": entity_index})
    if not rows:
        raise ValueError("Empty EV participant catalog cannot support the partition condition")
    return rows


def decode_participant_partition(text, catalog, ev_items, clean_text, sanitize_xml_string):
    """Strict transport decoder before the unchanged native semantic EE parser.

    The model's complete partition is classified in its existing EE call.
    Labels are restored only from the chosen actual EV occurrence. No lexical
    identity rule is applied, and no producer record is silently discarded.
    """
    records = strict(text)
    if not isinstance(records, list):
        raise ValueError("Partition producer output must be a strict JSON array")
    identities = {r["id"]: r for r in catalog}
    mapping, controls, semantics, semantic_indices = {}, [], [], []
    for index, item in enumerate(records):
        if not isinstance(item, dict) or set(item) != {"Head", "Relation", "Tail"} or any(not isinstance(v, str) for v in item.values()):
            raise ValueError("Partition producer record must contain exactly three native string fields")
        if item["Relation"] == PARTICIPANT_BINDING_RELATION:
            if item["Head"] not in identities or item["Tail"] not in identities:
                raise ValueError("Participant binding refers to an unknown occurrence ID")
            if item["Head"] in mapping:
                raise ValueError("Duplicate participant binding Head before native deduplication")
            mapping[item["Head"]] = item["Tail"]
            controls.append({"producer_record_index": index, "record": deepcopy(item), "origin_kind": "participant_identity_protocol"})
        else:
            if item["Head"] not in identities or item["Tail"] not in identities:
                raise ValueError("Semantic EE endpoint is not a known occurrence ID; claim remains unresolved")
            semantics.append(deepcopy(item)); semantic_indices.append(index)
    if set(mapping) != set(identities):
        raise ValueError("Participant partition does not cover every actual EV occurrence exactly once")
    if any(mapping[target] != target for target in mapping.values()):
        raise ValueError("Participant partition requires direct canonical self-roots; chains or cycles are unresolved")
    canonical_ids = [key for key in identities if mapping[key] == key]
    canonical_catalog = [deepcopy(identities[key]) for key in canonical_ids]
    materialization = validate_entity_id_materialization(canonical_catalog, ev_items, clean_text, sanitize_xml_string)
    resolved_catalog, rebound_ev = [], deepcopy(ev_items)
    for item in catalog:
        resolved = deepcopy(item)
        resolved["entity"] = identities[mapping[item["id"]]]["entity"]
        resolved_catalog.append(resolved)
        rebound_ev[item["event_index"]]["Entity"][item["entity_index"]] = resolved["entity"]
    return {"status": "resolved", "raw_model_output": text, "producer_records": deepcopy(records),
        "binding_records": controls, "semantic_record_indices": semantic_indices, "semantic_id_records": semantics,
        "occurrence_to_canonical_id": mapping, "canonical_catalog": canonical_catalog,
        "resolved_occurrence_catalog": resolved_catalog, "original_native_EV_items": deepcopy(ev_items),
        "rebound_native_EV_items": rebound_ev, "materialization_validation": materialization,
        "native_parser_input": canonical(semantics).decode("utf-8"),
        "claim": "Source-grounded coreference partition requested in the same EE call. Technical validation is not independent proof of referent truth; closed EV catalog recall limit remains."}


def resolve_vv_event_ids(id_items, binding):
    """Resolve only exact known IDs, preserving native relation fields unchanged."""
    identities = {row["id"]: row["event"] for row in binding}
    if len(identities) != len(binding):
        raise ValueError("Event ID binding is ambiguous")
    resolved = []
    for item in id_items:
        if not isinstance(item, dict) or item.get("Head") not in identities or item.get("Tail") not in identities:
            raise ValueError("VV output refers to unknown event IDs")
        row = deepcopy(item)
        row["Head"], row["Tail"] = identities[item["Head"]], identities[item["Tail"]]
        resolved.append(row)
    return resolved


def vv_direction_messages(messages, category, enabled, temporal_coverage=False):
    """Append only a generic definition of the existing VV relation grammar."""
    actual = deepcopy(messages)
    if enabled and category == "event_relation":
        actual[0][-1]["content"] += "\n\n" + VV_DIRECTION_CONTRACT
        if temporal_coverage:
            actual[0][-1]["content"] += "\n\n" + VV_TEMPORAL_COVERAGE_CONTRACT
    return actual


def vv_full_predicate_messages(messages, category, enabled):
    """Ask for complete source-semantic predicates only in VV, without a label list."""
    actual = deepcopy(messages)
    if enabled and category == "event_relation":
        actual[0][-1]["content"] += "\n\n" + VV_FULL_PREDICATE_CONTRACT
    return actual


def vv_reference_messages(messages, source_text, event_catalog):
    """Replace only the VV user body with reference semantics and actual data."""
    actual = deepcopy(messages)
    if len(actual) != 1 or not actual[0] or actual[0][-1].get("role") != "user":
        raise ValueError("Reference VV prompt requires one native conversation ending in a user message")
    actual[0][-1]["content"] = (VV_REFERENCE_PROMPT + "\n\nORIGINAL SOURCE:\n" + source_text
        + "\n\nACTUAL EVENT CATALOG:\n" + canonical(event_catalog).decode("utf-8"))
    return actual


def ee_scope_messages(messages, category, enabled, coverage=False):
    """Append only a generic source and occurrence scope constraint to EE."""
    actual = deepcopy(messages)
    if enabled and category == "entity_relation":
        actual[0][-1]["content"] += "\n\n" + EE_SCOPE_CONTRACT
    if coverage and category == "entity_relation":
        actual[0][-1]["content"] += "\n\n" + EE_COVERAGE_CONTRACT
    return actual


def partition_referent_messages(messages, category, enabled):
    """A generic referent grouping instruction only for the partition EE call."""
    actual = deepcopy(messages)
    if enabled and category == "entity_relation":
        actual[0][-1]["content"] += "\n\n" + PARTITION_REFERENT_CONTRACT
    return actual


class DispatchHalt(BaseException):
    """Bypass native Exception fallbacks and preserve a failed execution as failed."""


class OnceRuntime:
    def __init__(self, output, token, model, timeout, *, wire=institutional.institutional_wire,
                 concept_source_context=None, concept_edge_context=None, concept_direction_contract=False,
                 preserve_structural_relations=False, preserve_source_relations=False):
        self.output, self.token, self.model = Path(output), token, model
        self.timeout, self.wire = timeout, wire
        self.concept_source_context = concept_source_context
        self.concept_edge_context = concept_edge_context
        self.concept_direction_contract = concept_direction_contract
        self.preserve_structural_relations = preserve_structural_relations
        self.preserve_source_relations = preserve_source_relations
        self.structural_relations, self.original_relation_template = {}, None
        self.source_relations = {}
        self.deterministic_concepts = []
        if concept_source_context is not None and concept_edge_context is not None:
            raise ValueError("Choose one concept context condition")
        self.phase, self.seen, self.receipts = None, set(), []
        self.retry_blocked = False
        self.ee_partition_decoder, self.ee_partition_result = None, None

    def generate(self, messages, parameters):
        original_messages = deepcopy(messages)
        if self.phase == "concept_induction" and (self.preserve_structural_relations or self.preserve_source_relations):
            label = original_relation_item(original_messages, self.original_relation_template)
            provenance = self.source_relations.get(label) if self.preserve_source_relations else None
            if provenance is None and self.preserve_structural_relations:
                provenance = self.structural_relations.get(label)
            if provenance is not None:
                item = {"original_native_messages": original_messages, "native_generation_kwargs": deepcopy(parameters),
                    "original_prompt_sha256": sha(canonical(original_messages)), "label": label,
                    "provenance": deepcopy(provenance), "origin_kind": provenance["origin_kind"], "returned_text": label,
                    "physical_POSTs": 0, "concept_context_or_direction_instructions_used": False}
                save_json(self.output / "deterministic_concepts" / f"{len(self.deterministic_concepts):04d}.json", item)
                self.deterministic_concepts.append(item)
                return label
        context_added = self.phase == "concept_induction" and self.concept_source_context is not None
        edge_context_added = self.phase == "concept_induction" and self.concept_edge_context is not None
        direction_contract_added = self.phase == "concept_induction" and self.concept_direction_contract
        if context_added or edge_context_added or direction_contract_added:
            messages = deepcopy(messages)
            if not messages or messages[-1].get("role") != "user":
                raise DispatchHalt("Original concept user message absent")
            if context_added:
                messages[-1]["content"] += "\n\nSOURCE CONTEXT:\n" + self.concept_source_context
            elif edge_context_added:
                messages[-1]["content"] += "\n\nDIRECTED GRAPH CONTEXT (head, relation, tail; do not reverse these roles):\n" + canonical(self.concept_edge_context).decode("utf-8")
            if direction_contract_added:
                messages[-1]["content"] += "\n\n" + CONCEPT_DIRECTION_CONTRACT
        identity = sha(canonical([self.phase, messages, parameters]))
        if identity in self.seen:
            self.retry_blocked = True
            save_json(self.output / "native_retry_blocked.json", {"phase": self.phase, "request_identity": identity,
                "additional_POSTs": 0, "reason": "Native validator requested repetition; one-shot condition stops here"})
            raise DispatchHalt("native_validation_retry_blocked")
        self.seen.add(identity)
        ordinal = len(self.receipts)
        folder = self.output / "calls" / f"{ordinal:04d}"
        payload = {"payload": {"model": self.model, "messages": [
            {"role": m["role"], "content": {"text": m["content"]}} for m in messages]}}
        raw_request = canonical(payload)
        save_json(folder / "native_intent.json", {"phase": self.phase, "messages": deepcopy(messages),
            "original_native_messages": original_messages, "concept_source_context_added": context_added,
            "concept_edge_context_added": edge_context_added,
            "concept_edge_context_sha256": sha(canonical(self.concept_edge_context)) if edge_context_added else None,
            "concept_direction_contract_added": direction_contract_added,
            "concept_direction_contract_sha256": sha(CONCEPT_DIRECTION_CONTRACT.encode()) if direction_contract_added else None,
            "native_generation_kwargs": deepcopy(parameters), "prompt_sha256": sha(canonical(messages)),
            "wire_sha256": sha(raw_request), "sampling_and_caps_on_wire": None})
        save(folder / "request.json", raw_request)
        receipt = {"ordinal": ordinal, "phase": self.phase, "physical_dispatch_performed": False,
            "unknown_execution": False, "institutional_completion_confirmed": False,
            "http_status": None, "HTTP_body_complete": False, "response_bytes": None,
            "response_sha256": None, "raw_body_saved": False, "backend_output_token_cap": None,
            "effective_sampling": None, "actual_cost_USD": None, "provider_seconds": None,
            "provider_usage": None, "HTTP_client_seconds": None, "error_class": None}
        self.receipts.append(receipt)
        began = time.monotonic()
        raw, headers = b"", {}
        try:
            receipt["physical_dispatch_performed"] = True
            receipt["unknown_execution"] = True
            save_json(folder / "dispatch_started.json", {"physical_POSTs": 1, "request_sha256": sha(raw_request)})
            response = self.wire(raw_request, token=self.token, timeout=self.timeout)
            if type(response) is not institutional.WireResponse:
                raise ValueError("Unexpected institutional response type")
            raw, headers = response.body, response.headers
            receipt.update(http_status=response.status, HTTP_body_complete=response.complete)
            value, metadata, usage = capture.capture_response(raw, headers, self.token, SimpleNamespace(strict_json=strict))
            receipt.update(response_metadata=metadata, provider_usage=usage)
            content = value.get("content") if isinstance(value, dict) else None
            text = content.get("text") if isinstance(content, dict) else content
            confirmed = (response.status == 200 and response.complete and isinstance(value, dict)
                and value.get("success") is True and isinstance(text, str) and not metadata["credential_reflection"])
            if not confirmed:
                raise ValueError("Institutional completion unconfirmed")
            receipt.update(institutional_completion_confirmed=True, unknown_execution=False)
            if self.phase == "entity_relation" and self.ee_partition_decoder is not None:
                try:
                    self.ee_partition_result = self.ee_partition_decoder(text)
                    save_json(self.output / "ee_entity_partition_decoder.json", self.ee_partition_result)
                    return self.ee_partition_result["native_parser_input"]
                except Exception as error:
                    receipt["protocol_decoder_error"] = type(error).__name__
                    save_json(self.output / "ee_entity_partition_decoder.json", {"status": "rejected",
                        "raw_model_output": text, "reason": str(error), "additional_POSTs": 0, "VV_POSTs": 0})
                    raise DispatchHalt("participant_partition_protocol_rejected") from None
            return text
        except institutional.WireInterrupted as error:
            raw, headers = error.raw, error.headers
            receipt.update(http_status=error.status, error_class=type(error).__name__)
            raise DispatchHalt("unknown_execution") from None
        except Exception as error:
            receipt["error_class"] = type(error).__name__
            raise DispatchHalt("unknown_execution") from None
        finally:
            receipt["HTTP_client_seconds"] = time.monotonic() - began
            receipt.update(response_bytes=len(raw), response_sha256=sha(raw))
            # A reflected credential is never written back into an artifact.
            if self.token.encode() not in raw:
                save(folder / "response.raw", raw)
                receipt["raw_body_saved"] = True
            else:
                receipt["response_omitted_due_to_credential_reflection"] = True
            save_json(folder / "receipt.json", receipt)


def pipeline_client(runtime):
    # Native LLMGenerator selects its unchanged Pipeline branch by isinstance.
    from transformers.pipelines import Pipeline
    class OncePipeline(Pipeline):
        def __init__(self):
            self.tokenizer, self.model = None, None
        def _sanitize_parameters(self, **kwargs):
            raise NotImplementedError
        def preprocess(self, inputs, **kwargs):
            raise NotImplementedError
        def _forward(self, inputs, **kwargs):
            raise NotImplementedError
        def postprocess(self, outputs, **kwargs):
            raise NotImplementedError
        def __call__(self, batch_messages, **kwargs):
            return [[{"generated_text": runtime.generate(messages, kwargs)}] for messages in batch_messages]
    return OncePipeline()


def selected_fixture(path, fixture_id):
    raw = unlinked(path).read_bytes()
    value = strict(raw)
    rows = value.get("fixtures") if isinstance(value, dict) else value
    if not isinstance(rows, list):
        raise ValueError("Fixture file requires a fixtures list")
    matches = [r for r in rows if isinstance(r, dict) and r.get("id") == fixture_id]
    if len(matches) != 1 or not isinstance(matches[0].get("text"), str) or not matches[0]["text"].strip():
        raise ValueError("One nonempty source fixture is required")
    # Only these fields are projected. Reference/expected fields are ignored.
    return {"id": fixture_id, "text": matches[0]["text"], "metadata": {"lang": "en"}}, sha(raw)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixtures", required=True, type=Path)
    p.add_argument("--fixture-id", "--fixture", dest="fixture_id", required=True)
    p.add_argument("--source", type=Path, default=ROOT / "Tools/ReferenceRepos/benchmark_autoschemakg_original")
    p.add_argument("--env", type=Path, default=ROOT / ".env")
    p.add_argument("--model", default="gpt-4.1")
    p.add_argument("--arm", choices=("original", "variant"), default="original")
    p.add_argument("--category", choices=tuple(CATEGORIES))
    p.add_argument("--constraint", choices=tuple(CONSTRAINTS))
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--repetitions", type=int, default=3)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--extraction-only", action="store_true")
    mode.add_argument("--with-schema", action="store_true")
    p.add_argument("--schema-from", type=Path, help="Reuse a completed matching extraction run; no extraction POSTs")
    context = p.add_mutually_exclusive_group()
    context.add_argument("--concept-source-context", action="store_true",
        help="Append exact source text only to original concept messages; separate data-context condition")
    context.add_argument("--concept-edge-context", action="store_true",
        help="Append actual directed native graph edges only to concept messages; separate data-context condition")
    p.add_argument("--concept-direction-contract", action="store_true",
        help="Append a generic direction-preserving abstraction instruction only to concept messages")
    p.add_argument("--preserve-structural-relations", action="store_true",
        help="Keep verified converter-derived EV-only relation labels without a model call")
    p.add_argument("--bind-vv-event-ids", action="store_true",
        help="Give VV the actual prior EV occurrence IDs, then resolve exact known IDs to EV labels")
    p.add_argument("--preserve-source-relations", action="store_true",
        help="Remove semantic predicate abstraction for completely verified native source-origin labels")
    p.add_argument("--vv-direction-contract", action="store_true",
        help="Define existing causal Head/Tail relation directions only in the VV prompt")
    p.add_argument("--vv-temporal-coverage-contract", action="store_true",
        help="Clarify only in VV that the causal definitions retain the original temporal extraction task")
    p.add_argument("--vv-full-predicate-contract", action="store_true",
        help="Ask only VV for a complete unambiguous source-semantic predicate after event ID resolution")
    p.add_argument("--vv-reference-prompt", action="store_true",
        help="Replace only the VV user body with an event-reference task, original source and actual event catalog")
    p.add_argument("--ee-scope-contract", action="store_true",
        help="Constrain EE to source-affirmed relations without inventing unqualified event-participant dependencies")
    p.add_argument("--ee-coverage-contract", action="store_true",
        help="Clarify only in partition EE that technical bindings and event routing retain semantic entity claims")
    ee_binding_mode = p.add_mutually_exclusive_group()
    ee_binding_mode.add_argument("--bind-ee-entity-ids", action="store_true",
        help="Run EV first and bind EE endpoints to its exact participant IDs; closed-catalog diagnostic only")
    ee_binding_mode.add_argument("--partition-ee-entity-ids", action="store_true",
        help="Use the existing EE call to partition actual EV participant occurrences by source referent, then restore chosen native labels")
    p.add_argument("--partition-referent-contract", action="store_true",
        help="Add a generic source referent grouping instruction only to the partition EE prompt")
    p.add_argument("--timeout", type=float, default=90)
    args = p.parse_args(argv)
    if args.arm == "variant" and (not args.constraint or not args.category):
        p.error("Variant requires one generic constraint and one category")
    if args.arm == "original" and (args.constraint or args.category):
        p.error("Original arm has no prompt modification")
    if args.schema_from and not args.with_schema:
        p.error("--schema-from requires --with-schema")
    if args.partition_referent_contract and not args.partition_ee_entity_ids:
        p.error("--partition-referent-contract requires --partition-ee-entity-ids")
    if args.ee_coverage_contract and not args.partition_ee_entity_ids:
        p.error("--ee-coverage-contract requires --partition-ee-entity-ids")
    if args.vv_temporal_coverage_contract and not args.vv_direction_contract:
        p.error("--vv-temporal-coverage-contract requires --vv-direction-contract")
    if args.vv_full_predicate_contract and not args.bind_vv_event_ids:
        p.error("--vv-full-predicate-contract requires --bind-vv-event-ids")
    if args.vv_reference_prompt:
        if not args.bind_vv_event_ids or args.arm != "variant" or args.category != "VV" or args.constraint != "explicit_event_relations":
            p.error("--vv-reference-prompt requires --bind-vv-event-ids and the VV explicit_event_relations variant")
        if args.vv_direction_contract or args.vv_temporal_coverage_contract or args.vv_full_predicate_contract:
            p.error("--vv-reference-prompt is exclusive with the three other VV prompt contracts")
    if args.concept_source_context and not args.with_schema:
        p.error("--concept-source-context requires --with-schema")
    if args.concept_edge_context and not args.with_schema:
        p.error("--concept-edge-context requires --with-schema")
    if args.concept_direction_contract and not args.with_schema:
        p.error("--concept-direction-contract requires --with-schema")
    if args.preserve_structural_relations and not args.with_schema:
        p.error("--preserve-structural-relations requires --with-schema")
    if args.preserve_source_relations and not args.with_schema:
        p.error("--preserve-source-relations requires --with-schema")
    if not 1 <= args.repetitions <= 10 or not 0 < args.timeout <= institutional.HTTP_SECONDS:
        p.error("Require 1-10 repetitions and a positive HTTP timeout at most 90 seconds")
    output = unlinked(args.output)
    if output.exists():
        p.error("Output must be a new directory")
    fixture, fixture_file_sha = selected_fixture(args.fixtures, args.fixture_id)
    original = verify_source(args.source)
    output.mkdir(parents=True)
    runner_source = Path(__file__).read_bytes()
    save(output / "runner_source.py", runner_source)
    condition = {"protocol": PROTOCOL, "fixture_id": args.fixture_id, "fixture_file_sha256": fixture_file_sha,
        "source_text_sha256": sha(fixture["text"].encode()), "original_commit": original["commit"],
        "original_files": original["files"], "runner_sha256": sha(runner_source),
        "model": args.model, "provider": "HAWKI", "arm": args.arm, "category": args.category,
        "constraint": args.constraint, "constraint_text": CONSTRAINTS.get(args.constraint),
        "with_schema": args.with_schema, "schema_from": str(args.schema_from) if args.schema_from else None,
        "concept_context": args.concept_source_context,
        "concept_context_source_sha256": sha(fixture["text"].encode()) if args.concept_source_context else None,
        "concept_context_claim": "Additional original source data only in concept messages; separate context condition, not an isolated algorithm effect" if args.concept_source_context else None,
        "concept_edge_context": args.concept_edge_context,
        "concept_edge_context_hashes": "Recorded after native conversion in concept_edge_context_condition.json" if args.concept_edge_context else None,
        "concept_edge_context_claim": "Actual directed edge occurrences from the existing native graph added only to concept messages; separate data-context condition, not an isolated algorithm effect" if args.concept_edge_context else None,
        "concept_direction_contract": args.concept_direction_contract,
        "concept_direction_contract_text": CONCEPT_DIRECTION_CONTRACT if args.concept_direction_contract else None,
        "concept_direction_contract_sha256": sha(CONCEPT_DIRECTION_CONTRACT.encode()) if args.concept_direction_contract else None,
        "preserve_structural_relations": args.preserve_structural_relations,
        "structural_relation_claim": "Deterministic retention of converter-derived EV-only labels verified against native output, excluding source predicate collisions; format/provenance variant, no ontology quality gain" if args.preserve_structural_relations else None,
        "preserve_source_relations": args.preserve_source_relations,
        "source_relation_claim": "Explicit component-removal variant: omit semantic predicate abstraction for verified source-origin relations, retain exact labels, and continue original entity/event concepts. Identity retention is not an ontology improvement" if args.preserve_source_relations else None,
        "bind_vv_event_ids": args.bind_vv_event_ids,
        "vv_event_id_directive": VV_EVENT_ID_DIRECTIVE if args.bind_vv_event_ids else None,
        "vv_event_id_directive_sha256": sha(VV_EVENT_ID_DIRECTIVE.encode()) if args.bind_vv_event_ids else None,
        "vv_event_id_claim": "VV receives actual previously generated EV occurrences as technical IDs. Source-derived input addition and exact output binding, no semantic label matching or gold information" if args.bind_vv_event_ids else None,
        "vv_direction_contract": args.vv_direction_contract,
        "vv_direction_contract_text": VV_DIRECTION_CONTRACT if args.vv_direction_contract else None,
        "vv_direction_contract_sha256": sha(VV_DIRECTION_CONTRACT.encode()) if args.vv_direction_contract else None,
        "vv_temporal_coverage_contract": args.vv_temporal_coverage_contract,
        "vv_temporal_coverage_contract_text": VV_TEMPORAL_COVERAGE_CONTRACT if args.vv_temporal_coverage_contract else None,
        "vv_temporal_coverage_contract_sha256": sha(VV_TEMPORAL_COVERAGE_CONTRACT.encode()) if args.vv_temporal_coverage_contract else None,
        "vv_full_predicate_contract": args.vv_full_predicate_contract,
        "vv_full_predicate_contract_text": VV_FULL_PREDICATE_CONTRACT if args.vv_full_predicate_contract else None,
        "vv_full_predicate_contract_sha256": sha(VV_FULL_PREDICATE_CONTRACT.encode()) if args.vv_full_predicate_contract else None,
        "vv_full_predicate_contract_claim": "Separate Relation wording contract: complete source-semantic predicates instead of insufficient discourse connectors, with original string fields and parser. Not native label-style equivalence or an ontology quality gain" if args.vv_full_predicate_contract else None,
        "vv_reference_prompt": args.vv_reference_prompt,
        "vv_reference_prompt_template": VV_REFERENCE_PROMPT if args.vv_reference_prompt else None,
        "vv_reference_prompt_template_sha256": sha(VV_REFERENCE_PROMPT.encode()) if args.vv_reference_prompt else None,
        "vv_reference_prompt_claim": "Separate VV producer task using actual source-bound event references. Replace user body only; native System, three string fields, parser and resolver retained. Original and previous modified messages archived. No source quality, benchmark gain, prompt reduction or token/cost claim until measured" if args.vv_reference_prompt else None,
        "ee_scope_contract": args.ee_scope_contract,
        "ee_scope_contract_text": EE_SCOPE_CONTRACT if args.ee_scope_contract else None,
        "ee_scope_contract_sha256": sha(EE_SCOPE_CONTRACT.encode()) if args.ee_scope_contract else None,
        "ee_coverage_contract": args.ee_coverage_contract,
        "ee_coverage_contract_text": EE_COVERAGE_CONTRACT if args.ee_coverage_contract else None,
        "ee_coverage_contract_sha256": sha(EE_COVERAGE_CONTRACT.encode()) if args.ee_coverage_contract else None,
        "bind_ee_entity_ids": args.bind_ee_entity_ids,
        "extraction_execution_order": ["event_entity", "entity_relation", "event_relation"] if args.bind_ee_entity_ids or args.partition_ee_entity_ids else ["entity_relation", "event_entity", "event_relation"],
        "ee_entity_id_directive": EE_ENTITY_ID_DIRECTIVE if args.bind_ee_entity_ids else None,
        "ee_entity_id_directive_sha256": sha(EE_ENTITY_ID_DIRECTIVE.encode()) if args.bind_ee_entity_ids else None,
        "ee_entity_id_claim": "Narrow closed-catalog EV-first contrast. Exact actual EV participant strings are restored from technical IDs, without article or language heuristics. Missing participants, unknown endpoints and repeated participant labels halt without dropping claims. EE recall is limited by EV catalog coverage; no all-source-entity or shared-referent guarantee" if args.bind_ee_entity_ids else None,
        "ee_entity_catalog_identity_policy": "Label-based EV occurrence catalog with position provenance. Repeated literal labels require identity evidence and are unresolved, without asserting either same or different referents. Native CSV/XML format collisions are rejected before EE" if args.bind_ee_entity_ids else None,
        "partition_ee_entity_ids": args.partition_ee_entity_ids,
        "ee_partition_directive": EE_PARTITION_DIRECTIVE if args.partition_ee_entity_ids else None,
        "ee_partition_directive_sha256": sha(EE_PARTITION_DIRECTIVE.encode()) if args.partition_ee_entity_ids else None,
        "ee_partition_reserved_relation": PARTICIPANT_BINDING_RELATION if args.partition_ee_entity_ids else None,
        "ee_partition_claim": "Separate output protocol: same existing EE call classifies source referent identity over actual EV participant occurrences, then supplies EE claims. Strict decoder preserves every producer record and sends only semantic ID triples to unchanged native parser. Labels restored from actual selected EV slots without equal-label merging. Closed catalog limits EE recall; no arbitrary-coreference or benchmark guarantee" if args.partition_ee_entity_ids else None,
        "ee_partition_contract_sha256": sha(Path(__file__).with_name("identity_partition_contract_v1.json").read_bytes()) if args.partition_ee_entity_ids else None,
        "partition_referent_contract": args.partition_referent_contract,
        "partition_referent_contract_text": PARTITION_REFERENT_CONTRACT if args.partition_referent_contract else None,
        "partition_referent_contract_sha256": sha(PARTITION_REFERENT_CONTRACT.encode()) if args.partition_referent_contract else None,
        "repetitions": args.repetitions, "native_sampling_requested": {"temperature": .7, "do_sample": True},
        "native_extraction_cap_requested": 2048, "native_concept_cap_requested": 8192,
        "effective_sampling": None, "backend_output_cap": None, "provider_model_revision": None,
        "physical_retries": 0, "native_validation_retries_blocked": True,
        "claim_limit": "Development diagnosis. Native prompts/parsers with a new institutional provider condition; no paper-model sampling equivalence, independent annotation, transfer or benchmark superiority claim."}
    save_json(output / "condition.json", condition)
    save_json(output / "source_input.json", fixture)
    summary = {"protocol": PROTOCOL, "status": "running", "complete": False, "repetitions_completed": 0,
        "physical_POSTs": 0, "unknown_executions": 0, "runs": [], "failure_class": None}
    try:
        if args.partition_ee_entity_ids and PARTICIPANT_BINDING_RELATION in fixture["text"]:
            raise ValueError("Source text contains the reserved participant binding relation; protocol/source collision unresolved")
        prior = None
        if args.schema_from:
            prior_root = unlinked(args.schema_from)
            prior = strict((prior_root / "condition.json").read_bytes())
            prior_summary = strict((prior_root / "summary.json").read_bytes())
            if not prior_summary.get("complete") or any(prior.get(k) != condition.get(k) for k in
                    ("protocol", "fixture_id", "fixture_file_sha256", "source_text_sha256", "original_commit", "original_files", "model", "arm", "category", "constraint", "repetitions")):
                raise ValueError("Saved extraction condition differs or is incomplete")
            if prior.get("bind_vv_event_ids", False) != args.bind_vv_event_ids:
                raise ValueError("Saved extraction event ID binding condition differs")
            if prior.get("vv_direction_contract", False) != args.vv_direction_contract:
                raise ValueError("Saved extraction VV direction condition differs")
            if prior.get("vv_temporal_coverage_contract", False) != args.vv_temporal_coverage_contract:
                raise ValueError("Saved extraction VV temporal coverage condition differs")
            if prior.get("vv_full_predicate_contract", False) != args.vv_full_predicate_contract:
                raise ValueError("Saved extraction VV full predicate condition differs")
            if prior.get("vv_reference_prompt", False) != args.vv_reference_prompt:
                raise ValueError("Saved extraction VV reference prompt condition differs")
            if prior.get("ee_scope_contract", False) != args.ee_scope_contract:
                raise ValueError("Saved extraction EE scope condition differs")
            if prior.get("ee_coverage_contract", False) != args.ee_coverage_contract:
                raise ValueError("Saved extraction EE coverage condition differs")
            if prior.get("bind_ee_entity_ids", False) != args.bind_ee_entity_ids:
                raise ValueError("Saved extraction EE participant ID binding condition differs")
            if prior.get("partition_ee_entity_ids", False) != args.partition_ee_entity_ids:
                raise ValueError("Saved extraction EE participant partition condition differs")
            if prior.get("partition_referent_contract", False) != args.partition_referent_contract:
                raise ValueError("Saved extraction partition referent prompt condition differs")
            save_json(output / "reused_extraction_binding.json", {"path": str(prior_root),
                "condition_sha256": sha((prior_root / "condition.json").read_bytes()),
                "summary_sha256": sha((prior_root / "summary.json").read_bytes())})
        token = probe.load_token(unlinked(args.env))
        with (output / "native_execution.log").open("x", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log), verified_source_imports(args.source):
            from atlas_rag.kg_construction.triple_extraction import KnowledgeGraphExtractor, DatasetProcessor, CustomDataLoader
            from atlas_rag.kg_construction.triple_config import ProcessingConfig
            from atlas_rag.llm_generator import LLMGenerator
            from atlas_rag.llm_generator.prompt.triple_extraction_prompt import CONCEPT_INSTRUCTIONS
            from atlas_rag.kg_construction.utils.json_processing.json_to_csv import clean_text
            from atlas_rag.kg_construction.utils.csv_processing.csv_to_graphml import sanitize_xml_string
            for repetition in range(1, args.repetitions + 1):
                rep = output / f"r{repetition}"
                rep.mkdir()
                runtime = OnceRuntime(rep, token, args.model, args.timeout,
                    concept_source_context=fixture["text"] if args.concept_source_context else None,
                    concept_direction_contract=args.concept_direction_contract,
                    preserve_structural_relations=args.preserve_structural_relations,
                    preserve_source_relations=args.preserve_source_relations)
                generator = LLMGenerator(pipeline_client(runtime), model_name=args.model)
                config = ProcessingConfig(model_path=args.model, data_directory=str(rep), filename_pattern="toy",
                    batch_size_triple=3, batch_size_concept=16, output_directory=str(rep),
                    max_new_tokens=2048, max_workers=3, remove_doc_spaces=True, record=False)
                extractor = KnowledgeGraphExtractor(generator, config)
                row = {"repetition": repetition, "complete": False, "physical_POSTs": 0, "unknown_executions": 0,
                    "native_retry_blocked": False, "categories": {}, "schema_complete": False}
                summary["runs"].append(row)
                try:
                    if prior is None:
                        processor = DatasetProcessor(config, extractor.prompt_instructions, extractor.result_schema)
                        loader = CustomDataLoader([fixture], processor, extractor.prompt_instructions, extractor.result_schema)
                        messages, ids, texts, metadata = next(iter(loader))
                        llm_outputs, parsed_outputs, keys = [], [], list(messages)
                        if (args.bind_vv_event_ids or args.bind_ee_entity_ids or args.partition_ee_entity_ids) and keys != ["entity_relation", "event_entity", "event_relation"]:
                            raise ValueError("Native EE/EV/VV execution order differs")
                        execution_order = condition["extraction_execution_order"] if args.bind_ee_entity_ids or args.partition_ee_entity_ids else keys
                        row["extraction_execution_order"] = execution_order
                        parsed_by_category = {}
                        for key in execution_order:
                            actual = deepcopy(messages[key])
                            if args.arm == "variant" and key == CATEGORIES[args.category]:
                                actual[0][-1]["content"] += "\n\n" + CONSTRAINTS[args.constraint]
                            actual = ee_scope_messages(actual, key, args.ee_scope_contract, args.ee_coverage_contract)
                            actual = vv_direction_messages(actual, key, args.vv_direction_contract, args.vv_temporal_coverage_contract)
                            actual = vv_full_predicate_messages(actual, key, args.vv_full_predicate_contract)
                            entity_binding = None
                            if args.bind_ee_entity_ids and key == "entity_relation":
                                try:
                                    entity_binding = entity_id_binding(parsed_by_category["event_entity"])
                                    materialization = validate_entity_id_materialization(entity_binding,
                                        parsed_by_category["event_entity"], clean_text, sanitize_xml_string)
                                except ValueError as error:
                                    save_json(rep / "ee_entity_id_binding_failure.json", {"status": "unresolved",
                                        "native_EV_items": deepcopy(parsed_by_category["event_entity"]),
                                        "reason": str(error), "EE_POSTs": 0, "VV_POSTs": 0})
                                    raise
                                row["ee_entity_binding_sha256"] = sha(canonical(entity_binding))
                                save_json(rep / "ee_entity_id_binding.json", {"binding": entity_binding,
                                    "binding_sha256": row["ee_entity_binding_sha256"],
                                    "native_EV_items": deepcopy(parsed_by_category["event_entity"]),
                                    "native_EV_items_sha256": sha(canonical(parsed_by_category["event_entity"])),
                                    "original_native_messages": deepcopy(messages[key]), "messages_before_binding": deepcopy(actual),
                                    "materialization_validation": materialization})
                                actual[0][-1]["content"] += "\n\nACTUAL EV PARTICIPANT IDS:\n" + canonical(entity_binding).decode("utf-8") + "\n\n" + EE_ENTITY_ID_DIRECTIVE
                            if args.partition_ee_entity_ids and key == "entity_relation":
                                try:
                                    catalog = participant_occurrence_catalog(parsed_by_category["event_entity"])
                                except ValueError as error:
                                    save_json(rep / "ee_entity_partition_binding_failure.json", {"status": "unresolved",
                                        "native_EV_items": deepcopy(parsed_by_category["event_entity"]),
                                        "reason": str(error), "EE_POSTs": 0, "VV_POSTs": 0})
                                    raise
                                row["ee_entity_binding_sha256"] = sha(canonical(catalog))
                                save_json(rep / "ee_entity_partition_binding.json", {"binding": catalog,
                                    "binding_sha256": row["ee_entity_binding_sha256"],
                                    "native_EV_items": deepcopy(parsed_by_category["event_entity"]),
                                    "native_EV_items_sha256": sha(canonical(parsed_by_category["event_entity"])),
                                    "original_native_messages": deepcopy(messages[key]), "messages_before_binding": deepcopy(actual)})
                                ev_before_partition = deepcopy(parsed_by_category["event_entity"])
                                runtime.ee_partition_decoder = lambda text: decode_participant_partition(text,
                                    catalog, ev_before_partition, clean_text, sanitize_xml_string)
                                actual[0][-1]["content"] += "\n\nACTUAL EV PARTICIPANT OCCURRENCES:\n" + canonical(catalog).decode("utf-8")
                                actual = partition_referent_messages(actual, key, args.partition_referent_contract)
                                actual[0][-1]["content"] += "\n\n" + EE_PARTITION_DIRECTIVE
                            binding = None
                            if args.bind_vv_event_ids and key == "event_relation":
                                try:
                                    binding = event_id_binding(parsed_by_category["event_entity"])
                                except ValueError as error:
                                    save_json(rep / "vv_event_id_binding_failure.json", {"status": "unresolved",
                                        "native_EV_items": deepcopy(parsed_by_category["event_entity"]),
                                        "reason": str(error), "VV_POSTs": 0})
                                    raise
                                row["vv_event_binding_sha256"] = sha(canonical(binding))
                                actual[0][-1]["content"] += "\n\nACTUAL EV EVENT IDS:\n" + canonical(binding).decode("utf-8") + "\n\n" + VV_EVENT_ID_DIRECTIVE
                                if args.vv_reference_prompt:
                                    old_modified = deepcopy(actual)
                                    actual = vv_reference_messages(actual, fixture["text"], binding)
                                    save_json(rep / "vv_reference_prompt_binding.json", {
                                        "original_native_messages": deepcopy(messages[key]), "old_modified_messages": old_modified,
                                        "actual_messages": deepcopy(actual), "template": VV_REFERENCE_PROMPT,
                                        "template_sha256": sha(VV_REFERENCE_PROMPT.encode()),
                                        "source_text": fixture["text"], "source_text_sha256": sha(fixture["text"].encode()),
                                        "event_catalog": deepcopy(binding), "event_catalog_sha256": sha(canonical(binding)),
                                        "original_prompt_sha256": sha(canonical(messages[key][0])),
                                        "old_modified_prompt_sha256": sha(canonical(old_modified[0])),
                                        "actual_prompt_sha256": sha(canonical(actual[0])),
                                        "original_user_characters": len(messages[key][0][-1]["content"]),
                                        "old_modified_user_characters": len(old_modified[0][-1]["content"]),
                                        "actual_user_characters": len(actual[0][-1]["content"]),
                                        "claim": "New event-reference VV producer task. Actual source and actual EV catalog only; native System/schema/parser/resolver unchanged."})
                                save_json(rep / "vv_event_id_binding.json", {"binding": binding,
                                    "binding_sha256": row["vv_event_binding_sha256"],
                                    "native_EV_items": deepcopy(parsed_by_category["event_entity"]),
                                    "native_EV_items_sha256": sha(canonical(parsed_by_category["event_entity"]))})
                            runtime.phase = key
                            raw_outputs, parsed = extractor.process_stage(actual, extractor.result_schema[key])
                            if args.partition_ee_entity_ids and key == "entity_relation":
                                partition = runtime.ee_partition_result
                                if partition is None or partition["status"] != "resolved":
                                    raise ValueError("Participant partition decoder did not produce a validated result")
                                entity_binding = partition["resolved_occurrence_catalog"]
                                parsed_by_category["event_entity"] = deepcopy(partition["rebound_native_EV_items"])
                                parsed_outputs[execution_order.index("event_entity")] = deepcopy(partition["rebound_native_EV_items"])
                                row["categories"]["event_entity"]["participant_partition_rebound"] = True
                            if entity_binding is not None:
                                id_parsed = deepcopy(parsed[0])
                                try:
                                    resolved = resolve_ee_entity_ids(id_parsed, entity_binding)
                                except ValueError as error:
                                    save_json(rep / "ee_entity_id_resolver.json", {"binding_sha256": row["ee_entity_binding_sha256"],
                                        "native_generated_output": raw_outputs[0], "id_parsed_output": id_parsed,
                                        "resolved_output": None, "status": "rejected", "reason": str(error),
                                        "additional_POSTs": 0, "VV_POSTs": 0})
                                    raise
                                save_json(rep / "ee_entity_id_resolver.json", {"binding_sha256": row["ee_entity_binding_sha256"],
                                    "native_generated_output": raw_outputs[0], "id_parsed_output": id_parsed,
                                    "resolved_output": resolved, "resolved_output_sha256": sha(canonical(resolved)), "status": "resolved",
                                    "resolution": "Exact occurrence IDs through the explicit model partition to unchanged selected canonical EV labels; Relation fields preserved" if args.partition_ee_entity_ids else "Exact actual EV participant IDs to unchanged participant strings; Relation fields preserved",
                                    "partition_decoder_sha256": sha((rep / "ee_entity_partition_decoder.json").read_bytes()) if args.partition_ee_entity_ids else None})
                                parsed = [resolved]
                            if binding is not None:
                                id_parsed = deepcopy(parsed[0])
                                try:
                                    resolved = resolve_vv_event_ids(id_parsed, binding)
                                except ValueError as error:
                                    save_json(rep / "vv_event_id_resolver.json", {"binding_sha256": row["vv_event_binding_sha256"],
                                        "native_generated_output": raw_outputs[0], "id_parsed_output": id_parsed,
                                        "resolved_output": None, "status": "rejected", "reason": str(error),
                                        "additional_POSTs": 0})
                                    raise
                                save_json(rep / "vv_event_id_resolver.json", {"binding_sha256": row["vv_event_binding_sha256"],
                                    "native_generated_output": raw_outputs[0], "id_parsed_output": id_parsed,
                                    "resolved_output": resolved, "resolved_output_sha256": sha(canonical(resolved)), "status": "resolved",
                                    "resolution": "Exact known event IDs to unchanged EV Event strings; Relation fields preserved"})
                                parsed = [resolved]
                            llm_outputs.append(raw_outputs[0]); parsed_outputs.append(parsed[0])
                            parsed_by_category[key] = deepcopy(parsed[0])
                            row["categories"][key] = {"prompt_sha256": sha(canonical(actual[0])), "items": len(parsed[0])}
                        native = extractor.prepare_result_dict(ids[0], texts[0], metadata[0], (llm_outputs, parsed_outputs), execution_order)
                        save(rep / "kg_extraction" / "toy_native_output.json", canonical(native) + b"\n")
                    else:
                        saved = prior_root / f"r{repetition}" / "kg_extraction" / "toy_native_output.json"
                        raw = unlinked(saved).read_bytes()
                        save(rep / "kg_extraction" / "toy_native_output.json", raw)
                        save_json(rep / "extraction_reuse.json", {"path": str(saved), "sha256": sha(raw), "extraction_POSTs": 0})
                    if args.with_schema:
                        runtime.phase = "concept_induction"
                        extractor.convert_json_to_csv()
                        if args.concept_edge_context or args.preserve_structural_relations or args.preserve_source_relations:
                            edge_file = rep / "triples_csv" / "triple_edges_toy_from_json_without_emb.csv"
                            fields = (":START_ID", "relation", ":END_ID", ":TYPE")
                            with edge_file.open("r", encoding="utf-8", newline="") as stream:
                                edges = [{key: edge[key] for key in fields} for edge in csv.DictReader(stream)]
                            if args.concept_edge_context:
                                runtime.concept_edge_context = edges
                                row["concept_edge_context_sha256"] = sha(canonical(edges))
                                save_json(rep / "concept_edge_context.json", {"source_path": str(edge_file),
                                    "source_file_sha256": sha(edge_file.read_bytes()), "edges": edges,
                                    "edge_context_sha256": row["concept_edge_context_sha256"]})
                            if args.preserve_structural_relations or args.preserve_source_relations:
                                saved_native = rep / "kg_extraction" / "toy_native_output.json"
                                native_data = strict(saved_native.read_bytes())
                                runtime.original_relation_template = CONCEPT_INSTRUCTIONS["en"]["relation"]
                                if args.preserve_structural_relations:
                                    runtime.structural_relations = structural_relation_bindings(native_data, edges, clean_text)
                                    row["structural_relations_binding_sha256"] = sha(canonical(runtime.structural_relations))
                                    save_json(rep / "structural_relation_bindings.json", {
                                        "native_output_sha256": sha(saved_native.read_bytes()), "edge_file_sha256": sha(edge_file.read_bytes()),
                                        "bindings": runtime.structural_relations, "binding_sha256": row["structural_relations_binding_sha256"]})
                                if args.preserve_source_relations:
                                    resolver_path = rep / "vv_event_id_resolver.json"
                                    if prior is not None:
                                        resolver_path = prior_root / f"r{repetition}" / "vv_event_id_resolver.json"
                                    vv_resolver = strict(resolver_path.read_bytes()) if resolver_path.is_file() else None
                                    ee_resolver_path = rep / "ee_entity_id_resolver.json"
                                    if prior is not None:
                                        ee_resolver_path = prior_root / f"r{repetition}" / "ee_entity_id_resolver.json"
                                    ee_resolver = strict(ee_resolver_path.read_bytes()) if ee_resolver_path.is_file() else None
                                    runtime.source_relations = source_relation_bindings(native_data, edges, clean_text, vv_resolver, ee_resolver)
                                    row["source_relations_binding_sha256"] = sha(canonical(runtime.source_relations))
                                    save_json(rep / "source_relation_bindings.json", {
                                        "native_output_sha256": sha(saved_native.read_bytes()), "edge_file_sha256": sha(edge_file.read_bytes()),
                                        "VV_resolver_sha256": sha(resolver_path.read_bytes()) if resolver_path.is_file() else None,
                                        "EE_resolver_sha256": sha(ee_resolver_path.read_bytes()) if ee_resolver_path.is_file() else None,
                                        "bindings": runtime.source_relations, "binding_sha256": row["source_relations_binding_sha256"]})
                        extractor.generate_concept_csv_temp(batch_size=64)
                        extractor.create_concept_csv()
                        extractor.convert_to_graphml()
                        graph = rep / "kg_graphml" / "toy_graph.graphml"
                        if not graph.is_file():
                            raise ValueError("Native graph output absent")
                        row["schema_complete"] = True
                        row["graphml_sha256"] = sha(graph.read_bytes())
                    row["complete"] = True
                    summary["repetitions_completed"] += 1
                finally:
                    row.update(physical_POSTs=sum(r["physical_dispatch_performed"] for r in runtime.receipts),
                        unknown_executions=sum(r["unknown_execution"] for r in runtime.receipts),
                        native_retry_blocked=runtime.retry_blocked,
                        deterministic_concepts=len(runtime.deterministic_concepts))
                    row["deterministic_concepts_by_origin_kind"] = {
                        kind: sum(item["origin_kind"] == kind for item in runtime.deterministic_concepts)
                        for kind in sorted({item["origin_kind"] for item in runtime.deterministic_concepts})}
                    save_json(rep / "deterministic_concepts.json", runtime.deterministic_concepts)
                    summary["physical_POSTs"] += row["physical_POSTs"]
                    summary["unknown_executions"] += row["unknown_executions"]
                    save_json(rep / "repetition_summary.json", row)
        after = verify_source(args.source)
        if after["files"] != original["files"]:
            raise ValueError("Original source changed during execution")
        summary.update(status="completed", complete=True, source_bytes_preserved=True)
    except BaseException as error:
        summary.update(status="failed", failure_class=type(error).__name__)
    finally:
        if args.concept_edge_context:
            save_json(output / "concept_edge_context_condition.json", {
                "condition_sha256": sha(canonical(condition)), "concept_edge_context": True,
                "hashes_by_repetition": {str(row["repetition"]): row.get("concept_edge_context_sha256") for row in summary["runs"]},
                "input_kind": "Projected actual directed native CSV edges; no source text or expected facts added"})
        save_json(output / "summary.json", summary)
    print(json.dumps({"output": str(output), **summary}, ensure_ascii=False))
    return 0 if summary["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

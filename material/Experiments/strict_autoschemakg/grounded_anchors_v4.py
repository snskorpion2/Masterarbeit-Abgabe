"""Opt-in AEVS-inspired anchored extraction, not an original-paper reproduction.

Per-element references are restored to exact, unchanged source spans. This is
reference binding, NOT entailment. Only separately source-verified candidates
cover anchors. Similarity retrieves deduplication proposals, never acceptance.
No language/content vocabulary or schema ontology is fixed here. All functions
are pure. Dispatch, technical retries and independent model choice belong to the
new runner, never the historical native extraction path.

Primary method: https://www.mdpi.com/2073-431X/15/3/178 sections 3.4--3.8.
Deliberate departures: generic spans with positional roles, exact restoration,
mandatory independent source verification, and semantic equivalence verification
instead of cosine-only removal. EV/VV are our adaptation, not paper validation.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from itertools import combinations
import json
import math
import re

from jsonschema import Draft202012Validator

from . import grounded_evidence_v1 as e
from . import reliability_v2 as r


CATEGORIES = ("entity", "event", "relation")


def _digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:20]


def _catalog(rows):
    e.validate_catalog(rows)
    for row in rows:
        if (not isinstance(row["id"], str) or not isinstance(row["text"], str)
                or row["end"] - row["start"] != len(row["text"])):
            raise ValueError("Evidence offsets must describe the exact source span")
    return {row["id"]: row for row in rows}


def schema_for(query):
    return query["output_schema"]


def classify(query, raw):
    return e.classify(query, raw)


def anchor_request(catalog, ident="b4:anchors", *, max_anchors=None):
    """One source-driven span inventory. Offset units are Python Unicode characters."""
    known = _catalog(catalog)
    span = r.obj({"evidence_id": {"type": "string", "enum": list(known)},
                  "text": {"type": "string", "minLength": 1},
                  "start": {"type": "integer", "minimum": 0},
                  "end": {"type": "integer", "minimum": 1}})
    anchors = r.array(span)
    if max_anchors is not None:
        if type(max_anchors) is not int or max_anchors < 1:
            raise ValueError("max_anchors must be a positive integer")
        anchors["maxItems"] = max_anchors
    prompt = (
        "Inventory useful exact source spans for grounded knowledge extraction. Include names, "
        "events, relational expressions, attributes, quantities, dates, qualifiers and negation "
        "when present. These are examples of roles, not a closed vocabulary or mandatory types. "
        "Use the source language and do not invent text. Return each span's exact text, evidence_id "
        "and zero-based start/end offsets WITHIN that evidence text (end exclusive, Unicode "
        "characters). Distinct occurrences have distinct offsets. Preserve case and whitespace. "
        "An anchor is only an occurrence, never proof of a relation. Empty output is allowed.\nSOURCE:\n"
        + json.dumps(catalog, ensure_ascii=False))
    query = e.request(ident, prompt, r.obj({"anchors": anchors}))
    query["anchor_limit"] = max_anchors
    return query


def restore_anchors(raw, catalog):
    """Restore literal spans only, with unique exact occurrence offset repair.

    Repeated strings with wrong offsets stay unbound. No fuzzy/case folding or
    ontology fallback. Invalid proposals remain in raw and audit.
    """
    known = _catalog(catalog)
    schema = anchor_request(catalog)["output_schema"]["properties"]["anchors"]["items"]
    if not isinstance(raw, dict) or set(raw) != {"anchors"} or not isinstance(raw["anchors"], list):
        raise ValueError("Invalid anchor response envelope")
    anchors, audit, seen = [], [], set()
    validator = Draft202012Validator(schema)
    for index, item in enumerate(raw["anchors"]):
        valid = validator.is_valid(item)
        findings, restored = [], None
        if valid:
            unit = known[item["evidence_id"]]
            start, end, text = item["start"], item["end"], item["text"]
            # jsonschema allows integral floats. Require actual integer offsets,
            # excluding bool, rather than silently coercing transport values.
            if type(start) is not int or type(end) is not int:
                valid = False
                findings.append("noninteger_offset")
            elif not text.strip():
                valid = False
                findings.append("empty_anchor_text")
            else:
                exact = 0 <= start < end <= len(unit["text"]) and unit["text"][start:end] == text
                if not exact:
                    occurrences = [m.start() for m in re.finditer("(?=" + re.escape(text) + ")", unit["text"])]
                    if len(occurrences) == 1:
                        start, end = occurrences[0], occurrences[0] + len(text)
                        findings.append("unique_exact_offset_repair")
                        exact = True
                    else:
                        findings.append("ambiguous_exact_span" if occurrences else "text_not_in_evidence")
                if exact:
                    aid = "A" + _digest([item["evidence_id"], start, end])
                    restored = {"id": aid, "evidence_id": item["evidence_id"], "text": text,
                                "start": start, "end": end,
                                "global_start": unit["start"] + start, "global_end": unit["start"] + end}
                    if aid in seen:
                        findings.append("duplicate_anchor_occurrence")
                    else:
                        seen.add(aid)
                        anchors.append(restored)
        if not valid and not findings:
            findings.append("invalid_anchor_schema")
        audit.append({"index": index, "valid": valid, "bound": restored is not None,
                      "entailed": None, "restored": restored, "findings": findings})
    return {"raw": deepcopy(raw), "anchors": anchors, "audit": audit}


def _anchors(rows, catalog):
    known, indexed = _catalog(catalog), {}
    for row in rows:
        unit = known.get(row.get("evidence_id"))
        start, end = row.get("start"), row.get("end")
        if (unit is None or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(unit["text"])
                or unit["text"][start:end] != row.get("text")
                or row.get("id") != "A" + _digest([row["evidence_id"], start, end])
                or row["id"] in indexed):
            raise ValueError("Anchor is not an exact restored occurrence")
        indexed[row["id"]] = row
    return indexed


def _candidate_schema(category, catalog, anchors):
    refs = e.enum_array(list(anchors), 1)
    elements = (r.obj({"Event": refs, "Entity": {"type": "array", "items": deepcopy(refs), "minItems": 1}})
                if category == "event" else r.obj({key: deepcopy(refs) for key in ("Head", "Relation", "Tail")}))
    return r.obj({"value": r.triple_schema(category, missing=True),
                  "evidence_ids": e.enum_array(list(_catalog(catalog)), 1),
                  "element_anchor_refs": elements})


def extraction_requests(catalog, anchors, *, prefix="b4:initial", max_candidates=None):
    """Initial EE, EV, VV extraction is anchored from its first extraction turn."""
    indexed = _anchors(anchors, catalog)
    if not indexed:
        return []
    prompts = {
        "entity": "Extract source-supported entity-to-entity (EE) claims: Head, Relation, Tail.",
        "event": "Extract source-supported event-to-entity (EV) records: Event and its Entity participants.",
        "relation": "Extract source-supported event-to-event (VV) claims: Head event, Relation, Tail event.",
    }
    queries = []
    for category in CATEGORIES:
        items = r.array(_candidate_schema(category, catalog, indexed))
        if max_candidates is not None:
            if type(max_candidates) is not int or max_candidates < 1:
                raise ValueError("max_candidates must be a positive integer")
            items["maxItems"] = max_candidates
        prompt = (
            prompts[category] + " Preserve the source language, direction, participants, quantities, "
            "dates, negation and modality. There is no fixed entity, event or relation vocabulary. "
            "Do not use memorized facts. Cite actual evidence_ids and anchor IDs for EVERY element. "
            "For EE/VV independently cite Head, Relation and Tail anchors. For EV cite Event anchors "
            "and a separate anchor-ID array for EACH Entity at the same array position. An element "
            "may paraphrase source spans only when their meaning is preserved. Exact word presence "
            "alone does not establish the whole claim. evidence_ids must include all cited anchors' "
            "evidence units. Return no unsupported or duplicate claims. Empty candidates is allowed.\nSOURCE:\n"
            + json.dumps(catalog, ensure_ascii=False) + "\nRESTORED_ANCHORS:\n" + json.dumps(anchors, ensure_ascii=False))
        query = e.request(f"{prefix}:{category}", prompt, r.obj({"candidates": items}), category)
        query["candidate_limit"] = max_candidates
        queries.append(query)
    return queries


def restore_candidates(query, raw, catalog, anchors):
    """Audit every element reference without rewriting any candidate value.

    'bound' means all referenced source spans exist and belong to the claimed
    evidence units. Paraphrase correspondence and full truth require the later
    independent verifier, even for exact lexical matches.
    """
    indexed = _anchors(anchors, catalog)
    if not isinstance(raw, dict) or set(raw) != {"candidates"} or not isinstance(raw["candidates"], list):
        raise ValueError("Invalid candidate response envelope")
    schema = query["output_schema"]["properties"]["candidates"]["items"]
    validator = Draft202012Validator(schema)
    candidates, audit = [], []
    for i, item in enumerate(raw["candidates"], 1):
        cid = f"{query['request_id']}:{i:04d}"
        valid = validator.is_valid(item)
        findings, element_audit, used = [], [], []
        bound = valid
        if valid:
            value, refs = item["value"], item["element_anchor_refs"]
            if query["category"] == "event":
                fields = [("Event", value["Event"], refs["Event"])]
                if len(value["Entity"]) != len(refs["Entity"]):
                    findings.append("ev_participant_reference_count")
                    bound = False
                fields += [(f"Entity[{n}]", text, refs["Entity"][n] if n < len(refs["Entity"]) else [])
                           for n, text in enumerate(value["Entity"])]
            else:
                fields = [(key, value[key], refs[key]) for key in ("Head", "Relation", "Tail")]
            for field, text, field_refs in fields:
                exact_refs = bool(field_refs) and all(ident in indexed for ident in field_refs)
                units_match = exact_refs and all(indexed[ident]["evidence_id"] in item["evidence_ids"] for ident in field_refs)
                surface = exact_refs and any(indexed[ident]["text"] == text for ident in field_refs)
                if not units_match:
                    bound = False
                    findings.append("element_evidence_reference_mismatch")
                if not surface:
                    findings.append("surface_mapping_requires_verifier")
                used.extend(field_refs)
                element_audit.append({"element": field, "text": text, "anchor_ids": deepcopy(field_refs),
                                      "bound": units_match, "exact_surface": surface, "entailed": None})
            candidates.append({"id": cid, "category": query["category"], "value": deepcopy(value),
                               "evidence_ids": deepcopy(item["evidence_ids"])})
        else:
            findings.append("invalid_candidate_schema")
        audit.append({"id": cid, "valid": valid, "bound": bound, "entailed": None,
                      "anchor_ids": list(dict.fromkeys(used)), "elements": element_audit,
                      "findings": list(dict.fromkeys(findings))})
    return {"raw": deepcopy(raw), "candidates": candidates, "audit": audit, "request_id": query["request_id"]}


def verifier_request(restored, catalog, anchors, ident="b4:source_verify"):
    """Independent check of BOTH full claims and their per-element mappings.

    A batch is a restored record with candidates/audit filtered to the same IDs.
    The fixed-ID output contract is shared with the source-fidelity verifier.
    The extra mapping context closes the gap where a true claim cites unrelated
    real anchors and would otherwise mark those anchors as covered.
    """
    indexed = _anchors(anchors, catalog)
    candidates = restored["candidates"]
    candidate_ids = {row["id"] for row in candidates}
    relevant = [row for row in restored["audit"] if row["id"] in candidate_ids]
    if len(relevant) != len(candidates) or {row["id"] for row in relevant} != candidate_ids:
        raise ValueError("Missing or duplicate element-mapping audit")
    query = e.verifier_request(candidates, catalog, ident)
    base_prompt = query["prompt"].split("\nOUTPUT_CONTRACT (JSON only):\n", 1)[0]
    mappings = [{"id": row["id"], "reference_bound": row["bound"],
                 "elements": [{**deepcopy(element),
                               "anchors": [deepcopy(indexed[aid]) for aid in element["anchor_ids"] if aid in indexed]}
                              for element in row["elements"]]}
                for row in relevant]
    prompt = (base_prompt + "\nADDITIONAL ANCHORED-EXTRACTION CHECK: For every candidate, independently inspect "
              "the element-to-anchor mappings below. supported requires BOTH full-claim source entailment "
              "AND an appropriate meaning-preserving mapping for EVERY Head/Relation/Tail or Event/Entity "
              "element. Real but unrelated anchors do not support an element. Matching source IDs, offsets "
              "or words alone are not enough. Reordered or misplaced participant/role references must not "
              "pass. If the claim is true elsewhere but these mappings do not establish its elements, return "
              "insufficient and explain the mapping failure. Paraphrases are allowed only if the cited spans "
              "in original context express that element's meaning. A false claim remains contradicted or "
              "insufficient. Do not modify values or references.\nELEMENT_MAPPINGS:\n"
              + json.dumps(mappings, ensure_ascii=False))
    return e.request(ident, prompt, query["output_schema"])


def accepted_coverage(restored, decisions, catalog, anchors):
    """Reference-based coverage from bound AND independently supported candidates.

    Decisions must come from verifier_request, not only the generic full-claim
    verifier, because per-element semantic correspondence is also required.
    Verifier citations may use any original evidence unit, but never rescue
    broken element references. Semantic decisions are model evidence, not gold.
    """
    indexed = _anchors(anchors, catalog)
    candidates = restored["candidates"]
    if set(decisions) != {row["id"] for row in candidates}:
        raise ValueError("Incomplete or unexpected source-verification decisions")
    if candidates:
        Draft202012Validator(e.verifier_request(candidates, catalog, "validation")["output_schema"]).validate(decisions)
    gated = e.gate(candidates, catalog, decisions)
    restoration = {row["id"]: row for row in restored["audit"]}
    eligible = {row["id"] for row in gated["accepted"]
                if restoration[row["id"]]["valid"] is True and restoration[row["id"]]["bound"] is True}
    accepted = [deepcopy(row) for row in candidates if row["id"] in eligible]
    used = {ident for row in restored["audit"] if row["id"] in eligible for ident in row["anchor_ids"]}
    by_category = {}
    for category in CATEGORIES:
        category_candidates = [row for row in accepted if row["category"] == category]
        category_ids = {row["id"] for row in category_candidates}
        category_used = {aid for row in restored["audit"] if row["id"] in category_ids for aid in row["anchor_ids"]}
        by_category[category] = {"accepted": deepcopy(category_candidates),
                                 "used_anchor_ids": [aid for aid in indexed if aid in category_used],
                                 "unused_anchor_ids": [aid for aid in indexed if aid not in category_used]}
    return {"accepted": accepted, "used_anchor_ids": [ident for ident in indexed if ident in used],
            "unused_anchor_ids": [ident for ident in indexed if ident not in used],
            "coverage_by_category": by_category,
            "audit": [{**deepcopy(row), "reference_bound": restoration[row["id"]]["bound"],
                       "accepted": row["id"] in eligible} for row in gated["audit"]],
            "raw_candidates": deepcopy(candidates), "claim_limit": "model_verified_not_gold"}


def supplement_requests(catalog, anchors, coverage, *, prefix="b4:supplement", max_candidates=None):
    """One bounded pass per category can revisit every restored anchor.

    Unused references prioritize the search, but used references can support
    further facts. Reference use is not a fact-completeness stop condition.
    The runner invokes this once and retains its existing total request cap.
    """
    indexed = _anchors(anchors, catalog)
    queries = extraction_requests(catalog, anchors, prefix=prefix, max_candidates=max_candidates)
    selected = []
    for query in queries:
        category = query["category"]
        # accepted may already be safely deduplicated by the runner. Preserve
        # that supplied selection rather than reintroducing covered aliases.
        accepted = [row for row in coverage["accepted"] if row["category"] == category]
        category_coverage = coverage.get("coverage_by_category", {}).get(category)
        unused = list(indexed) if category_coverage is None else category_coverage["unused_anchor_ids"]
        if len(unused) != len(set(unused)) or not set(unused) <= set(indexed):
            raise ValueError("Invalid category-specific unused anchor references")
        # Insert the supplement instruction before the sole output-contract block.
        base_prompt = query["prompt"].split("\nOUTPUT_CONTRACT (JSON only):\n", 1)[0]
        prompt = (base_prompt + "\nSUPPLEMENT: In this single bounded pass, examine ALL restored anchors for "
                  "additional claims under the same per-element grounding and source-only rules. Prioritize "
                  "UNUSED_ANCHOR_IDS, but revisit used anchors too: one anchor can support several claims. "
                  "Previously used references do not establish fact completeness. Other anchors may supply "
                  "necessary context. Do not repeat an accepted claim. An unused anchor need not yield a "
                  "claim. Empty output is valid.\nSEARCH_ANCHOR_IDS:\n" + json.dumps(list(indexed), ensure_ascii=False) + "\n"
                  "UNUSED_ANCHOR_IDS:\n" + json.dumps(unused, ensure_ascii=False)
                  + "\nALREADY_ACCEPTED:\n" + json.dumps(accepted, ensure_ascii=False))
        query["prompt"] = e.request(query["request_id"], prompt, query["output_schema"], query["category"])["prompt"]
        query["unused_anchor_ids"] = deepcopy(unused)
        query["search_anchor_ids"] = list(indexed)
        query["accepted_candidates"] = deepcopy(accepted)
        query["coverage_scope"] = "category_specific_accepted_references"
        query["search_scope"] = "all_restored_anchors_single_pass"
        query["fact_completeness_claim"] = False
        selected.append(query)
    return selected


def _check_candidates(candidates):
    ids = []
    for row in candidates:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError("Candidate ID must be a nonempty string")
        if row.get("category") not in CATEGORIES:
            raise ValueError("Unknown candidate category")
        Draft202012Validator(r.triple_schema(row["category"], missing=True)).validate(row["value"])
        ids.append(row["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate candidate IDs")
    return {row["id"]: row for row in candidates}


def _content(value):
    # Role labels do not inflate lexical similarity. They remain in raw values.
    return "\n".join("\n".join(part) if isinstance(part, list) else part for part in value.values())


def propose_duplicates(candidates, *, threshold=0.5, ngram_size=3, max_pairs=None, score_fn=None):
    """Configurable lexical retrieval, not proof of equivalence.

    This intentionally makes no cross-script/semantic recall guarantee. A custom
    similarity callback is allowed, but cannot bypass the independent gate.
    """
    indexed = _check_candidates(candidates)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
        raise ValueError("threshold must lie in [0,1]")
    if type(ngram_size) is not int or ngram_size < 1:
        raise ValueError("ngram_size must be positive")
    if max_pairs is not None and (type(max_pairs) is not int or max_pairs < 0):
        raise ValueError("max_pairs must be nonnegative")
    def grams(row):
        text = _content(row["value"]).casefold()
        return {text[i:i + ngram_size] for i in range(max(1, len(text) - ngram_size + 1))}
    pairs, examined = [], 0
    for left, right in combinations(sorted(indexed), 2):
        a, b = indexed[left], indexed[right]
        if a["category"] != b["category"]:
            continue
        examined += 1
        ga, gb = grams(a), grams(b)
        score = score_fn(deepcopy(a), deepcopy(b)) if score_fn else len(ga & gb) / len(ga | gb)
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Similarity callback must return a finite [0,1] number")
        if score >= threshold:
            pairs.append({"id": "D" + _digest([left, right]), "left": left, "right": right, "score": score})
    pairs.sort(key=lambda row: (-row["score"], row["left"], row["right"]))
    proposed = len(pairs)
    if max_pairs is not None:
        pairs = pairs[:max_pairs]
    return {"pairs": pairs, "threshold": threshold, "ngram_size": ngram_size, "max_pairs": max_pairs,
            "same_category_pairs_examined": examined, "above_threshold_pairs": proposed,
            "selected_pairs": len(pairs), "omitted_by_limit": proposed - len(pairs),
            "retrieval": "custom_callback" if score_fn else "unicode_character_ngram_jaccard",
            "claim_limit": "retrieval_only_no_equivalence_claim"}


def _pair_index(candidates, proposals):
    indexed = _check_candidates(candidates)
    seen = set()
    for pair in proposals["pairs"]:
        if (pair["id"] in seen or pair["left"] not in indexed or pair["right"] not in indexed
                or pair["left"] == pair["right"]
                or indexed[pair["left"]]["category"] != indexed[pair["right"]]["category"]):
            raise ValueError("Invalid deduplication proposal")
        seen.add(pair["id"])
    return indexed


def _equivalence_schema(catalog):
    return r.obj({"status": {"type": "string", "enum": ["equivalent", "different", "uncertain"]},
                  **{key: {"type": "string", "enum": ["same", "different", "uncertain"]}
                     for key in ("meaning", "direction", "numbers", "polarity")},
                  "evidence_ids": e.enum_array(list(_catalog(catalog))),
                  "reason": {"type": "string", "minLength": 1}})


def equivalence_request(candidates, proposals, catalog, ident="b4:dedup:verify"):
    indexed = _pair_index(candidates, proposals)
    if not proposals["pairs"]:
        raise ValueError("No deduplication proposals")
    schema = r.obj({pair["id"]: _equivalence_schema(catalog) for pair in proposals["pairs"]})
    prompt = (
        "Independently decide whether each pair expresses exactly the SAME entire claim in the ORIGINAL "
        "source. Similar words or shared evidence are not equivalence. Preserve entity identity, roles, "
        "direction, event participants, every numeric value/unit/date, negation, modality, conditions and "
        "temporal scope. Reverse relations, stronger/weaker claims, different participants or uncertainty "
        "must not be merged. Do not repair or rewrite either claim. For each immutable pair ID, assess "
        "meaning, direction, numbers and polarity separately. equivalent requires all dimensions same "
        "and original-source evidence. If uncertain choose uncertain and keep both. Source IDs and "
        "offsets alone do not establish equivalence.\nPAIRS:\n"
        + json.dumps([{**pair, "left_candidate": indexed[pair["left"]], "right_candidate": indexed[pair["right"]]}
                      for pair in proposals["pairs"]], ensure_ascii=False)
        + "\nORIGINAL_SOURCE:\n" + json.dumps(catalog, ensure_ascii=False))
    return e.request(ident, prompt, schema)


def _numbers(value):
    # Unicode numeric characters, without language-specific number-word lists.
    return sorted(re.findall(r"[+-]?\d+(?:[.,]\d+)*(?:[eE][+-]?\d+)?", _content(value)))


def deduplicate(candidates, proposals, decisions, catalog):
    """Keep raw provenance. Collapse only fully verified cliques, never chains.

    Missing/invalid independent decisions retain both. Lexical numeric and exact
    reversal guards can veto a mistaken equivalence verdict, never approve one.
    """
    indexed, known = _pair_index(candidates, proposals), _catalog(catalog)
    expected = {pair["id"] for pair in proposals["pairs"]}
    if set(decisions) - expected:
        raise ValueError("Unexpected equivalence decision IDs")
    schema = Draft202012Validator(_equivalence_schema(catalog))
    equivalent, audit = set(), []
    for pair in proposals["pairs"]:
        decision = decisions.get(pair["id"])
        findings, accept = [], False
        a, b = indexed[pair["left"]], indexed[pair["right"]]
        if decision is None:
            findings.append("missing_independent_decision")
        elif not schema.is_valid(decision):
            findings.append("invalid_independent_decision")
        else:
            support = bool(decision["evidence_ids"]) and set(decision["evidence_ids"]) <= set(known) and bool(decision["reason"].strip())
            source_bound = all(isinstance(row.get("evidence_ids"), list) and bool(row["evidence_ids"])
                               and set(row["evidence_ids"]) <= set(known) for row in (a, b))
            accept = support and source_bound and decision["status"] == "equivalent" and all(
                decision[key] == "same" for key in ("meaning", "direction", "numbers", "polarity"))
            if not accept:
                findings.append("not_independently_equivalent")
            if _numbers(a["value"]) != _numbers(b["value"]):
                accept = False
                findings.append("numeric_signature_mismatch")
            if a["category"] != "event":
                av, bv = a["value"], b["value"]
                if av["Head"] != av["Tail"] and av["Head"] == bv["Tail"] and av["Tail"] == bv["Head"]:
                    accept = False
                    findings.append("exact_endpoint_reversal")
        if accept:
            equivalent.add(frozenset((pair["left"], pair["right"])))
        audit.append({"pair": deepcopy(pair), "decision": deepcopy(decision), "equivalent": accept, "findings": findings})
    groups = []
    # Stable input occurrence wins, but every collapsed member must have a
    # positive independently checked edge to EVERY existing group member.
    for row in candidates:
        group = next((g for g in groups if all(frozenset((row["id"], member)) in equivalent for member in g)), None)
        if group is None:
            groups.append([row["id"]])
        else:
            group.append(row["id"])
    return {"raw_candidates": deepcopy(candidates), "retained": [deepcopy(indexed[g[0]]) for g in groups],
            "groups": [{"representative": g[0], "members": g} for g in groups], "audit": audit,
            "proposals": deepcopy(proposals), "claim_limit": "model_verified_not_gold"}

"""Versioned, bounded A/K method diagnostics over one immutable saved graph.

Default CLI is read-only. --execute uses the existing traced eleven-attempt
engine. It never starts baseline extraction, judges, confidence, or semantic
retries. These are method variants, not guaranteed fixes or paper reproductions.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import random

from . import completion_contracts as c, completion_measurements as measurements
from . import completion_pilot as stages, completion_probe as original_probe
from . import immutable_publish, local_runtime, recall_methods as methods
from . import reliability_v2 as r, retry_continuation, technical_repairs
from .contract import sha256

VARIANT = "supplement_diagnostics_v1"
PROTOCOL = "native_conversation_and_bounded_nodewise_completion_v1"
CONTEXT = 131072
OUTPUT_CEILING = 16384
SEED = 30092026
SOURCES = {
    "A": {
        "url": "https://github.com/microsoft/graphrag/blob/6d21ef268377e319a165ca2250bd6841737df1ad/graphrag/index/graph/extractors/graph/graph_extractor.py",
        "reference": "GraphExtractor._process_document uses history=response.history for CONTINUE_PROMPT",
        "adaptation": "Native EE/EV/VV JSON retained. One continuation, no YES/NO loop. No claim of complete GraphRAG reproduction.",
    },
    "B": {
        "url": "https://www.mdpi.com/2073-431X/15/3/178",
        "reference": "Sections 3.5, 3.6.4, Box 4, Algorithm 2",
        "adaptation": "Audit only. Existing B is lexical coverage hints, not element-grounded extraction, restoration verification or semantic deduplication.",
        "code_url": "https://github.com/yyz-nbt/AEVS/blob/9c4a5b18eb48e1b7ad8fcd6956fcf95c73b527a7/pipeline.py",
        "code_limit": "This inspected author pipeline has no supplement invocation. Paper and released implementation must not be conflated.",
    },
    "K": {
        "url": "https://arxiv.org/html/2410.17600v2",
        "code_url": "https://github.com/IreneZihuiLi/Graphusion/blob/cc767d7b099a760d91613ad9b724fa3d5df3aff6/step_03_fusion.py",
        "reference": "step_03_fusion iterates focal concepts, retrieves incident triples and supplies background",
        "adaptation": "Bounded one-graph source-grounded nodewise search. No second graph, pretrained relation ontology, entity merging or conflict replacement. Not full Graphusion.",
    },
}


def _positive(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(name + " must be a positive integer")


def _read(path):
    return immutable_publish.read_json(Path(path))


def _view_from_request(request):
    """Recover the actual base view using the unchanged native prompt template."""
    marker = "__SUPPLEMENT_DIAGNOSTIC_SOURCE_SENTINEL_7f91__"
    native = r.native_extraction_prompts(marker)[r.CATEGORIES.index(request["category"])]
    template = native[-1]["content"]
    if template.count(marker) != 1:
        raise ValueError("Native source template is not uniquely identifiable")
    before, after = template.split(marker)
    messages = request["messages"]
    prompt = messages[-1]["content"]
    if (messages[:-1] != native[:-1] or messages[-1]["role"] != "user" or
            not prompt.startswith(before) or (after and not prompt.endswith(after))):
        raise ValueError("Base messages differ from native extraction template")
    return prompt[len(before):len(prompt) - len(after) if after else None]


def load_inputs(source, baseline, base_stage):
    inputs = c.load_inputs(Path(source), Path(baseline))
    base_stage = Path(base_stage)
    queries = _read(base_stage / "schedule.json")["requests"]
    responses = _read(base_stage / "final_responses.json")
    if ([q.get("category") for q in queries] != list(r.CATEGORIES) or
            len(responses) != 3 or any(q.get("kind") != "extraction" for q in queries)):
        raise ValueError("Expected exactly three native base queries in EE/EV/VV order")
    views = []
    for query, response in zip(queries, responses):
        expected = inputs["baseline"][c.CATEGORIES[query["category"]]]
        if (response.get("request_id") != query["request_id"] or response.get("status") != "valid" or
                response.get("parsed") != expected):
            raise ValueError("Base response differs from frozen baseline graph")
        if r.classify(query, response["raw_response"]) != expected:
            raise ValueError("Base raw answer differs from frozen baseline graph")
        views.append(_view_from_request(query))
    if len(set(views)) != 1:
        raise ValueError("Base category source views differ")
    return inputs, {"requests": queries, "responses": responses, "view": views[0],
                    "hashes": {name: sha256(base_stage / name)
                               for name in ("schedule.json", "final_responses.json")}}


def glean_pair(inputs, history):
    state = {"triples": {category: inputs["baseline"][field] for category, field in c.CATEGORIES.items()}}
    controls = methods.supplement_requests(history["view"], state, "glean", "control")
    variants = []
    for control, base, response in zip(controls, history["requests"], history["responses"]):
        request = deepcopy(control)
        # Same source and existing graph as the flat control. Only the packing
        # and follow-up instruction differ. No new baseline model call.
        instruction = control["prompt"].split("EXISTING_OUTPUT:\n", 1)[0]
        request["prompt"] = instruction + (
            "The preceding assistant answer is the existing output. Continue the preceding "
            "native extraction task on exactly the same passage. Return additions only."
        )
        request["messages"] = deepcopy(base["messages"]) + [
            {"role": "assistant", "content": response["raw_response"]},
            {"role": "user", "content": request["prompt"]},
        ]
        request["method"] = "conversation_glean_v1"
        request["base_request_id"] = base["request_id"]
        variants.append(request)
    return controls, variants


def _endpoints(item):
    value = item["value"]
    return ([value["Event"], *value["Entity"]] if item["category"] == "event"
            else [value["Head"], value["Tail"]])


def nodewise_requests(inputs, max_nodes=2):
    _positive(max_nodes, "max_nodes")
    items = inputs["items"]
    universe = {
        "entity": {v for item in items if item["category"] == "entity" for v in _endpoints(item)},
        "event": {v for item in items if item["category"] == "event" for v in item["value"]["Entity"]},
        "relation": {v for item in items if item["category"] in ("event", "relation")
                     for v in ([item["value"]["Event"]] if item["category"] == "event" else _endpoints(item))},
    }
    requests, coverage = [], {}
    category_definitions = {
        "entity": "EE: Head and Tail are named entities or explicit values, Relation connects them. The focal node is an entity endpoint.",
        "event": "EV: Event is a source-supported event statement, Entity is an array of participating named entities or explicit values. The focal node is an Entity participant.",
        "relation": "VV: Head and Tail are event statements, Relation describes their source-supported connection. The focal node is an event endpoint.",
    }
    for category in r.CATEGORIES:
        neighborhood = {node: [item for item in items if node in _endpoints(item)] for node in universe[category] if node.strip()}
        ordered = sorted(neighborhood, key=lambda node: (-len(neighborhood[node]), node))
        chosen = ordered[:max_nodes]
        coverage[category] = {
            "total_nodes": len(ordered), "selected_nodes": len(chosen), "max_nodes": max_nodes,
            "selection": "descending_exact_incident_item_count_then_Unicode_lexical",
            "selected": [{"text": node, "incident_items": len(neighborhood[node]),
                          "literal_in_original_source": any(node in u["text"] for u in inputs["source_units"])}
                         for node in chosen],
            "unselected_nodes": ordered[max_nodes:], "complete_node_coverage": len(chosen) == len(ordered),
        }
        for index, node in enumerate(chosen):
            query = deepcopy(c.completion_requests(inputs)[r.CATEGORIES.index(category)])
            query["request_id"] = f"nodewise:{category}:{index:04d}"
            query["focal_node"] = {"text": node, "category": category, "selection_rank": index + 1}
            query["local_items"] = deepcopy(neighborhood[node])
            query["prompt"] = (
                "METHOD: bounded source-grounded nodewise completion, one focal node per request.\n"
                + category_definitions[category] + "\n"
                "Read the full original source. Inspect the focal node's incident graph. Search for "
                "missing connections involving this focal node, including additional connections "
                "between already connected nodes. New source-supported counterpart nodes are allowed. "
                "Do not replace or correct existing statements. Return only new candidates of the "
                "requested category. Do not use external knowledge or force an edge. An empty "
                "candidates list is valid. Mark direct versus inferred claims, include exact source "
                "spans and premise references, and retain uncertainty. Positions address each original "
                "source unit, with exclusive end. Local graph IDs may be premise_refs.\n"
                "FOCAL_NODE:\n" + json.dumps(query["focal_node"], ensure_ascii=False) +
                "\nLOCAL_INCIDENT_GRAPH:\n" + json.dumps(query["local_items"], ensure_ascii=False, separators=(",", ":")) +
                "\nEXISTING_CATEGORY_VALUES_FOR_DEDUPLICATION:\n" +
                json.dumps(inputs["baseline"][c.CATEGORIES[category]], ensure_ascii=False, separators=(",", ":")) +
                "\nFULL_ORIGINAL_SOURCE_UNITS:\n" + json.dumps(inputs["source_units"], ensure_ascii=False) +
                "\nOUTPUT_CONTRACT (JSON only):\n" + json.dumps(c.schema_for(query), ensure_ascii=False)
            )
            requests.append(query)
    return requests, coverage


def plan(inputs, history, *, repetitions=3, max_nodes=2, seed=SEED):
    _positive(repetitions, "repetitions")
    _positive(max_nodes, "max_nodes")
    controls_a, variants_a = glean_pair(inputs, history)
    controls_k = c.completion_requests(inputs)
    for query in controls_k:
        query["prompt"] += original_probe.SEARCH_PARAGRAPH
    controls_k = technical_repairs.compact_completion_requests(controls_k)
    variants_k, coverage = nodewise_requests(inputs, max_nodes)
    rng, schedule = random.Random(seed), []
    for repeat in range(1, repetitions + 1):
        for method, controls, variants in (("A", controls_a, variants_a), ("K", controls_k, variants_k)):
            for category in r.CATEGORIES:
                arms = [("control", [q for q in controls if q["category"] == category]),
                        ("variant", [q for q in variants if q["category"] == category])]
                rng.shuffle(arms)
                for arm, queries in arms:
                    for index, original in enumerate(queries):
                        query = deepcopy(original)
                        query.update(request_id=f"{method}:r{repeat}:{category}:{arm}:{index:04d}",
                                     diagnostic_method=method, diagnostic_arm=arm, repetition=repeat,
                                     diagnostic_protocol="validation_detail_v1",
                                     baseline_sha256=inputs["input_hashes"]["baseline"])
                        schedule.append(query)
    return technical_repairs.enable_adaptive_output_v2(schedule, ceiling=OUTPUT_CEILING), coverage


def schema_for(query):
    return c.schema_for(query) if query["kind"] == "completion" else r.schema_for(query)


def classify(query, raw):
    return c.classify(query, raw) if query["kind"] == "completion" else r.classify(query, raw)


def _protect_output(output, source, baseline, base_stage):
    output = Path(output).resolve()
    for location in (Path(baseline).resolve(), Path(base_stage).resolve()):
        ancestors = [location] + list(location.parents)
        frozen_roots = [p for p in ancestors if p.is_dir() and (p / "input_manifest.json").is_file()]
        for root in frozen_roots:
            if output == root or output.is_relative_to(root):
                raise ValueError("Output must be outside historical run trees")
    for location in (Path(source).resolve(), Path(baseline).resolve(), Path(base_stage).resolve()):
        if location == output or location.is_relative_to(output):
            raise ValueError("Output cannot contain frozen input files")


def _code_files():
    """Freeze the local import closure, including imports inside functions."""
    pending, found = [Path(__file__).resolve()], set()
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                names = [node.module.split(".")[0]] if node.module else [a.name for a in node.names]
                pending.extend(candidate for name in names
                               if (candidate := path.parent / (name + ".py")).is_file())
    # Explicit file-driven dependencies are not visible as Python imports.
    found.add(r.DEFAULT_SOURCE / "atlas_rag/llm_generator/prompt/triple_extraction_prompt.py")
    return found


def preflight(source, baseline, base_stage, output, *, repetitions=3, max_nodes=2, seed=SEED):
    _protect_output(output, source, baseline, base_stage)
    inputs, history = load_inputs(source, baseline, base_stage)
    schedule, coverage = plan(inputs, history, repetitions=repetitions, max_nodes=max_nodes, seed=seed)
    files = _code_files()
    _, budget = stages._stage_contract(schedule, PROTOCOL, schema_for, variant=VARIANT, context=CONTEXT)
    return {
        "variant": VARIANT, "protocol": PROTOCOL, "output": str(Path(output).resolve()),
        "source": str(Path(source).resolve()), "baseline": str(Path(baseline).resolve()),
        "base_stage": str(Path(base_stage).resolve()), "input_hashes": inputs["input_hashes"],
        "base_stage_hashes": history["hashes"], "base_view_sha256": r.artifacts.digest(history["view"]),
        "code_hashes": {str(p.relative_to(c.ROOT)).replace("\\", "/"): sha256(p) for p in sorted(files)},
        "baseline_counts": inputs["baseline_counts"], "request_hash": r.artifacts.digest(schedule),
        "repetitions": repetitions, "max_nodes": max_nodes, "run_order_seed": seed,
        "logical_requests": len(schedule), "max_physical_calls": budget["max_physical_calls"],
        "budget": budget, "selection_coverage": coverage, "sources": SOURCES,
        "A_source_policy": "Both arms use the exact saved base input view. Flat control replays the historical A template, not necessarily its historical original-source input.",
        "K_source_policy": "Both arms use original source and identical frozen graph. Variant also changes task decomposition and makes category/schema guidance explicit; not an isolated node-count effect.",
        "sampling_policy": "Historical request parameters retained in each matched pair: A temperature 0.7, K constructor defaults. No custom seed for inference.",
        "segmentation_fallback": {"enabled": False, "reason": "Existing recovery is native-base-only. Replacing supplement history or candidate provenance with native extraction would change the task. Terminal length failures remain explicit."},
        "B": {"status": "audit_only", "limitation": SOURCES["B"]["adaptation"]},
        "claim": "bounded_method_diagnosis_not_quality_or_generalization",
        "paused": ["B_model_calls", "baseline_extraction", "judge", "confidence", "compiler", "mcq", "schema"],
    }


def _units(category, values):
    if category == "event":
        return {(value["Event"], entity) for value in values for entity in value["Entity"]}
    return {(value["Head"], value["Relation"], value["Tail"]) for value in values}


def analyze(inputs, schedule, results):
    by_id = {row["request_id"]: row for row in results}
    if len(by_id) != len(results) or set(by_id) != {q["request_id"] for q in schedule}:
        raise ValueError("Results differ from the complete diagnostic schedule")
    groups = defaultdict(list)
    for query in schedule:
        groups[(query["diagnostic_method"], query["repetition"], query["category"], query["diagnostic_arm"])].append(query)
    output = []
    for (method, repeat, category, arm), queries in sorted(groups.items()):
        rows = [by_id[q["request_id"]] for q in queries]
        valid = [row for row in rows if row["status"] == "valid"]
        complete = len(valid) == len(queries)
        values = ([candidate["value"] for row in valid for candidate in row["parsed"]["candidates"]]
                  if method == "K" else [value for row in valid for value in row["parsed"]])
        existing = _units(category, inputs["baseline"][c.CATEGORIES[category]])
        produced = _units(category, values)
        detail = {
            "method": method, "repetition": repeat, "category": category, "arm": arm,
            "logical_requests": len(queries), "valid_requests": len(valid),
            "group_status": "complete" if complete else "partial" if valid else "failed",
            "failed_requests": [row["request_id"] for row in rows if row["status"] != "valid"],
            "raw_candidate_records": len(values) if complete else None,
            "exact_new_units": len(produced - existing) if complete else None,
            "exact_existing_units": len(produced & existing) if complete else None,
            "observed_raw_candidate_records": len(values),
            "observed_exact_new_units": len(produced - existing),
            "observed_exact_existing_units": len(produced & existing), "quality_assessed": False,
            "values": values,
        }
        if method == "K":
            bound = c.bind_candidates(inputs, queries, rows, deterministic_repairs=True)
            observed_bound = sum(x["status"] == "bound" for x in bound["bindings"])
            detail.update(source_bound_candidates=observed_bound if complete else None,
                          observed_source_bound_candidates=observed_bound,
                          binding_findings=dict(Counter(f for x in bound["bindings"] for f in x["findings"])),
                          candidate_bindings=bound["bindings"], candidates=bound["candidates"])
        else:
            detail["evidence_status"] = "No candidate-level evidence contract in native A. Source checking remains required."
        output.append(detail)
    return {"groups": output, "unit": "EE/VV exact SPO; EV exact Event-Entity pair",
            "claim": "Counts and span bindings do not establish source truth or semantic novelty."}


def execute(source, baseline, base_stage, output, *, repetitions=3, max_nodes=2, seed=SEED, resume=False):
    with immutable_publish.publication_scope(True):
        manifest = preflight(source, baseline, base_stage, output, repetitions=repetitions, max_nodes=max_nodes, seed=seed)
        inputs, history = load_inputs(source, baseline, base_stage)
        schedule, _ = plan(inputs, history, repetitions=repetitions, max_nodes=max_nodes, seed=seed)
        output = Path(output).resolve()
        stage_path = output / "construction"
        if output.exists():
            if not resume or not (output / "input_manifest.json").is_file():
                raise ValueError("Existing output requires --resume and frozen manifest")
            stages._same(output / "input_manifest.json", manifest)
            stages._same(output / "plan.json", schedule)
            stages._audit_stage(stage_path, schedule, PROTOCOL, schema_for, classify,
                                variant=VARIANT, context=CONTEXT)
        elif resume:
            raise ValueError("Cannot resume missing output")
        else:
            output.mkdir(parents=True)
        with retry_continuation.execution_lock(output):
            r.immutable(output / "input_manifest.json", manifest)
            r.immutable(output / "plan.json", schedule)
            r.immutable(output / "audit.json", {"sources": SOURCES, "B": manifest["B"],
                "selection_coverage": manifest["selection_coverage"],
                "A_source_policy": manifest["A_source_policy"], "K_source_policy": manifest["K_source_policy"],
                "segmentation_fallback": manifest["segmentation_fallback"]})
            results = stages._stage(stage_path, schedule, PROTOCOL, schema_for, classify,
                                    variant=VARIANT, context=CONTEXT)
            detail = analyze(inputs, schedule, results)
            r.immutable(output / "diagnostic_outputs.json", detail)
            costs = original_probe._cost_stage(stage_path, results)
            summary = {"variant": VARIANT, "status": "technically_complete_uninterpreted" if
                       all(row["status"] == "valid" for row in results) else "partial",
                       "logical_requests": len(schedule), "physical_attempts": costs["physical_attempts"],
                       "stage_costs": costs, "input_hashes": inputs["input_hashes"],
                       "selection_coverage": manifest["selection_coverage"],
                       "groups": [{k: v for k, v in group.items() if k not in
                                   ("values", "candidate_bindings", "candidates")} for group in detail["groups"]],
                       "B": manifest["B"], "claim": manifest["claim"], "paused": manifest["paused"]}
            r.immutable(output / "summary.json", summary)
            return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("source", "baseline", "base-stage", "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--max-nodes", type=int, default=2)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = vars(parser.parse_args(argv))
    live, resume = args.pop("execute"), args.pop("resume")
    if resume and not live:
        parser.error("--resume requires --execute")
    result = execute(**args, resume=resume) if live else preflight(**args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

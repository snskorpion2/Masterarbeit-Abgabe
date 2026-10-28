"""Finite strict temporal closure with replayable, content-bound proof DAGs.

Proof validity is conditional on supplied primitives. It does not establish
compiler binding correctness or the truth of a primitive in the source text.
Unknown relation kinds are inert. Malformed known primitives fail closed.
"""
from datetime import date
import hashlib
import json
from time import perf_counter

RULE_VERSION = "temporal_rules_v1"
DATE_RULE = RULE_VERSION + ":disjoint_bounds"
CHAIN_RULE = RULE_VERSION + ":transitivity"


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _order(primitive):
    if primitive["kind"] == "before":
        return primitive["head"], primitive["tail"]
    if primitive["kind"] == "after":
        return primitive["tail"], primitive["head"]
    return None


def _iso(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("Expected canonical ISO date")
    return value


def _prepare(primitives):
    """Validate terminals and analyze the explicit plus date-projected graph.

    This does not materialize transitive conclusions. Weak components of the
    full projected graph ensure excluded events cannot leak via date edges.
    """
    records, nodes, explicit, times = {}, set(), {}, {}
    for p in primitives:
        if not isinstance(p, dict) or not isinstance(p.get("id"), str) or not p["id"]:
            raise ValueError("Primitive needs a nonempty ID")
        if p["id"] in records:
            raise ValueError("Duplicate primitive ID")
        records[p["id"]] = p
        if p.get("kind") not in ("before", "after", "event_time"):
            continue
        sources = p.get("source_item_ids")
        if not isinstance(sources, list) or not sources or any(not isinstance(s, str) or not s for s in sources):
            raise ValueError("Primitive needs source item IDs")
        if not isinstance(p.get("input_spans"), list):
            raise ValueError("Primitive needs input spans")
        endpoints = [p.get("event_id")] if p["kind"] == "event_time" else [p.get("head"), p.get("tail")]
        if any(not isinstance(n, str) or not n for n in endpoints):
            raise ValueError("Primitive needs known event IDs")
        nodes.update(endpoints)
        if p["kind"] == "event_time":
            _iso(p.get("earliest_start"))
            _iso(p.get("latest_end"))
            times.setdefault(p["event_id"], []).append(p)
        else:
            pair = _order(p)
            if pair not in explicit or p["id"] < explicit[pair]["id"]:
                explicit[pair] = p

    conflicts = []
    bad = set()
    bounds = {}
    for event, entries in sorted(times.items()):
        low = min(entries, key=lambda p: (-date.fromisoformat(p["earliest_start"]).toordinal(), p["id"]))
        high = min(entries, key=lambda p: (p["latest_end"], p["id"]))
        bounds[event] = (low, high)
        if low["earliest_start"] > high["latest_end"]:
            bad.add(event)
            conflicts.append({"kind": "incompatible_bounds", "event_ids": [event],
                              "primitive_ids": sorted(p["id"] for p in entries)})
    projected = {}
    for a in sorted(bounds):
        for b in sorted(bounds):
            if a != b and bounds[a][1]["latest_end"] < bounds[b][0]["earliest_start"]:
                projected[a, b] = (bounds[a][1], bounds[b][0])
    adjacency = {n: set() for n in nodes}
    undirected = {n: set() for n in nodes}
    for a, b in set(explicit) | set(projected):
        adjacency[a].add(b)
        undirected[a].add(b)
        undirected[b].add(a)
    # A reachability search identifies cyclic vertices without recursion limits.
    cyclic = set()
    for start in sorted(nodes):
        visited, pending = set(), list(adjacency[start])
        while pending:
            node = pending.pop()
            if node == start:
                cyclic.add(start)
                break
            if node not in visited:
                visited.add(node)
                pending.extend(adjacency[node] - visited)
    unseen, excluded = set(nodes), []
    while unseen:
        pending, component = [min(unseen)], set()
        while pending:
            node = pending.pop()
            if node not in component:
                component.add(node)
                pending.extend(undirected[node] - component)
        unseen -= component
        if component & cyclic:
            conflicts.append({"kind": "temporal_cycle", "event_ids": sorted(component & cyclic)})
        if component & (cyclic | bad):
            excluded.append(sorted(component))
    excluded.sort()
    blocked = {n for component in excluded for n in component}
    return records, explicit, projected, conflicts, excluded, blocked


def _conclusion(head, tail, rule, premises):
    body = {"head": head, "relation": "before", "tail": tail,
            "rule_id": rule, "premise_ids": [p["id"] for p in premises],
            "premise_hashes": [_digest(p) for p in premises],
            "source_item_ids": sorted({s for p in premises for s in p["source_item_ids"]})}
    return {"id": "derived:" + _digest(body), **body}


def materialize(primitives: list[dict]) -> dict:
    """Return new before edges only, excluding conflicted weak components.

    Rule IDs distinguish direct date projection from temporal transitivity.
    Proof choice is deterministic: explicit terminals, then direct dates, then
    sorted synchronous closure rounds. A round only uses previous-round nodes.
    """
    started = perf_counter()
    _, explicit, projected, conflicts, excluded, blocked = _prepare(primitives)
    known = {pair: p for pair, p in explicit.items() if not set(pair) & blocked}
    derived = []
    for (a, b), premises in sorted(projected.items()):
        if (a, b) not in known and not {a, b} & blocked:
            d = _conclusion(a, b, DATE_RULE, premises)
            known[a, b] = d
            derived.append(d)
    while True:
        additions = {}
        for (a, b), first in sorted(known.items()):
            for (c, d), second in sorted(known.items()):
                if b == c and a != d and (a, d) not in known:
                    additions.setdefault((a, d), _conclusion(a, d, CHAIN_RULE, [first, second]))
        if not additions:
            break
        for pair, conclusion in sorted(additions.items()):
            known[pair] = conclusion
            derived.append(conclusion)
    return {"derived": derived, "conflicts": conflicts,
            "excluded_components": excluded, "elapsed_seconds": perf_counter() - started}


def verify_proof(conclusion: dict, primitives: list[dict], derived: list[dict]) -> bool:
    """Replay a proof independently of closure construction.

    Rechecks terminal contents, per-step rules, provenance unions and IDs,
    rejects cycles/missing premises and conflicted components. Source truth and
    compiler binding remain separate audits. This never invokes materialize.
    """
    try:
        terminals, explicit, _, _, _, blocked = _prepare(primitives)
        proofs = {}
        for record in derived:
            rid = record["id"]
            if rid in proofs or rid in terminals:
                return False
            proofs[rid] = record
        if conclusion["id"] in terminals:
            return False
        if conclusion["id"] in proofs and conclusion != proofs[conclusion["id"]]:
            return False
        proofs[conclusion["id"]] = conclusion
        active, verified = set(), {}

        def replay(rid):
            if rid in terminals:
                terminal = terminals[rid]
                if terminal.get("kind") not in ("before", "after", "event_time"):
                    raise ValueError("Not a temporal premise")
                return terminal
            if rid in active:
                raise ValueError("Cyclic proof")
            if rid in verified:
                return verified[rid]
            active.add(rid)
            step = proofs[rid]
            a, b = step["head"], step["tail"]
            if a == b or {a, b} & blocked or (a, b) in explicit:
                raise ValueError("Excluded or non-new conclusion")
            if len(step["premise_ids"]) != 2:
                raise ValueError("Expected two direct premises")
            premises = [replay(pid) for pid in step["premise_ids"]]
            left, right = premises
            if step["rule_id"] == DATE_RULE:
                if (left.get("kind") != "event_time" or right.get("kind") != "event_time"
                        or left["event_id"] != a or right["event_id"] != b
                        or not left["latest_end"] < right["earliest_start"]):
                    raise ValueError("Invalid date step")
            elif step["rule_id"] == CHAIN_RULE:
                def pair(record):
                    if record["id"] in terminals:
                        return _order(record)
                    return record["head"], record["tail"]
                lp, rp = pair(left), pair(right)
                if lp is None or rp is None or lp[0] != a or lp[1] != rp[0] or rp[1] != b:
                    raise ValueError("Invalid chain step")
            else:
                raise ValueError("Unknown rule")
            if step != _conclusion(a, b, step["rule_id"], premises):
                raise ValueError("Proof content, fingerprint or provenance mismatch")
            active.remove(rid)
            verified[rid] = step
            return step

        replay(conclusion["id"])
        return True
    except (KeyError, ValueError, TypeError, RecursionError, OverflowError):
        return False

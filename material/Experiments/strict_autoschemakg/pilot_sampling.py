"""Explicit small-pilot schedule; original judging functions remain unchanged."""
import argparse
import contextlib
import csv
import math
from pathlib import Path
from statistics import mean
from types import SimpleNamespace

from .contract import sha256, write_json


def validate_repetitions(value):
    if type(value) is not int or value < 1:
        raise ValueError("Pilot judge repetitions must be a positive integer")
    return value


def positive_integer(text):
    return validate_repetitions(int(text))


@contextlib.contextmanager
def sampling_scope(native, passage_count, repetitions):
    """Bind only the pinned original's range(100) and random.randint call.

    No source rewriting or global random-module mutation. The original function
    object, prompts, parsers, exception handling and metric formulas are retained.
    This is explicitly a methodological sampling deviation, not an I/O bridge.
    """
    validate_repetitions(repetitions)
    validate_repetitions(passage_count)
    indices = [index for index in range(passage_count) for _ in range(repetitions)]
    remaining = iter(indices)
    selected = []

    def pilot_range(*arguments):
        if arguments != (100,):
            raise ValueError("Unexpected native range call in pilot sampling")
        return range(len(indices))

    def randint(low, high):
        if (low, high) != (0, passage_count - 1):
            raise ValueError("Native passage count differs from the pilot schedule")
        index = next(remaining)
        selected.append(index)
        return index

    sentinel = object()
    previous = {name: vars(native).get(name, sentinel) for name in ("range", "random")}
    native.range = pilot_range
    native.random = SimpleNamespace(randint=randint)
    try:
        yield {"mode": "pilot_balanced_repetitions", "repetitions_per_passage": repetitions,
               "distinct_passages": passage_count, "passage_indices": indices}
        if selected != indices:
            raise ValueError("Native evaluator did not consume the declared pilot schedule")
    finally:
        for name, original in previous.items():
            if original is sentinel:
                vars(native).pop(name, None)
            else:
                setattr(native, name, original)


def summarize_csv(path):
    """Describe every completed CSV row, with missing denominators explicit."""
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = list(reader.fieldnames or [])
        if not columns or columns[0] != "i" or len(columns) < 2:
            raise ValueError("Expected native triple-accuracy CSV columns")
        rows = list(reader)

    def metrics(subset):
        result = {}
        for column in columns[1:]:
            values = [float(row[column]) for row in subset if row[column] not in (None, "")]
            values = [value for value in values if math.isfinite(value)]
            result[column] = {"valid": len(values), "missing": len(subset) - len(values),
                              "mean": mean(values) if values else None,
                              "min": min(values) if values else None,
                              "max": max(values) if values else None}
        return result

    indices = dict.fromkeys(row["i"] for row in rows)
    return {
        "source_csv_sha256": sha256(path), "completed_draws": len(rows),
        "distinct_passages": len(indices), "scientific_claim": False,
        "interpretation": "Repeated judgments of fixed extractions, not independent articles. No outcome-based row selection.",
        "metrics": metrics(rows),
        "by_passage": {index: {"completed_draws": sum(row["i"] == index for row in rows),
                                "metrics": metrics([row for row in rows if row["i"] == index])}
                       for index in indices},
    }


def main():
    parser = argparse.ArgumentParser(description="Summarize existing native judgments without model calls")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Summary already exists; preserve the previous evidence")
    write_json(args.output, summarize_csv(args.input))


if __name__ == "__main__":
    main()

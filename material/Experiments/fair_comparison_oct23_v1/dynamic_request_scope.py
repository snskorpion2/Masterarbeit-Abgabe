"""Exact pre-wire admission for a reviewed native tail or QA renderer.

The reviewed caller validates the original renderer outside HTTP and persists
its complete intent and declared body. File/code pins plus Main's review bind
that caller: the scope alone cannot prove who wrote an intent. This module
neither renders prompts nor selects a provider.
"""
from copy import deepcopy
from hashlib import sha256

from . import baseline
from .native_tail_worker import checked, pin, require


PROTOCOL = "pre-wire-sealed-dynamic-request-scope:oct23-v1"


class DynamicRequestScope:
    """Body admission only; reviewed runtime/QA guards own physical ordinals.

    A fresh scope may bind a later ordinal for a fresh QA admission. The tail
    factory derives it from runtime receipts; QA rotation checks client receipts.
    Direct scope construction is not execution approval or a replay counter.
    """
    def __init__(self, bindings, approved_bindings_sha256):
        require(type(bindings) is dict and set(bindings) == {"plan_pin", "source_pins",
                "carrier_producer_pins", "renderer_code_pins", "phase", "wire_parameters"},
                "Explicit plan/source/whole-carrier/renderer/wire bindings required")
        require(all(type(bindings[key]) is list and bindings[key] for key in
                ("source_pins", "carrier_producer_pins", "renderer_code_pins"))
                and type(bindings["phase"]) is str and bool(bindings["phase"])
                and type(bindings["wire_parameters"]) is dict and bindings["wire_parameters"]
                and "messages" not in bindings["wire_parameters"], "Complete reviewed binding groups required")
        self.bindings, self.binding_sha256 = deepcopy(bindings), approved_bindings_sha256
        self.current, self.last_ordinal, self._current_sha256 = None, -1, None
        self.verify()

    def verify(self):
        require(baseline.digest(self.bindings) == self.binding_sha256, "External scope binding differs")
        for item in [self.bindings["plan_pin"], *self.bindings["source_pins"],
                     *self.bindings["carrier_producer_pins"], *self.bindings["renderer_code_pins"]]:
            checked(item)
        if self.current is not None:
            require(baseline.digest(self.current) == self._current_sha256, "Current request binding changed")
            checked(self.current["intent_pin"])
            checked(self.current["declared_wire_request_pin"])

    def bind_current(self, ordinal, intent_pin, declared_wire_request_pin, expected_body_sha256):
        """Only after the frozen caller has checked the complete native render."""
        self.verify()
        intent, payload = checked(intent_pin, parse=True), checked(declared_wire_request_pin, parse=True)
        require(type(ordinal) is int and ordinal >= 0
                and (self.last_ordinal == -1 or ordinal == self.last_ordinal + 1),
                "Fresh consecutive physical ordinal required; no replay")
        require(type(intent) is dict and type(payload) is dict and intent.get("ordinal") == ordinal
                and intent.get("phase") == self.bindings["phase"]
                and intent.get("status") == "not_dispatched"
                and intent.get("declared_wire_payload_sha256") == expected_body_sha256 == baseline.digest(payload)
                and baseline.canonical(intent.get("messages")) == baseline.canonical(payload.get("messages"))
                and intent.get("prompt_sha256") == baseline.digest(payload.get("messages"))
                and baseline.canonical({k: v for k, v in payload.items() if k != "messages"})
                    == baseline.canonical(self.bindings["wire_parameters"]),
                "Persisted ordinal/phase/messages/full declared wire differs")
        self.current = {"ordinal": ordinal, "intent_pin": deepcopy(intent_pin),
            "declared_wire_request_pin": deepcopy(declared_wire_request_pin),
            "payload_sha256": expected_body_sha256}
        self.last_ordinal = ordinal
        self._current_sha256 = baseline.digest(self.current)
        self.verify()

    def admits_request(self, value):
        self.verify()
        return self.current is not None and baseline.digest(value) == self.current["payload_sha256"]

    def certificate(self):
        self.verify()
        return {"protocol": PROTOCOL, "bindings": deepcopy(self.bindings),
            "approved_bindings_sha256": self.binding_sha256, "current": deepcopy(self.current),
            "raw_body_publishable": False, "private_processing_is_publication_permission": False,
            "renderer_validation_required_outside_HTTP": True,
            "scope_alone_approves_execution_or_guarantees_physical_ordinals": False}


class _ClientOrdinalScope:
    """Freeze one QA admission against the receipt created by original _send."""
    def __init__(self, client, scope):
        self.client, self.scope = client, scope
        self.current = deepcopy(scope.current)
        self._current_sha256 = baseline.digest(self.current)
        self.verify()

    def verify(self):
        self.scope.verify()
        require(baseline.digest(self.current) == self._current_sha256
                == baseline.digest(self.scope.current), "Authorized QA scope changed after admission")

    def admits_request(self, value):
        self.verify()
        rows, ordinal = self.client.receipts, self.current["ordinal"]
        return (len(rows) == ordinal + 1 and rows[-1].get("ordinal") == ordinal
                and rows[-1].get("POST_attempts") == 0 and self.scope.admits_request(value))

    def certificate(self):
        self.verify()
        return {**self.scope.certificate(), "physical_client_ordinal": self.current["ordinal"],
                "current": deepcopy(self.current), "follows_mutable_scope_current": False}


def authorize_next_completed_request(client, next_scope):
    """Mandatory before each QA SDK request, including the first one.

    The installed adapter checks the actual original-client receipt ordinal.
    Never reset an unsettled/failed client or silently follow a rebound scope.
    """
    from .source_bound_private_policy import SourceBoundClient
    require(isinstance(client, SourceBoundClient), "Existing SourceBoundClient required")
    with client._lock:
        require(not client.halted and (client.config.url, client.config.key) == client._config_binding,
                "Failed transport or changed configuration cannot rotate")
        client.source_scope.verify()
        next_scope.verify()
        require(next_scope.current is not None and next_scope.current["ordinal"] == len(client.receipts),
                "Next physical request ordinal must already be sealed")
        if not client.receipts:
            require(client.authorized_request_digest is None, "Fresh client admission differs")
        else:
            row = client.receipts[-1]
            require(row.get("POST_attempts") == 1 and row.get("unknown_execution") is False
                    and row.get("error_class") is None and row.get("text_completion_confirmed") is True
                    and row.get("HTTP_body_complete") is True and row.get("http_status") == 200
                    and row.get("raw_body_saved") is True and row.get("response_archive_complete") is True,
                    "Only fully confirmed archived completion permits next request")
            ordinal = row["ordinal"]
            receipt = checked(pin(client.output / "calls" / f"{ordinal:04d}" / "receipt.json"), parse=True)
            require(baseline.canonical(receipt) == baseline.canonical(row), "Durable receipt differs")
            relative = f"private_raw/calls/{ordinal:04d}/response.raw"
            require(row.get("private_response_body_path") == relative
                    and sha256(checked(pin(client.output / relative))).hexdigest() == row.get("response_sha256"),
                    "Previous raw archive differs")
            old = client.source_scope.current
            require(all(next_scope.current[key]["path"] != old[key]["path"] for key in
                        ("intent_pin", "declared_wire_request_pin")),
                    "Every next physical call needs its own newly sealed intent and declared body")
        client.source_scope = _ClientOrdinalScope(client, next_scope)
        client.authorized_request_digest = None


def scoped_tail_runtime(output, *, max_calls, scope, wire_factory, request_validator, config=None):
    """Wrap only the existing runtime's entry, after ObservedRuntime seals files."""
    import inspect
    from . import source_bound_private_policy as private
    require(callable(request_validator), "Reviewed original-renderer checker required")
    validator_pin = pin(inspect.getsourcefile(request_validator))
    require(validator_pin in scope.bindings["renderer_code_pins"], "Checker implementation is not externally pinned")
    runtime = private.runtime(output, max_calls=max_calls, scope=scope,
                              wire_factory=wire_factory, config=config)
    native_generate = runtime.generate
    def generate(messages, parameters):
        try:
            require(not runtime.abort_required, "Previous failure blocks every further request")
            scope.verify()
            proof = request_validator(messages, runtime.output)
            require(type(proof) is dict and proof.get("complete") is True
                    and proof.get("prompt_sha256") == baseline.digest(messages),
                    "Original complete rendered prompt was not verified before HTTP")
            ordinal = len(runtime.receipts)
            folder = runtime.output / "observed_calls" / f"{ordinal:05d}"
            intent_pin, body_pin = pin(folder / "intent.json"), pin(folder / "declared-wire-request.json")
            body = checked(body_pin, parse=True)
            require(baseline.canonical(body.get("messages")) == baseline.canonical(messages),
                    "Checked renderer messages differ from persisted complete request")
            scope.bind_current(ordinal, intent_pin, body_pin, baseline.digest(body))
            return native_generate(messages, parameters)
        except BaseException:
            runtime.abort_required = True
            raise
    runtime.generate = generate
    return runtime

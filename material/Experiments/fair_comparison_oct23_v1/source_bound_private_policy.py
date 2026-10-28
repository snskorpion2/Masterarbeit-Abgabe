"""Explicit private-only transport policy for an approved source-bound suffix.

The existing/default publication and envelope policies stay untouched. Only
exact frozen native request objects from the separately approved roster can
enter this client. The complete original request/response is still scanned for
configured credential and endpoint reflection. Generic identifier/property-name
publication warnings do not, by themselves, forbid this private processing.
No request/response bytes are repaired, masked, paraphrased or published.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import time
from types import FunctionType, MethodType, SimpleNamespace
from urllib.parse import unquote, urlsplit

from Experiments.fair_comparison_oct23_v1 import baseline_precollection_worker as worker
from Tools.abschluss import hipporag2_foundry_client_v1 as original
from Tools.azure import response_diagnostics_v2 as diagnostics


PROTOCOL = "approved-source-bound-private-processing:oct23-v1"


class RequestScope:
    """No source-name/word whitelist: exact approved plan, source and body pins."""
    def __init__(self, plan_path, approved_plan_file_sha256, roster, approved_roster_sha256):
        plan, evidence = worker.load_plan(plan_path, approved_plan_file_sha256)
        worker.require(worker.baseline.digest(roster) == approved_roster_sha256,
                       "Explicit approved request roster differs")
        calls = [call for job in plan["jobs"] for call in job["calls"]]
        expected = [{"global_index":call["global_index"], "physical_call_id":call["physical_call_id"],
                     "payload_sha256":call["payload_sha256"]} for call in calls]
        worker.require(type(roster) is list and bool(roster)
                       and roster == expected[roster[0]["global_index"]:],
                       "Only an exact contiguous suffix of the original frozen roster is allowed")
        self.plan_pin, self.source_pins = evidence, deepcopy(plan["source_pins"])
        self.roster, self.roster_sha256 = deepcopy(roster), approved_roster_sha256
        self.body_hashes = frozenset(row["payload_sha256"] for row in roster)
        self.verify()

    def verify(self):
        worker.require(worker.preparation.pin(self.plan_pin["path"]) == self.plan_pin,
                       "Approved original source-only plan changed")
        for pin in self.source_pins:
            worker.require(worker.preparation.pin(pin["path"]) == pin,
                           "Authorized source-only input changed")

    def admits_request(self, value):
        self.verify()
        return worker.baseline.digest(value) in self.body_hashes

    def certificate(self):
        return {"protocol":PROTOCOL, "original_plan":deepcopy(self.plan_pin),
                "approved_request_roster_sha256":self.roster_sha256,
                "authorized_physical_calls":len(self.roster),
                "source_pins":deepcopy(self.source_pins),
                "raw_body_publishable":False, "private_processing_is_publication_permission":False}


def private_scan(raw, config):
    """Reuse strict parsing/accounting and existing bounded reflection views.

    The endpoint/full hostname are also treated as secret literals so the
    existing reflected() check covers their base64 spellings, not just keys.
    Return no provider fields, source strings, decoded data or metadata values.
    """
    if type(raw) is not bytes or len(raw) > diagnostics.MAX_BYTES:
        return False
    try:
        value = original.accounting.safe_object(raw, config, max_bytes=diagnostics.MAX_BYTES,
                                                 strict_json=original.probe._strict_json)
        text = raw.decode("utf8") + "\n" + worker.baseline.canonical(value).decode("utf8")
        endpoints = {config.url, urlsplit(config.url).hostname}
        endpoints.discard(None)
        protected = {config.key, *endpoints}
        # Same bounded decoders, including URL-spelled Unicode escapes. Do not
        # let the order of these existing scans conceal a configured value.
        for url_view in (text, unquote(text), unquote(unquote(text))):
            views, unresolved = diagnostics._publication_views(url_view)
            if unresolved or any(any(diagnostics.old.reflected(view, protected, endpoints)) for view in views):
                return False
        return True
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return False


def private_admission(capture):
    return (capture.get("private_policy_protocol") == PROTOCOL
            and capture.get("approved_source_bound_request") is True
            and capture.get("strict_JSON") is True
            and capture.get("HTTP_body_complete") is True
            and capture.get("configured_reflection_scan_passed") is True
            and capture.get("raw_body_publishable") is False)


class SourceBoundClient(original.FoundryNotebookClient):
    """Original SDK/_send/accounting/HTTP callback with an instance-only policy."""
    def __init__(self, output, *, scope, config, wire, model="deepseek.v3.2", timeout=300,
                 thinking=None, clock=time.monotonic, max_physical_posts=1,
                 expected_response_model="deepseek.v3.2"):
        scope.verify()
        self.source_scope, self.authorized_request_digest = scope, None
        # Same original function code; only its diagnostics/admission globals
        # are copied per instance. No process-wide monkeypatch or second send.
        local_diagnostics = SimpleNamespace(**vars(diagnostics))
        local_diagnostics.capture_metadata = self._private_capture
        native_send = original.FoundryNotebookClient._send
        namespace = dict(native_send.__globals__, diagnostics=local_diagnostics,
                         private_response_admission=private_admission)
        isolated = FunctionType(native_send.__code__, namespace, native_send.__name__,
                                native_send.__defaults__, native_send.__closure__)
        isolated.__kwdefaults__ = deepcopy(native_send.__kwdefaults__)
        self._send = MethodType(isolated, self)
        super().__init__(output, config=config, wire=wire, model=model, timeout=timeout,
                         thinking=thinking, clock=clock, max_physical_posts=max_physical_posts,
                         expected_response_model=expected_response_model)
        try:
            original._save(self.output / "source_bound_private_policy.json", worker.baseline.canonical({
                **scope.certificate(), "policy_code_sha256":sha256(Path(__file__).read_bytes()).hexdigest(),
                "original_send_code_reused":True, "shared_module_globals_mutated":False,
                "all_original_bytes_unchanged":True, "default_policy_unchanged":True,
                "SDK_max_retries":0, "actual_dispatch_approved_by_this_record":False}))
        except BaseException:
            self.client.close()
            raise

    def _private_capture(self, raw, secrets, endpoints, *, status=None, body_complete=True):
        # The supplied configured values are checked rather than trusted as
        # alternate configuration. Avoid emitting original scanner field data.
        configured = secrets == {self.config.key} and endpoints == {self.config.url}
        clean = configured and private_scan(raw, self.config)
        return {"private_policy_protocol":PROTOCOL,
                "approved_source_bound_request":self.authorized_request_digest is not None,
                "strict_JSON":bool(clean), "HTTP_body_complete":body_complete is True,
                "http_status":status if type(status) is int else None,
                "configured_reflection_scan_passed":bool(clean),
                "raw_body_publishable":False, "original_response_bytes_modified":False,
                "publication_permission_granted":False}

    def _safe_raw(self, raw):
        if not private_scan(raw, self.config):
            return False
        try:
            value = original.probe._strict_json(raw)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            return False
        if "messages" in value:
            if not self.source_scope.admits_request(value):
                return False
            digest = worker.baseline.digest(value)
            if self.authorized_request_digest not in (None, digest):
                return False
            self.authorized_request_digest = digest
            return True
        # Private response archival only after an exact source-bound request.
        return self.authorized_request_digest is not None


def runtime(output, *, max_calls, scope, wire_factory, config=None):
    """Reuse the whole pinned runtime; only select the new named client policy."""
    def definitions(path):
        reader, old, _unchanged_default = worker.existing.definitions(path)
        def client(*args, **kwargs):
            return SourceBoundClient(*args, scope=scope, **kwargs)
        return reader, old, SimpleNamespace(MantleClient=client)
    native_generate = worker.existing.MantleTailRuntime.generate
    namespace = dict(native_generate.__globals__, definitions=definitions)
    isolated = FunctionType(native_generate.__code__, namespace, native_generate.__name__,
                            native_generate.__defaults__, native_generate.__closure__)
    isolated.__kwdefaults__ = deepcopy(native_generate.__kwdefaults__)
    class SourceBoundRuntime(worker.existing.MantleTailRuntime):
        generate = isolated
    return SourceBoundRuntime(output, max_calls=max_calls, config=config, wire_factory=wire_factory)

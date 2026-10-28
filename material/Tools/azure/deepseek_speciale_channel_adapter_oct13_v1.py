"""Opt-in, exact-deployment DeepSeek channel adapter. No dispatch or booking.

This is a conditional format adapter, not a Foundry weights/revision attestation.
Historical strict outputs and booked costs stay unchanged. All returned text is
private. Only public_metadata() is suitable for publication. Existing accounting
and whole-fence handling are reused, never rebinding a frozen core module.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from Tools.azure import output_budget_probe_v2 as provider
from Tools.azure import probe
from Tools.hawki import evaluation_controls as common

DEPLOYMENT = "DeepSeek-V3.2-Speciale"
NATIVE_MODEL = "deepseek-v3.2-speciale"
CATALOGUE_SHA = "3e25ad6890df938b5b4b7a12127231d9cccc0030f7a62df5c0528174093c56cc"
PAIR_RESPONSE_SHA = "4bab35623458cfcd91fa3cf9381fc8414b28892eebdf1d2a2992da38a340b99d"
PROTOCOL = "foundry-deepseek-speciale-exact-opt-in-channel-adapter:oct13-v1"
SOURCE_PINS = {
    "model_card": "https://huggingface.co/deepseek-ai/DeepSeek-V3.2-Speciale/blob/c562883eda916fd699a44bbf1f4987a53b96008b/README.md",
    "model_card_revision": "c562883eda916fd699a44bbf1f4987a53b96008b",
    "reference_parser": "https://raw.githubusercontent.com/vllm-project/vllm/df6c7ad03194a3051a197d57ca4a94e4a063014e/vllm/reasoning/basic_parsers.py",
    "reference_parser_revision": "df6c7ad03194a3051a197d57ca4a94e4a063014e",
    "reference_parser_method": "BaseThinkingReasoningParser.extract_reasoning",
    "foundry_specific_native_channel_contract_independently_confirmed": False,
}
HELPER_PINS = {
    Path(provider.__file__): "51c31f260c0d905a307d92ddb06964b3e1ef16fef1b1d78fb9d1b3b3ad7896bb",
    Path(common.__file__): "f21e4ccdd692437e117761e368c7bde20cd233491ab4a93364e45e8157c6a161",
}
strict, canonical = probe._strict_json, common.canonical


def sha(raw):
    return sha256(raw).hexdigest()


def cpu_config():
    """No environment access. Only for replaying already captured private bytes."""
    return probe.Config("https://cpu-only.openai.azure.com/openai/v1/chat/completions",
                        "CPU_ONLY_NOT_A_REAL_SECRET_12859056", "openai.azure.com", False)


@dataclass(frozen=True)
class DeploymentBinding:
    root_opt_in: bool = False
    provider: str = "microsoft_foundry_openai_v1"
    requested_deployment: str = DEPLOYMENT
    native_model_id: str = NATIVE_MODEL
    catalogue_model_id: str = DEPLOYMENT
    catalogue_raw_sha256: str = CATALOGUE_SHA
    observed_pair_response_sha256: str = PAIR_RESPONSE_SHA
    actual_weights_revision: None = None

    def validate(self):
        wanted = DeploymentBinding(root_opt_in=True)
        if any(getattr(self, name) != getattr(wanted, name)
               or type(getattr(self, name)) is not type(getattr(wanted, name))
               for name in self.__dataclass_fields__):
            raise ValueError("Exact Root opt-in deployment/native pair required")


@dataclass(frozen=True)
class PrivateResult:
    private_reasoning: str | None = field(repr=False)
    private_final_text: str = field(repr=False)
    private_clean_json_text: str = field(repr=False)
    private_json: object = field(repr=False)
    _metadata: dict = field(repr=False)

    def public_metadata(self):
        return deepcopy(self._metadata)


def helper_bindings():
    for path, expected in HELPER_PINS.items():
        if sha(path.read_bytes()) != expected:
            raise ValueError("Existing provider/fence helper changed")
    return {path.name: expected for path, expected in HELPER_PINS.items()}


def _whole_json(text):
    try:
        return strict(text), text, []
    except (ValueError, TypeError, UnicodeError, RecursionError):
        clean, bridges = common.unwrap_format(text)
        if not bridges:
            raise ValueError("No valid whole JSON or complete known fence") from None
        try:
            return strict(clean), clean, bridges
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise ValueError("Known whole fence contains invalid JSON") from None


def _split_private(message):
    text = message.get("content")
    if not isinstance(text, str):
        raise ValueError("Nonempty final text required")
    separate = "reasoning_content" in message
    thinking = message.get("reasoning_content") if separate else None
    if separate and not isinstance(thinking, str):
        raise ValueError("Existing reasoning channel must be text")
    # Protect every already-valid JSON literal, including strings containing tags.
    try:
        value, clean, fences = _whole_json(text)
        return thinking, text, clean, value, fences, (
            "none_native_separate_channels" if separate else "none_native_final")
    except ValueError:
        if separate:
            raise ValueError("already_separate_final_invalid") from None
    opening, closing = "<think>", "</think>"
    if text.count(closing) != 1 or text.count(opening) not in (0, 1):
        raise ValueError("Exactly one unambiguous end marker required")
    explicit = text.count(opening) == 1
    if explicit and not text.startswith(opening):
        raise ValueError("Explicit opening must start the content")
    end = text.index(closing)
    start = len(opening) if explicit else 0
    if end < start:
        raise ValueError("Thinking marker order invalid")
    thinking, final = text[start:end], text[end + len(closing):]
    value, clean, fences = _whole_json(final)
    return thinking, final, clean, value, fences, (
        "explicit_open_thinking_single_end" if explicit else "implicit_open_thinking_single_end")


def adapt_completed_response(request_raw, response_raw, receipt, *, binding, config):
    """Reuse a single already-booked, privately saved completed response.

    Caller must project its existing receipt losslessly to this explicit contract.
    No receipt/status/cost is rewritten. Returned JSON still needs the consumer's
    unchanged semantic/schema validation. Length and unknown execution never pass.
    """
    if type(binding) is not DeploymentBinding:
        raise ValueError("Explicit bound deployment object required")
    binding.validate()
    helpers = helper_bindings()
    if (type(request_raw) is not bytes or type(response_raw) is not bytes
            or type(receipt) is not dict):
        raise ValueError("Original byte bodies and typed receipt required")
    request = strict(request_raw)
    if (type(request) is not dict or request.get("model") != binding.requested_deployment
            or request.get("stream", False) is not False
            or type(request.get("n", 1)) is not int or request.get("n", 1) != 1
            or any(key in request for key in ("tools", "tool_choice", "functions", "function_call"))
            or type(request.get("max_completion_tokens")) is not int
            or request["max_completion_tokens"] <= 0):
        raise ValueError("Exact deployment/no-tools/nonstream positive output cap required")
    expected_receipt = {
        "http_status": 200, "POST_attempts": 1, "response_complete": True,
        "provider_completion_confirmed": True, "unknown_execution": False,
        "physical_dispatch_performed": True, "private_admitted": True,
        "raw_saved_privately": True, "response_archive_complete": True,
        "metering_complete": True, "requested_model": binding.requested_deployment,
        "finish_reason": "stop", "request_sha256": sha(request_raw),
        "response_sha256": sha(response_raw), "response_body_sha256": sha(response_raw),
        "response_bytes": len(response_raw),
    }
    if any(receipt.get(k) != v or type(receipt.get(k)) is not type(v)
           for k, v in expected_receipt.items()):
        raise ValueError("Confirmed private single-response hash/terminal receipt required")
    text, details = provider.provider_response(response_raw, config, request["max_completion_tokens"])
    reported = receipt.get("provider_usage")
    if (type(reported) is not dict or set(reported) != set(details["provider_usage"])
            or any(reported[k] != v or type(reported[k]) is not type(v)
                   for k, v in details["provider_usage"].items())
            or details["provider_model"] != binding.native_model_id
            or details["finish_reason"] != "stop" or not details["metering_complete"]
            or not details["completion_within_requested_cap"]
            or details["provider_usage"]["prompt_tokens"] > len(request_raw) + 256):
        raise ValueError("Exact native identity/completion/usage/cap contract differs")
    envelope = strict(response_raw)
    message = envelope["choices"][0].get("message")
    if (type(message) is not dict or message.get("role") != "assistant"
            or any(k in message for k in ("tool_calls", "function_call"))
            or message.get("refusal") not in (None, "")):
        raise ValueError("Unambiguous assistant final channel required")
    thinking, final, clean, value, fences, bridge = _split_private(message)
    if helper_bindings() != helpers:
        raise ValueError("Existing helper changed during decode")
    return PrivateResult(thinking, final, clean, value, {
        "protocol": PROTOCOL, "conditional_opt_in_format_adapter_only": True,
        "requested_deployment": binding.requested_deployment,
        "observed_native_model": binding.native_model_id,
        "independent_model_identity_verified": False, "actual_weights_revision": None,
        "foundry_channel_contract_independently_verified": False,
        "request_sha256": sha(request_raw), "response_sha256": sha(response_raw),
        "channel_bridge": bridge, "reasoning_characters": len(thinking) if thinking is not None else None,
        "final_characters": len(final), "final_text_sha256": sha(final.encode("utf-8")),
        "clean_json_text_sha256": sha(clean.encode("utf-8")),
        "fence_bridges_count": len(fences), "helper_sha256": helpers,
        "native_usage_recheck_not_new_cost": deepcopy(details["provider_usage"]),
        "cost_bookings_created": 0, "model_calls": 0,
        "semantic_or_schema_validity_verified": False, "quality_measured": False,
        "historical_results_modified": False,
    })

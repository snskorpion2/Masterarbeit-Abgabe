"""Opt-in import-only adapter for the unchanged original schema CPU replay.

Execute complete verified original converter modules without their expensive
package initializers. No original function body, data mapping or global import
state is patched. The frozen schema bridge body remains the operative code.
"""
import builtins
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace

from . import sdk_schema_bridge as frozen
from Experiments.strict_autoschemakg import contract as native

VERSION = 'isolated-original-schema-module-imports-cpu:oct23-v1'
FROZEN_SHA = '9935436ee4297798b938ae4065e3585be7a9a21968e2cb05c31d04fa89828c32'
ORIGINAL_MODULES = {
    'json_to_csv': 'atlas_rag/kg_construction/utils/json_processing/json_to_csv.py',
    'csv_to_graphml': 'atlas_rag/kg_construction/utils/csv_processing/csv_to_graphml.py',
    'concept_to_csv': 'atlas_rag/kg_construction/concept_to_csv.py',
    'triple_config': 'atlas_rag/kg_construction/triple_config.py',
    'schema': 'atlas_rag/llm_generator/format/validate_json_schema.py',
}


def _pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': sha256(raw).hexdigest()}


class _OriginalModules:
    """Five fixed original modules, one invocation-local namespace each."""
    def __init__(self):
        self.proof = native.verify_source(native.DEFAULT_SOURCE)
        self.modules, self.pins = {}, {}

    def load(self, key):
        if key not in self.modules:
            relative = ORIGINAL_MODULES[key]
            path = native.DEFAULT_SOURCE / relative
            raw = path.read_bytes()
            digest = sha256(raw).hexdigest()
            if digest != self.proof['files'][relative]['sha256']:
                raise ValueError('Original module changed after verification')
            module = ModuleType('isolated_original_cpu_' + key)
            module.__file__ = str(path)
            module.__dict__['__builtins__'] = dict(vars(builtins), __import__=self.import_module)
            exec(compile(raw, str(path), 'exec'), module.__dict__)
            self.modules[key] = module
            self.pins[key] = {'path': str(path.resolve()), 'bytes': len(raw), 'sha256': digest}
        return self.modules[key]

    def import_module(self, name, globals=None, locals=None, fromlist=(), level=0):
        requested = tuple(fromlist or ())
        if level == 0:
            if name == 'atlas_rag.kg_construction.utils.json_processing' and requested == ('json_to_csv',):
                return SimpleNamespace(json_to_csv=self.load('json_to_csv'))
            if name == 'atlas_rag.kg_construction.utils.csv_processing' and requested == ('csv_to_graphml',):
                return SimpleNamespace(csv_to_graphml=self.load('csv_to_graphml'))
            if name == 'atlas_rag.llm_generator.format.validate_json_schema' and requested == ('ATLAS_SCHEMA',):
                return self.load('schema')
            if name == 'atlas_rag.kg_construction.triple_config' and requested == ('ProcessingConfig',):
                return self.load('triple_config')
            if name == 'atlas_rag.kg_construction.concept_to_csv' and requested == ('all_concept_triples_csv_to_csv',):
                return self.load('concept_to_csv')
        return builtins.__import__(name, globals, locals, fromlist, level)

    def verify_after(self):
        if any(_pin(pin['path']) != pin for pin in self.pins.values()):
            raise ValueError('Original converter module changed during CPU replay')


def build_sdk_schema_bindings(*args, **kwargs):
    if _pin(frozen.__file__)['sha256'] != FROZEN_SHA:
        raise ValueError('Frozen schema replay bridge changed')
    modules = _OriginalModules()
    original = frozen.build_sdk_schema_bindings
    namespace = dict(original.__globals__, __builtins__=dict(vars(builtins), __import__=modules.import_module))
    isolated = FunctionType(original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__)
    isolated.__kwdefaults__ = deepcopy(original.__kwdefaults__)
    result = isolated(*args, **kwargs)
    modules.verify_after()
    if _pin(frozen.__file__)['sha256'] != FROZEN_SHA:
        raise ValueError('Frozen schema bridge changed during CPU replay')
    result['CPU_import_adapter'] = {'protocol': VERSION, 'frozen_bridge_sha256': FROZEN_SHA,
        'original_module_pins': list(modules.pins.values()), 'original_SDK_commit': modules.proof['commit'],
        'complete_original_module_bytes_executed': True, 'original_function_bodies_edited': False,
        'sys_modules_or_global_import_monkeypatch': False, 'new_model_calls': 0}
    return result

"""Load atlas_rag from verified source bytes, never from bytecode caches."""

import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path

from . import contract


def _native_name(name):
    return name == "atlas_rag" or name.startswith("atlas_rag.")


class _VerifiedLoader(importlib.machinery.SourceFileLoader):
    def __init__(self, name, path, expected_hash, owned):
        super().__init__(name, str(path))
        self.expected_hash = expected_hash
        self.owned = owned

    def get_code(self, fullname):
        # SourceFileLoader.get_code would accept timestamp-valid .pyc files.
        # Compile the very bytes checked here instead of reading them twice.
        path = Path(self.path)
        if path.is_symlink():
            raise ValueError(f"Verlinkte Originalquelle beim Import: {self.name}")
        source = path.read_bytes()
        if hashlib.sha256(source).hexdigest() != self.expected_hash:
            raise ValueError(f"Geänderte Originalquelle beim Import: {self.name}")
        return self.source_to_code(source, self.path)

    def exec_module(self, module):
        self.owned[self.name] = module
        super().exec_module(module)


class _VerifiedFinder(importlib.abc.MetaPathFinder):
    def __init__(self, source, files):
        self.source = source
        self.files = files
        self.owned = {}

    def find_spec(self, fullname, path=None, target=None):
        if not _native_name(fullname):
            return None
        relative = fullname.replace(".", "/")
        for candidate, is_package in ((relative + "/__init__.py", True), (relative + ".py", False)):
            if candidate not in self.files:
                continue
            source_path = self.source / candidate
            loader = _VerifiedLoader(fullname, source_path, self.files[candidate]["sha256"], self.owned)
            return importlib.util.spec_from_file_location(
                fullname, source_path, loader=loader,
                submodule_search_locations=[str(source_path.parent)] if is_package else None,
            )
        # Do not let another finder resolve an unverified module or extension.
        raise ModuleNotFoundError(f"Keine verifizierte Originalquelle für {fullname}", name=fullname)


@contextmanager
def verified_source_imports(source):
    """Guard initial and deferred native imports for one complete construction.

    A fresh CLI process is required: module origin alone cannot establish which
    source bytes were previously executed. Third-party modules remain untouched.
    """
    loaded = sorted(name for name in sys.modules if _native_name(name))
    if loaded:
        raise ValueError("Originalmodule bereits geladen, bitte neuen Prozess starten: " + ", ".join(loaded))
    source = Path(source).resolve()
    finder = _VerifiedFinder(source, contract.verify_source(source)["files"])
    sys.meta_path.insert(0, finder)
    try:
        yield
    finally:
        sys.meta_path[:] = [entry for entry in sys.meta_path if entry is not finder]
        for name, module in finder.owned.items():
            if sys.modules.get(name) is module:
                del sys.modules[name]

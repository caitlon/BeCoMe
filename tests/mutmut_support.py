"""pytest plugin that lets mutmut 3 drive this project's tests.

Loaded only by the `[tool.mutmut]` settings in `pyproject.toml` (`-p tests.mutmut_support`),
never by a normal test run. Two things in mutmut 3 do not fit this project:

- mutmut names a mutated module without a leading `src.` and fails the stats run on a
  module whose name has one. The package here is literally called `src` and the tests
  import `src.models...`, so `src.X` is registered as an alias of the module `X`
  (mutmut puts `mutants/src` on the import path, so `X` resolves to the mutated copy).
- mutmut calls `pytest.main` several times in one process, which makes hypothesis
  raise `differing_executors` for every `@given` test method on the second call.
"""

import importlib
import sys
import types
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec

from hypothesis import HealthCheck, settings

_PREFIX = "src."


class _AliasLoader(Loader):
    def create_module(self, spec: ModuleSpec) -> types.ModuleType:
        return importlib.import_module(spec.name.removeprefix(_PREFIX))

    def exec_module(self, module: types.ModuleType) -> None:
        """Nothing to run: create_module returned an already executed module."""


class _AliasFinder(MetaPathFinder):
    def find_spec(
        self, fullname: str, path: object = None, target: object = None
    ) -> ModuleSpec | None:
        if fullname.startswith(_PREFIX):
            return ModuleSpec(fullname, _AliasLoader())
        return None


def _install_src_alias() -> None:
    src_package = types.ModuleType("src")
    src_package.__path__ = []
    sys.modules["src"] = src_package
    sys.meta_path.insert(0, _AliasFinder())


_install_src_alias()
settings.register_profile("mutmut", suppress_health_check=[HealthCheck.differing_executors])
settings.load_profile("mutmut")

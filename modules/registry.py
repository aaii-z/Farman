from __future__ import annotations

import importlib
import pathlib

import structlog

from modules.base import BaseModule, ParsedIntent

log = structlog.get_logger()

_registry: dict[str, BaseModule] = {}


def _discover() -> None:
    modules_dir = pathlib.Path(__file__).parent
    for handler_path in modules_dir.glob("*/handler.py"):
        pkg = handler_path.parent.name
        try:
            mod = importlib.import_module(f"modules.{pkg}.handler")
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseModule)
                    and attr is not BaseModule
                ):
                    instance: BaseModule = attr()
                    _registry[instance.name] = instance
                    log.info("module_registered", name=instance.name)
        except Exception as exc:
            log.error("module_load_failed", pkg=pkg, error=str(exc))


def get_registry() -> dict[str, BaseModule]:
    if not _registry:
        _discover()
    return _registry


def find_module(labels: list[str], intent: ParsedIntent) -> BaseModule | None:
    for module in get_registry().values():
        if module.can_handle(labels, intent):
            return module
    return None

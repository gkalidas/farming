from modules.base import BaseModule

_registry: dict[str, BaseModule] = {}


def register(module: BaseModule):
    _registry[module.name] = module


def get(name: str) -> BaseModule | None:
    return _registry.get(name)


def all_modules() -> list[BaseModule]:
    return list(_registry.values())

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ModuleContext:
    module_name: str
    available: bool
    summary: str             # injected verbatim into inference prompt
    detail: dict = field(default_factory=dict)   # structured data for the UI


class BaseModule(ABC):
    """
    Every parameter module implements this contract.
    Takes crop + location + date, returns a ModuleContext.
    Adding a new parameter = one new file that subclasses this.
    """
    name: str = ""

    @abstractmethod
    async def get_context(self, crop: str, location: str, date: str) -> ModuleContext:
        pass

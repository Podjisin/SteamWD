"""Game-specific Workshop content processors."""

from steamwd.processors.base import ModProcessor
from steamwd.processors.generic import GenericProcessor
from steamwd.processors.rimworld import RimWorldProcessor
from steamwd.processors.stellaris import StellarisProcessor

__all__ = ["ModProcessor", "processor_for", "processor_name", "supported_processors"]

_PROCESSORS: dict[int, tuple[str, ModProcessor]] = {
    281990: ("Stellaris", StellarisProcessor()),
    294100: ("RimWorld", RimWorldProcessor()),
}
_GENERIC = GenericProcessor()


def processor_for(app_id: int) -> ModProcessor:
    """Return the registered processor for a Steam app, or the generic fallback."""
    return _PROCESSORS.get(app_id, ("Generic", _GENERIC))[1]


def processor_name(app_id: int) -> str:
    """Return the display name of the processor selected for an app."""
    return _PROCESSORS.get(app_id, ("Generic", _GENERIC))[0]


def supported_processors() -> tuple[tuple[int, str], ...]:
    """Return built-in processors as ``(Steam app ID, display name)`` pairs."""
    return tuple((app_id, name) for app_id, (name, _) in _PROCESSORS.items())

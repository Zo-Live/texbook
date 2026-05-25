"""Shared LaTeX output style options."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BeamerBoxStyle(str, Enum):
    """Supported Beamer emphasis box styles."""

    block = "block"
    tcolorbox = "tcolorbox"


class CtexFontProfile(str, Enum):
    """Supported CTeX font profiles."""

    default = "default"
    local = "local"


@dataclass(frozen=True)
class LatexOutputOptions:
    """Options that affect generated LaTeX source and LLM prompts."""

    beamer_box_style: BeamerBoxStyle = BeamerBoxStyle.block
    ctex_font_profile: CtexFontProfile = CtexFontProfile.default
    beamer_title_page: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "beamer_box_style",
            _coerce_enum(BeamerBoxStyle, self.beamer_box_style),
        )
        object.__setattr__(
            self,
            "ctex_font_profile",
            _coerce_enum(CtexFontProfile, self.ctex_font_profile),
        )
        object.__setattr__(self, "beamer_title_page", bool(self.beamer_title_page))

    def to_metadata(self) -> dict[str, object]:
        """Return a stable representation for project metadata and caches."""
        return {
            "beamer_box_style": self.beamer_box_style.value,
            "ctex_font_profile": self.ctex_font_profile.value,
            "beamer_title_page": self.beamer_title_page,
        }


def _coerce_enum(enum_type, value):
    if isinstance(value, enum_type):
        return value
    return enum_type(str(value))


DEFAULT_OUTPUT_OPTIONS = LatexOutputOptions()

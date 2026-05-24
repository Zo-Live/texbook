"""Convert extracted content to LaTeX document source."""

import re

from typing import List

from ..extract.base import ExtractedContent


_DOCUMENTCLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{[^}]+\}")
_USEPACKAGE_RE = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{[^}]+\}")

_ESCAPE_MAP = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "$": r"\$",
    "&": r"\&",
    "#": r"\#",
    "^": r"\^{}",
    "_": r"\_",
    "%": r"\%",
    "~": r"\textasciitilde{}",
}
_ESCAPE_RE = re.compile("[" + re.escape("".join(_ESCAPE_MAP)) + "]")

_UNICODE_MATH_MAP = {
    "∉": r"\(\notin\)",
    "≠": r"\(\ne\)",
    "∉": r"\(\notin\)",
    "≤": r"\(\le\)",
    "≥": r"\(\ge\)",
    "≠": r"\(\ne\)",
    "∈": r"\(\in\)",
    "∅": r"\(\emptyset\)",
    "∀": r"\(\forall\)",
    "∃": r"\(\exists\)",
    "⊆": r"\(\subseteq\)",
    "⊂": r"\(\subset\)",
    "∩": r"\(\cap\)",
    "∪": r"\(\cup\)",
    "⇒": r"\(\Rightarrow\)",
    "⇐": r"\(\Leftarrow\)",
    "⇔": r"\(\Leftrightarrow\)",
    "↔": r"\(\leftrightarrow\)",
    "→": r"\(\to\)",
    "←": r"\(\leftarrow\)",
    "∨": r"\(\vee\)",
    "∧": r"\(\wedge\)",
    "¬": r"\(\neg\)",
    "ℵ": r"\(\aleph\)",
    "ϵ": r"\(\epsilon\)",
    "ε": r"\(\epsilon\)",
    "ϕ": r"\(\phi\)",
    "φ": r"\(\phi\)",
    "α": r"\(\alpha\)",
    "β": r"\(\beta\)",
    "γ": r"\(\gamma\)",
    "δ": r"\(\delta\)",
    "η": r"\(\eta\)",
    "θ": r"\(\theta\)",
    "κ": r"\(\kappa\)",
    "λ": r"\(\lambda\)",
    "ξ": r"\(\xi\)",
    "σ": r"\(\sigma\)",
    "τ": r"\(\tau\)",
    "ω": r"\(\omega\)",
    "Π": r"\(\Pi\)",
    "Θ": r"\(\Theta\)",
    "′": r"\(^{\prime}\)",
    "−": r"\(-\)",
    "×": r"\(\times\)",
    "±": r"\(\pm\)",
    "∗": r"\(\ast\)",
    "⋆": r"\(\star\)",
    "⊕": r"\(\oplus\)",
    "∫": r"\(\int\)",
    "∑": r"\(\sum\)",
    "√": r"\(\sqrt{\;}\)",
    "∼": r"\(\sim\)",
    "✓": r"\(\checkmark\)",
    "◦": r"\(\circ\)",
    "¯": r"\(\overline{\phantom{x}}\)",
    "\u0338": "",
}
_UNICODE_MATH_RE = re.compile(
    "|".join(
        re.escape(symbol)
        for symbol in sorted(_UNICODE_MATH_MAP, key=len, reverse=True)
    )
)

_INVALID_CHAR_TRANSLATION = {
    codepoint: None
    for codepoint in range(32)
    if codepoint not in (ord("\t"), ord("\n"), ord("\r"))
}


class LatexConverter:
    """Converts ExtractedContent to a complete LaTeX document string."""

    def __init__(self, use_ctex: bool = True):
        self.use_ctex = use_ctex

    def convert(self, content: ExtractedContent, *, show_date: bool = False) -> str:
        lines: List[str] = []
        lines.append("% !TEX program = xelatex")
        docclass = r"\documentclass[UTF8]{ctexart}" if self.use_ctex else r"\documentclass{article}"
        lines.append(docclass)
        lines.append(r"\usepackage{amsmath}")
        lines.append(r"\usepackage{amsthm}")
        lines.append(r"\usepackage{amssymb}")
        lines.append(r"\newtheorem{definition}{定义}")
        lines.append(r"\newtheorem{theorem}{定理}")
        lines.append(r"\newtheorem{lemma}{引理}")
        lines.append(r"\newtheorem{property}{性质}")
        lines.append(r"\newtheorem{corollary}{推论}")
        lines.append(r"\newtheorem{example}{例}")
        lines.append("")
        lines.append(r"\title{" + self._escape_latex(content.title) + "}")
        lines.append(self._date_line(show_date))
        lines.append("")
        lines.append(r"\begin{document}")
        lines.append(r"\maketitle")
        lines.append("")

        for block in content.blocks:
            text = self._escape_latex(block.text)

            if block.block_type == "heading":
                lines.append(r"\section{" + text + "}")
                lines.append("")
            elif block.block_type == "definition":
                lines.append(r"\begin{definition}")
                lines.append("  " + text)
                lines.append(r"\end{definition}")
                lines.append("")
            elif block.block_type == "theorem":
                lines.append(r"\begin{theorem}")
                lines.append("  " + text)
                lines.append(r"\end{theorem}")
                lines.append("")
            elif block.block_type == "lemma":
                lines.append(r"\begin{lemma}")
                lines.append("  " + text)
                lines.append(r"\end{lemma}")
                lines.append("")
            elif block.block_type == "property":
                lines.append(r"\begin{property}")
                lines.append("  " + text)
                lines.append(r"\end{property}")
                lines.append("")
            elif block.block_type == "corollary":
                lines.append(r"\begin{corollary}")
                lines.append("  " + text)
                lines.append(r"\end{corollary}")
                lines.append("")
            elif block.block_type == "example":
                lines.append(r"\begin{example}")
                lines.append("  " + text)
                lines.append(r"\end{example}")
                lines.append("")
            elif block.block_type == "proof":
                lines.append(r"\begin{proof}")
                lines.append("  " + text)
                lines.append(r"\end{proof}")
                lines.append("")
            else:
                lines.append(text)
                lines.append("")

        lines.append(r"\end{document}")
        lines.append("")
        return "\n".join(lines)

    def convert_fragments(
        self,
        *,
        title: str,
        fragments: List[str],
        notes: List[str] | None = None,
        show_date: bool = False,
    ) -> str:
        """Build a complete LaTeX document from trusted body fragments."""
        lines = self._document_header(title, show_date=show_date)
        for note in notes or []:
            sanitized_note = note.replace("\n", " ").strip()
            if sanitized_note:
                lines.append("% LLM note: " + sanitized_note)
        if notes:
            lines.append("")

        for fragment in fragments:
            cleaned = self._clean_body_fragment(fragment)
            if not cleaned:
                continue
            lines.append(cleaned)
            lines.append("")

        lines.append(r"\end{document}")
        lines.append("")
        return "\n".join(lines)

    def _document_header(self, title: str, *, show_date: bool = False) -> List[str]:
        docclass = r"\documentclass[UTF8]{ctexart}" if self.use_ctex else r"\documentclass{article}"
        return [
            "% !TEX program = xelatex",
            docclass,
            r"\usepackage{amsmath}",
            r"\usepackage{amsthm}",
            r"\usepackage{amssymb}",
            r"\newtheorem{definition}{定义}",
            r"\newtheorem{theorem}{定理}",
            r"\newtheorem{lemma}{引理}",
            r"\newtheorem{property}{性质}",
            r"\newtheorem{corollary}{推论}",
            r"\newtheorem{example}{例}",
            "",
            r"\title{" + self._escape_latex(title) + "}",
            self._date_line(show_date),
            "",
            r"\begin{document}",
            r"\maketitle",
            "",
        ]

    def _date_line(self, show_date: bool) -> str:
        return r"\date{\today}" if show_date else r"\date{}"

    def _clean_body_fragment(self, fragment: str) -> str:
        text = fragment.strip()
        text = _DOCUMENTCLASS_RE.sub("", text)
        text = _USEPACKAGE_RE.sub("", text)
        text = text.replace(r"\begin{document}", "")
        text = text.replace(r"\end{document}", "")
        return text.strip()

    def _escape_latex(self, text: str) -> str:
        text = self._strip_invalid_chars(text)
        text = _ESCAPE_RE.sub(lambda match: _ESCAPE_MAP[match.group(0)], text)
        return self._replace_unicode_math(text)

    def _strip_invalid_chars(self, text: str) -> str:
        return text.translate(_INVALID_CHAR_TRANSLATION)

    def _replace_unicode_math(self, text: str) -> str:
        return _UNICODE_MATH_RE.sub(
            lambda match: _UNICODE_MATH_MAP[match.group(0)],
            text,
        )

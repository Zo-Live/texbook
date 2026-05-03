"""Convert extracted content to LaTeX document source."""

from typing import List

from ..extract.base import ContentBlock, ExtractedContent


class LatexConverter:
    """Converts ExtractedContent to a complete LaTeX document string."""

    def __init__(self, use_ctex: bool = True):
        self.use_ctex = use_ctex

    def convert(self, content: ExtractedContent) -> str:
        lines: List[str] = []
        lines.append("% !TEX program = xelatex")
        docclass = r"\documentclass[UTF8]{ctexart}" if self.use_ctex else r"\documentclass{article}"
        lines.append(docclass)
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
        lines.append(r"\date{\today}")
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

    def _escape_latex(self, text: str) -> str:
        text = self._strip_invalid_chars(text)
        replacements = [
            ("\\", r"\textbackslash{}"),
            ("{", r"\{"),
            ("}", r"\}"),
            ("$", r"\$"),
            ("&", r"\&"),
            ("#", r"\#"),
            ("^", r"\^{}"),
            ("_", r"\_"),
            ("%", r"\%"),
            ("~", r"\textasciitilde{}"),
        ]
        for old, new in replacements:
            text = text.replace(old, new)
        return self._replace_unicode_math(text)

    def _strip_invalid_chars(self, text: str) -> str:
        return "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 32)

    def _replace_unicode_math(self, text: str) -> str:
        replacements = [
            ("∉", r"\(\notin\)"),
            ("≠", r"\(\ne\)"),
            ("∉", r"\(\notin\)"),
            ("≤", r"\(\le\)"),
            ("≥", r"\(\ge\)"),
            ("≠", r"\(\ne\)"),
            ("∈", r"\(\in\)"),
            ("∅", r"\(\emptyset\)"),
            ("∀", r"\(\forall\)"),
            ("∃", r"\(\exists\)"),
            ("⊆", r"\(\subseteq\)"),
            ("⊂", r"\(\subset\)"),
            ("∩", r"\(\cap\)"),
            ("∪", r"\(\cup\)"),
            ("⇒", r"\(\Rightarrow\)"),
            ("⇐", r"\(\Leftarrow\)"),
            ("⇔", r"\(\Leftrightarrow\)"),
            ("↔", r"\(\leftrightarrow\)"),
            ("→", r"\(\to\)"),
            ("←", r"\(\leftarrow\)"),
            ("∨", r"\(\vee\)"),
            ("∧", r"\(\wedge\)"),
            ("¬", r"\(\neg\)"),
            ("ℵ", r"\(\aleph\)"),
            ("ϵ", r"\(\epsilon\)"),
            ("ε", r"\(\epsilon\)"),
            ("ϕ", r"\(\phi\)"),
            ("φ", r"\(\phi\)"),
            ("α", r"\(\alpha\)"),
            ("β", r"\(\beta\)"),
            ("γ", r"\(\gamma\)"),
            ("δ", r"\(\delta\)"),
            ("η", r"\(\eta\)"),
            ("θ", r"\(\theta\)"),
            ("κ", r"\(\kappa\)"),
            ("λ", r"\(\lambda\)"),
            ("ξ", r"\(\xi\)"),
            ("σ", r"\(\sigma\)"),
            ("τ", r"\(\tau\)"),
            ("ω", r"\(\omega\)"),
            ("Π", r"\(\Pi\)"),
            ("Θ", r"\(\Theta\)"),
            ("′", r"\(^{\prime}\)"),
            ("−", r"\(-\)"),
            ("×", r"\(\times\)"),
            ("±", r"\(\pm\)"),
            ("∗", r"\(\ast\)"),
            ("⋆", r"\(\star\)"),
            ("⊕", r"\(\oplus\)"),
            ("∫", r"\(\int\)"),
            ("∑", r"\(\sum\)"),
            ("√", r"\(\sqrt{\;}\)"),
            ("∼", r"\(\sim\)"),
            ("✓", r"\(\checkmark\)"),
            ("◦", r"\(\circ\)"),
            ("¯", r"\(\overline{\phantom{x}}\)"),
            ("\u0338", ""),
        ]
        for old, new in replacements:
            text = text.replace(old, new)
        return text

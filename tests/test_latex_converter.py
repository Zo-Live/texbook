"""Tests for LaTeX document assembly."""

from texbook.convert.latex_converter import LatexConverter


def test_convert_fragments_strips_document_wrappers():
    converter = LatexConverter()
    latex = converter.convert_fragments(
        title="讲义",
        fragments=[
            r"\documentclass{article}\begin{document}\section{集合}\end{document}",
            r"\begin{definition}定义内容\end{definition}",
        ],
        notes=["removed header/footer"],
    )

    assert latex.count(r"\documentclass") == 1
    assert r"\section{集合}" in latex
    assert r"\begin{definition}定义内容\end{definition}" in latex
    assert "% LLM note: removed header/footer" in latex
    assert r"\date{}" in latex


def test_convert_fragments_hides_date_by_default():
    converter = LatexConverter()

    latex = converter.convert_fragments(title="讲义", fragments=[])

    assert r"\date{}" in latex
    assert r"\date{\today}" not in latex


def test_convert_fragments_can_show_today_date():
    converter = LatexConverter()

    latex = converter.convert_fragments(
        title="讲义",
        fragments=[],
        show_date=True,
    )

    assert r"\date{\today}" in latex


def test_escape_latex_escapes_special_characters_once():
    converter = LatexConverter()

    assert (
        converter._escape_latex(r"\{}$&#^_%~")
        == r"\textbackslash{}\{\}\$\&\#\^{}\_\%\textasciitilde{}"
    )


def test_escape_latex_replaces_unicode_math_symbols():
    converter = LatexConverter()

    assert converter._escape_latex("A∈B") == r"A\(\in\)B"
    assert converter._escape_latex("A∉B") == r"A\(\notin\)B"
    assert converter._escape_latex("x≠y") == r"x\(\ne\)y"
    assert converter._escape_latex("αβ≤γ") == (
        r"\(\alpha\)\(\beta\)\(\le\)\(\gamma\)"
    )


def test_strip_invalid_chars_removes_control_chars_but_keeps_whitespace():
    converter = LatexConverter()

    assert converter._strip_invalid_chars("a\x00b\tc\nd\re\x1ff") == "ab\tc\nd\ref"


def test_clean_body_fragment_strips_document_wrappers_with_options():
    converter = LatexConverter()
    cleaned = converter._clean_body_fragment(
        r"""
        \documentclass[UTF8]{ctexart}
        \usepackage{amsmath}
        \usepackage[margin=1in]{geometry}
        \begin{document}
        \section{集合}
        \end{document}
        """
    )

    assert r"\documentclass" not in cleaned
    assert r"\usepackage" not in cleaned
    assert r"\begin{document}" not in cleaned
    assert r"\end{document}" not in cleaned
    assert cleaned == r"\section{集合}"

"""Tests for LaTeX document assembly."""

from pathlib import PurePosixPath

from texbook.convert.latex_converter import LatexConverter
from texbook.convert.project import LatexProjectBuilder, LatexProjectResult


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


def test_project_builder_builds_main_preamble_and_chapters():
    builder = LatexProjectBuilder()

    project = builder.build(
        title="讲义",
        fragments=[
            r"\documentclass{article}\begin{document}\section{集合}\end{document}",
            r"\usepackage{amsmath}\begin{definition}定义内容\end{definition}",
        ],
        notes=["removed header/footer"],
    )

    assert project.entrypoint == PurePosixPath("main.tex")
    assert set(project.files) == {
        PurePosixPath("main.tex"),
        PurePosixPath("preamble.tex"),
        PurePosixPath("chapters/chapter01.tex"),
        PurePosixPath("chapters/chapter02.tex"),
    }
    assert project.notes == ["removed header/footer"]
    assert project.metadata == {}

    main = project.files[PurePosixPath("main.tex")]
    assert "% !TEX program = xelatex" in main
    assert r"\documentclass[UTF8]{ctexart}" in main
    assert r"\input{preamble}" in main
    assert r"\title{讲义}" in main
    assert r"\date{}" in main
    assert r"\begin{document}" in main
    assert "% LLM note: removed header/footer" in main
    assert r"\input{chapters/chapter01}" in main
    assert r"\input{chapters/chapter02}" in main
    assert main.rstrip().endswith(r"\end{document}")

    preamble = project.files[PurePosixPath("preamble.tex")]
    assert r"\usepackage{amsmath}" in preamble
    assert r"\newtheorem{definition}{定义}" in preamble
    assert r"\documentclass" not in preamble
    assert r"\begin{document}" not in preamble

    chapter = project.files[PurePosixPath("chapters/chapter01.tex")]
    assert chapter == "\\section{集合}\n"
    assert r"\documentclass" not in chapter
    assert r"\begin{document}" not in chapter
    assert r"\end{document}" not in chapter


def test_project_builder_skips_empty_chapters_and_can_show_today_date():
    builder = LatexProjectBuilder()

    project = builder.build(
        title="讲义",
        fragments=[
            r"\documentclass{article}\begin{document}\end{document}",
            r"\section{非空}",
        ],
        show_date=True,
    )

    assert set(project.files) == {
        PurePosixPath("main.tex"),
        PurePosixPath("preamble.tex"),
        PurePosixPath("chapters/chapter01.tex"),
    }
    assert r"\date{\today}" in project.files[PurePosixPath("main.tex")]
    assert project.files[PurePosixPath("chapters/chapter01.tex")] == "\\section{非空}\n"


def test_project_result_rejects_missing_entrypoint():
    try:
        LatexProjectResult(
            files={PurePosixPath("preamble.tex"): ""},
            entrypoint=PurePosixPath("main.tex"),
        )
    except ValueError as exc:
        assert "entrypoint" in str(exc)
    else:
        raise AssertionError("LatexProjectResult should reject missing entrypoint")


def test_project_result_rejects_unsafe_file_paths():
    try:
        LatexProjectResult(
            files={
                PurePosixPath("main.tex"): "",
                PurePosixPath("../outside.tex"): "",
            },
            entrypoint=PurePosixPath("main.tex"),
        )
    except ValueError as exc:
        assert "relative POSIX" in str(exc)
    else:
        raise AssertionError("LatexProjectResult should reject unsafe paths")

"""Tests for structure planning helpers."""

import pytest

from texbook.llm.client import LLMResponseError, parse_structure_plan_response
from texbook.structure import (
    BookmarkEntry,
    PageHeadingCandidate,
    StructureEvidence,
    StructurePlanSource,
    build_local_heading_plan,
    build_plan_from_bookmarks,
    normalize_llm_structure_plan,
)


def test_build_plan_from_valid_bookmarks():
    evidence = StructureEvidence(
        source_title="book",
        total_pages=10,
        selected_pages=list(range(1, 11)),
        bookmarks=[
            BookmarkEntry(level=1, title="第一章 集合", page_number=1),
            BookmarkEntry(level=1, title="第二章 映射", page_number=5),
        ],
    )

    plan = build_plan_from_bookmarks(evidence)

    assert plan is not None
    assert plan.source == StructurePlanSource.bookmark
    assert [(item.title, item.start_page, item.end_page) for item in plan.items] == [
        ("第一章 集合", 1, 4),
        ("第二章 映射", 5, 10),
    ]


def test_build_plan_rejects_page_number_only_bookmarks():
    evidence = StructureEvidence(
        source_title="book",
        total_pages=10,
        selected_pages=list(range(1, 11)),
        bookmarks=[
            BookmarkEntry(level=1, title="1", page_number=1),
            BookmarkEntry(level=1, title="2", page_number=5),
        ],
    )

    assert build_plan_from_bookmarks(evidence) is None


def test_local_heading_plan_is_low_confidence():
    evidence = StructureEvidence(
        source_title="book",
        total_pages=8,
        selected_pages=list(range(1, 9)),
        heading_candidates=[
            PageHeadingCandidate(page_number=1, text="第一章 集合", font_size=18),
            PageHeadingCandidate(page_number=4, text="第二章 映射", font_size=18),
        ],
    )

    plan = build_local_heading_plan(evidence)

    assert plan is not None
    assert plan.source == StructurePlanSource.local_headings
    assert plan.confidence == 0.45
    assert plan.items[0].end_page == 3


def test_parse_structure_plan_response_accepts_complete_json():
    result = parse_structure_plan_response(
        """
        {"status":"complete","confidence":0.7,"reason":"目录完整",
        "needed_pages":[],"notes":["ok"],
        "plan":[{"kind":"chapter","title":"第一章","start_page":1,"end_page":3}]}
        """
    )

    assert result.status == "complete"
    assert result.confidence == 0.7
    assert result.plan[0]["title"] == "第一章"
    assert result.notes == ["ok"]


def test_parse_structure_plan_response_rejects_bad_status():
    with pytest.raises(LLMResponseError):
        parse_structure_plan_response('{"status":"done","plan":[]}')


def test_normalize_llm_structure_plan_clips_to_selected_pages():
    plan = normalize_llm_structure_plan(
        items=[
            {
                "kind": "chapter",
                "title": "第一章",
                "start_page": 1,
                "end_page": 10,
            }
        ],
        source=StructurePlanSource.llm_toc,
        confidence=0.8,
        selected_pages=[3, 4, 5],
        inspected_pages=[1, 2],
    )

    assert plan.items[0].start_page == 3
    assert plan.items[0].end_page == 5
    assert plan.inspected_pages == [1, 2]

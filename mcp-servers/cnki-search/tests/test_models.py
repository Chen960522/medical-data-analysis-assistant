"""Tests for the LiteratureRecord data model and its normalization helpers."""

from __future__ import annotations

from cnki_search.models import DATA_SOURCE_CNKI, LiteratureRecord


def test_to_dict_contains_all_required_metadata_fields() -> None:
    record = LiteratureRecord(
        title="某医学研究",
        abstract="摘要内容",
        authors=["张三", "李四"],
        journal="中华医学杂志",
        publication_date="2023-05-01",
        keywords=["糖尿病", "随机对照"],
        doi="10.1234/abcd",
    )
    payload = record.to_dict()
    for key in (
        "title",
        "abstract",
        "authors",
        "journal",
        "publication_date",
        "keywords",
        "doi",
        "data_source",
    ):
        assert key in payload
    assert payload["data_source"] == DATA_SOURCE_CNKI


def test_from_dict_normalizes_aliases_and_delimited_strings() -> None:
    record = LiteratureRecord.from_dict(
        {
            "name": "标题别名",
            "summary": "摘要别名",
            "author": "王五；赵六",  # Chinese semicolon delimiter.
            "source": "影像学杂志",
            "year": 2021,
            "keyword": "CT, MRI、超声",
            "DOI": "10.5678/xyz",
        }
    )
    assert record.title == "标题别名"
    assert record.abstract == "摘要别名"
    assert record.authors == ["王五", "赵六"]
    assert record.journal == "影像学杂志"
    assert record.publication_date == "2021"
    assert record.keywords == ["CT", "MRI", "超声"]
    assert record.doi == "10.5678/xyz"
    assert record.data_source == DATA_SOURCE_CNKI


def test_from_dict_handles_missing_fields_gracefully() -> None:
    record = LiteratureRecord.from_dict({})
    assert record.title == ""
    assert record.authors == []
    assert record.keywords == []
    assert record.data_source == DATA_SOURCE_CNKI


def test_authors_list_input_is_preserved() -> None:
    record = LiteratureRecord.from_dict({"title": "t", "authors": ["A", "B", "  "]})
    assert record.authors == ["A", "B"]

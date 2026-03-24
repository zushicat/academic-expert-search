from typing import Any

from models.expert_search_response_model import (
    ExpertSearchResponse_Author,
    ExpertSearchResponse_Institution,
    ExpertSearchResponse_Topic,
    ExpertSearchResponse_Work,
)


def _normalize_topic_id(topic_id: str) -> str:
    if topic_id.startswith("https://"):
        return topic_id

    return f"https://openalex.org/{topic_id}"


def _serialize_collection(
    items_by_id: dict[str, dict[str, Any]], model_class: type
) -> list[dict[str, Any]]:
    return [
        model_class.model_validate(item).model_dump() for item in items_by_id.values()
    ]


def _serialize_authors(
    authors_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    short_authors = []

    for author in authors_by_id.values():
        short_author = dict(author)
        short_author["relevant_topics"] = [
            _normalize_topic_id(topic_id)
            for topic_id, is_relevant in (author.get("relevant_topics") or {}).items()
            if is_relevant
        ]
        # short_author["works"] = author.get("works_search")
        short_author["works_search_count"] = author.get("works_count")

        short_authors.append(
            ExpertSearchResponse_Author.model_validate(short_author).model_dump()
        )

    return short_authors


def create_short_search_response(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "topics": _serialize_collection(
            response.get("topics") or {}, ExpertSearchResponse_Topic
        ),
        "works": _serialize_collection(
            response.get("works") or {}, ExpertSearchResponse_Work
        ),
        "institutions": _serialize_collection(
            response.get("institutions") or {}, ExpertSearchResponse_Institution
        ),
        "authors": _serialize_authors(response.get("authors") or {}),
        "meta": response.get("meta"),
    }

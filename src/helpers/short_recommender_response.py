from typing import Any

from models.expert_recommender_response_model import (
    ExpertRecommenderResponse_Author,
    ExpertRecommenderResponse_Institution,
    ExpertRecommenderResponse_Topic,
    ExpertRecommenderResponse_Work,
)


def _serialize_collection(items_by_id: dict[str, dict[str, Any]], model_class: type) -> list[dict[str, Any]]:
    return [model_class.model_validate(item).model_dump() for item in items_by_id.values()]


def _serialize_authors(
    authors_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    short_authors = []

    for author in authors_by_id.values():
        short_author = dict(author)
        short_author["relevant_topics"] = [
            topic_id
            for topic_id, is_relevant in (author.get("relevant_topics") or {}).items()
            if is_relevant
        ]

        short_authors.append(
            ExpertRecommenderResponse_Author.model_validate(short_author).model_dump()
        )

    return short_authors


def create_short_recommender_response(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "topics": _serialize_collection(
            response.get("topics") or {}, ExpertRecommenderResponse_Topic
        ),
        "works": _serialize_collection(
            response.get("works") or {}, ExpertRecommenderResponse_Work
        ),
        "institutions": _serialize_collection(
            response.get("institutions") or {}, ExpertRecommenderResponse_Institution
        ),
        "authors": _serialize_authors(response.get("authors") or {}),
        "meta": response.get("meta"),
    }

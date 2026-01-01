import asyncio
from itertools import combinations
import json
from time import sleep
from typing import Dict, Any, List, Set

from helpers.filehandler import read_json_file


class ExpertSearch:
    def __init__(self):
        pass

    # ************
    # The actual processing call (i.e. from router)
    # ************
    async def search_experts(self, query: str):
        # ***
        # Step 1
        # ***
        search_results: List[Dict[str, Any]] = self._search_works(query=query)
        reference_author_openalex_ids: Set[str] = self._get_reference_author_ids(
            search_results=search_results
        )

        # ***
        # Step 2
        # ***
        reference_author_results: List[Dict[str, Any]] = (
            self._request_reference_authors(
                reference_author_openalex_ids=reference_author_openalex_ids
            )
        )

        collected_topics_reference_authors: List[List[str]] = (
            self._get_reference_author_topics(
                reference_author_results=reference_author_results
            )
        )

        best_match_topics: Dict[str, int] = self._get_most_shared_topics(
            collected_topics_reference_authors=collected_topics_reference_authors
        )

        # ***
        # Step 3
        # ***
        author_count = len(collected_topics_reference_authors)

        topics_filter = self._get_most_shared_topics_combinations(
            best_match_topics=best_match_topics,
            author_count=author_count,
            core_threshold=0.95,
        )

        authors_by_topics = self._get_authors_by_topics(topics_filter=topics_filter)
        print(json.dumps(authors_by_topics[0], indent=2))

        return [{"foo": "bar"}]

    # ***********
    # STEP 1: use Openalex search on works and get Openalex ids of reference authors
    # ***********
    def _search_works(self, query: str) -> List[Dict[str, Any]]:
        # ***
        # Simulate Openalex request: use mock data
        # ***
        sleep(0.1)
        json_data = read_json_file(
            "ExpertSearch/mock-responses/1_openalex_search_response_works.json"
        )

        results: List[Dict[str, Any]] = (json_data.get("results") or [])[
            :20
        ]  # use only top 20

        return results

    def _get_reference_author_ids(self, search_results: List[Dict[str, Any]]) -> Set:
        # ***
        # collect distinct author ids
        # ***
        author_ids: Set[str] = set()
        for work in search_results:
            authorships: List[Dict[str, Any]] = work.get("authorships") or []
            for author in authorships:
                if author.get("author_position") is None or author.get(
                    "author_position"
                ) not in ["first", "last"]:
                    continue

                author_data = author.get("author") or {}
                author_id = author_data.get("id")
                if author_id:
                    author_id = author_id.split("/")[
                        -1
                    ]  # https://openalex.org/A5111809245 -> A5111809245
                    author_ids.add(author_id)

        return author_ids

    # ***********
    # STEP 2: request reference authors (endpoint author) and get author topics
    # ***********
    def _request_reference_authors(
        self, reference_author_openalex_ids: Set
    ) -> List[Dict[str, Any]]:
        author_id_filter = "|".join(reference_author_openalex_ids)
        request_url = f"https://api.openalex.org/authors?filter=id:{author_id_filter}&select=topics"

        # ***
        # Simulate Openalex request: use mock data
        # ***
        sleep(0.1)
        json_data = read_json_file(
            "ExpertSearch/mock-responses/2_reference_authors.json"
        )

        results: List[Dict[str, Any]] = json_data.get("results") or []

        return results

    def _get_reference_author_topics(
        self, reference_author_results: List[Dict[str, Any]]
    ) -> List[List[str]]:
        topic_ids: List[List[str]] = []
        for result in reference_author_results or []:
            author_topics: List[str] = []
            for topic in result.get("topics") or []:
                topic_id = topic.get("id").split("/")[-1]
                author_topics.append(topic_id)

            topic_ids.append(author_topics)

        return topic_ids

    def _get_most_shared_topics(
        self, collected_topics_reference_authors: List[List[str]]
    ) -> Dict[str, int]:
        topics_counted: Dict[str, int] = {}

        for author in collected_topics_reference_authors:
            for topic_id in author:
                if not topics_counted.get(topic_id):
                    topics_counted[topic_id] = 0
                topics_counted[topic_id] += 1

        topics_counted = {
            topic_id: count for topic_id, count in topics_counted.items() if count > 1
        }  # count must be > 1

        topics_counted = dict(
            sorted(topics_counted.items(), key=lambda item: item[1], reverse=True)
        )  # sort desc by count

        topics_count_sum = sum(topics_counted.values())

        topics_counted = {
            topic_id: count
            for topic_id, count in topics_counted.items()
            if count / topics_count_sum >= 0.1
        }  # filter top topics

        return topics_counted

    # ***********
    # STEP 3: Create and request Topics combination as filter on authors
    # ***********
    def _get_most_shared_topics_combinations(
        self,
        best_match_topics: Dict[str, int],
        author_count: int,
        core_threshold: float = 0.9,
    ) -> str:
        """
        Create progressively restrictive OpenAlex topic filter expectations.

        - Core topics (count / author_count >= core_threshold) are always ANDed
        - Optional topics are added cumulatively and ORed
        - Core-only filter is always included
        """

        # def build_filter(core, optional):
        #     """helper to build OpenAlex filter string"""
        #     base = "topics.id:" + "+".join(core)
        #     if not optional:
        #         return base
        #     return base + "+(" + "|".join(optional) + ")"

        # ***************
        # preparation
        # ***************
        #  normalize topic strengths
        # ***
        topic_strengths = {
            topic_id: count / author_count
            for topic_id, count in best_match_topics.items()
        }

        # ***
        # classify topics: core topics / optional tiopcs
        #  ***
        core_topics = [
            topic_id
            for topic_id, strength in topic_strengths.items()
            if strength >= core_threshold
        ]

        optional_topics = [
            topic_id
            for topic_id, strength in topic_strengths.items()
            if strength < core_threshold
        ]

        # ***
        # sort by descending strength
        # ***
        core_topics.sort(key=lambda t: topic_strengths[t], reverse=True)
        optional_topics.sort(key=lambda t: topic_strengths[t], reverse=True)

        # ***************
        # actually build filter
        # ***************
        topics_filter = f'{"+".join(core_topics)}+({"|".join(optional_topics)})'

        return topics_filter

        # expectations = []

        # # ***
        # # core-only baseline
        # # ***
        # expectations.append(
        #     {
        #         "filter": build_filter(core_topics, []),
        #         "core_topics": core_topics.copy(),
        #         "optional_topics": [],
        #         "restrictiveness_level": "low",
        #         "expected_behavior": "Baseline: all authors sharing core topics",
        #     }
        # )

        # # ***
        # # progressive OR expansions
        # # ***
        # levels = ["medium", "high", "very_high"]
        # for i in range(len(optional_topics)):
        #     current_optional = optional_topics[: i + 1]
        #     level = levels[min(i, len(levels) - 1)]

        #     expectations.append(
        #         {
        #             "filter": build_filter(core_topics, current_optional),
        #             "core_topics": core_topics.copy(),
        #             "optional_topics": current_optional.copy(),
        #             "restrictiveness_level": level,
        #             "expected_behavior": "Progressively narrowed by optional topic OR expansion",
        #         }
        #     )

        # return expectations

    def _get_authors_by_topics(self, topics_filter: str) -> List[Dict[str, Any]]:
        request_url = f"https://api.openalex.org/authors?filter=topics.id:{topics_filter}&select=id,display_name,summary_stats,topics&sort=summary_stats.h_index:desc&per_page=100"

        # ***
        # Simulate Openalex request: use mock data
        # ***
        sleep(0.1)
        json_data = read_json_file(
            "ExpertSearch/mock-responses/3_authors_by_topics.json"
        )

        results: List[Dict[str, Any]] = json_data.get("results") or []

        return results


if __name__ == "__main__":
    searcher = ExpertSearch()
    result = asyncio.run(searcher.search_experts(query="foo"))

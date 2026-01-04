import asyncio
import collections
from itertools import combinations
import json
from time import sleep
from typing import Dict, Any, List, Set, Tuple

from helpers.filehandler import read_json_file, write_json_file

import requests


class ExpertSearch:
    def __init__(self):
        self.class_name = self.__class__.__name__

    # ************
    # The actual processing call (i.e. from router)
    # ************
    async def search_experts(self, query: str):
        # ***
        # Step 1
        # ***
        search_results: List[Dict[str, Any]] = self._search_works(query=query)
        reference_author_openalex_ids, works = self._get_reference_author_ids(
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

        collected_topics_reference_authors, topics = self._get_reference_author_topics(
            reference_author_results=reference_author_results
        )

        best_match_topics: Dict[str, int] = self._get_most_shared_topics(
            collected_topics_reference_authors=collected_topics_reference_authors
        )

        # keep best_match_topics in topics, only
        topics = {
            topic_id: topic_val
            for topic_id, topic_val in topics.items()
            if topic_id.split("/")[-1] in list(best_match_topics.keys())
        }

        # ***
        # Step 3
        # ***
        author_count = len(collected_topics_reference_authors)

        topics_filter = self._get_most_shared_topics_combinations(
            best_match_topics=best_match_topics,
            author_count=author_count,
            core_threshold=0.85,
        )

        authors_by_topics = self._get_authors_by_topics(topics_filter=topics_filter)

        # ***
        # Step 4
        # ***
        aggregated_authors_source_search, institutions = self._aggregate_authors(
            author_list=reference_author_results,
            best_match_topics=best_match_topics,
            from_relevant_author_list=True,
        )

        aggregated_authors_source_topics, institutions = self._aggregate_authors(
            author_list=authors_by_topics,
            best_match_topics=best_match_topics,
            from_relevant_author_list=False,
            institutions=institutions,
        )

        aggregated_authors = aggregated_authors_source_search
        for key, val in aggregated_authors_source_topics.items():
            if aggregated_authors.get(key):
                continue
            aggregated_authors[key] = val

        aggregated_authors = self._assign_search_works_authors(
            aggregated_authors=aggregated_authors, works=works
        )

        # ***
        # Step 5: Putting it all together and return
        # ***
        search_result: Dict[str, Any] = {
            "topics": topics,
            "works": works,
            "institutions": institutions,
            "authors": aggregated_authors,
            "meta": {
                "query": query,
                "reference_author_count": author_count,
                "author_count": len(aggregated_authors),
                "works_count": len(works),
                "institutions_count": len(institutions),
                "best_match_topics": best_match_topics,
                "topics_filter": topics_filter,
            },
        }

        # debug
        # write_json_file(
        #     file_path="ExpertRecommender/mock-responses/0_search_result.json",
        #     data=search_result,
        # )

        return search_result

    # ***********
    # STEP 1: use Openalex search on works and get Openalex ids of reference authors
    # ***********
    def _search_works(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        request_url = f"https://api.openalex.org/works?filter=title_and_abstract.search:{query},type:article&per_page={limit}&select=id,ids,title,publication_year,relevance_score,authorships,cited_by_count,primary_topic,topics"
        # print(request_url)
        # ***
        # Simulate Openalex request: use mock data
        # Use top 20 or so in order to only get relevant results
        # ***
        sleep(1)
        json_data = read_json_file(
            "ExpertSearch/mock-responses/1_openalex_search_response_works.json"
        )

        results: List[Dict[str, Any]] = json_data.get("results") or []

        return results

    def _get_reference_author_ids(
        self, search_results: List[Dict[str, Any]]
    ) -> Tuple[Set, Dict[str, Any], Dict[str, Any]]:
        # ***
        # collect distinct author ids
        # ***
        author_ids: Set[str] = set()
        works: Dict[str, Any] = {}

        for work in search_results:
            # ***
            # process work
            # ***
            work_id = work.get("id")

            tmp_work = {
                "openalex_id": work_id,
                "doi": work.get("ids").get("doi"),
                "title": work.get("title"),
                "publication_year": work.get("publication_year"),
                "relevance_score": work.get("relevance_score"),
                "cited_by_count": work.get("cited_by_count"),
                "primary_topic": (
                    work.get("primary_topic").get("id")
                    if work.get("primary_topic")
                    else None
                ),
                "topics": [topic.get("id") for topic in work.get("topics")],
                "author_ids": [],
            }

            # ***
            # process authors
            # ***
            authorships: List[Dict[str, Any]] = work.get("authorships") or []
            for author in authorships:
                author_data = author.get("author") or {}
                author_id = author_data.get("id")

                # store all author ids in works
                tmp_work["author_ids"].append(author_id)

                # for authors: collect only authors with first / last position
                if author.get("author_position") is None or author.get(
                    "author_position"
                ) not in ["first", "last"]:
                    continue

                if author_id:
                    author_id = author_id.split("/")[
                        -1
                    ]  # https://openalex.org/A5111809245 -> A5111809245
                    author_ids.add(author_id)

            works[work_id] = tmp_work

        return author_ids, works

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
        sleep(1)
        json_data = read_json_file(
            "ExpertSearch/mock-responses/2_reference_authors.json"
        )

        results: List[Dict[str, Any]] = json_data.get("results") or []

        return results

    def _get_reference_author_topics(
        self, reference_author_results: Tuple[List[Dict[str, Any]], Dict[str, Any]]
    ) -> List[List[str]]:
        topic_ids: List[List[str]] = []
        topics: Dict[str, Any] = {}

        for result in reference_author_results or []:
            author_topics: List[str] = []
            for topic in result.get("topics") or []:
                topic_id = topic.get("id")
                # ***
                # set topics dict
                # ***
                if topics.get(topic_id) is None:
                    topics[topic_id] = topic

                # ***
                # topic in author
                # ***
                topic_id = topic_id.split("/")[-1]
                author_topics.append(topic_id)

            topic_ids.append(author_topics)

        return topic_ids, topics

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

    def _get_authors_by_topics(self, topics_filter: str) -> List[Dict[str, Any]]:
        request_url = f"https://api.openalex.org/authors?filter=topics.id:{topics_filter}&select=id,display_name,summary_stats,topics&sort=summary_stats.h_index:desc&per_page=100"

        # ***
        # Simulate Openalex request: use mock data
        # ***
        sleep(1)
        json_data = read_json_file(
            "ExpertSearch/mock-responses/3_authors_by_topics.json"
        )

        results: List[Dict[str, Any]] = json_data.get("results") or []

        return results

    # ***********
    # STEP 4: Aggregate responses
    # ***********
    def _aggregate_authors(
        self,
        author_list: List[Dict[str, Any]],
        best_match_topics: Dict[str, int],
        from_relevant_author_list: bool = False,
        institutions: Dict[str, Any] = {},
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        relevant_topics = list(best_match_topics.keys())
        aggregate_authors: Dict[str, Any] = {}

        for author in author_list:
            author_openalex_id = author.get("id")

            tmp_author = {
                "openalex_id": author_openalex_id,
                "orcid_id": author.get("ids").get("orcid"),
                "display_name": author.get("display_name"),
                "from_relevant_author_list": from_relevant_author_list,
                "2yr_mean_citedness": author.get("summary_stats").get(
                    "2yr_mean_citedness"
                ),
                "h_index": author.get("summary_stats").get("h_index"),
                "i10_index": author.get("summary_stats").get("i10_index"),
                "relevant_topics": {topic: False for topic in relevant_topics},
                "relevant_topics_share": 0,
                "active_years_min": None,
                "active_years_max": None,
                "active_years_sum": None,
                "active_years_counted": None,
                "institutions": None,
                "instituitions_count": 0,
                "works_search": None,
            }

            # ***
            # process topics
            # ***
            for topic in author.get("topics"):
                topic_id = topic.get("id").split("/")[-1]
                if topic_id in relevant_topics:
                    tmp_author["relevant_topics"][topic_id] = True

            tmp_author["relevant_topics_share"] = sum(
                tmp_author["relevant_topics"].values()
            )

            # ***
            # process affiliations: collect year activity
            # ***
            active_years = {}
            for affiliation in author.get("affiliations"):
                # set counted active years
                years = affiliation.get("years")

                for year in years:
                    if active_years.get(year) is None:
                        active_years[year] = 0
                    active_years[year] += 1

                # ***
                # process institution
                # ***
                institution = affiliation.get("institution")
                openalex_id = institution.get("id")

                # set institutions for author
                year_min = min(years)
                year_max = max(years)

                if tmp_author["institutions"] is None:
                    tmp_author["institutions"] = []

                tmp_author["institutions"].append(
                    {
                        "openalex_id": openalex_id,
                        "year_start": year_min,
                        "year_end": year_max,
                    }
                )

                # set institution object
                if institutions.get(openalex_id) is None:
                    institution["openalex_id"] = institution.get("id")
                    for attr in ("id", "lineage"):
                        del institution[attr]
                    institutions[openalex_id] = institution

            # ***
            # sort institutions by year_start
            # ***
            if tmp_author["institutions"]:
                tmp_author["institutions"] = sorted(
                    tmp_author["institutions"], key=lambda item: item["year_start"]
                )

                tmp_author["instituitions_count"] = len(tmp_author["institutions"])

            # ***
            # year activity in activities / institutions
            # Multiple counts per year can be a signal for
            # a) mismatches regarding the disambiguation
            # b) high coorporation activity with different institutions that year (nor necessarily employment per se)
            # ***
            active_years = collections.OrderedDict(
                sorted(active_years.items(), reverse=False)
            )

            tmp_author["active_years_counted"] = active_years
            tmp_author["active_years_sum"] = len(list(set(active_years.keys())))

            # ***
            # get min and max active years
            # ***
            tmp_author["active_years_min"] = min(map(int, active_years.keys()))
            tmp_author["active_years_max"] = max(map(int, active_years.keys()))

            if aggregate_authors.get(author_openalex_id) is None:
                aggregate_authors[author_openalex_id] = tmp_author

        return aggregate_authors, institutions

    def _assign_search_works_authors(
        self, aggregated_authors: Dict[str, Any], works: Dict[str, Any]
    ):
        for work_id, work_val in works.items():
            for author_id in work_val.get("author_ids"):
                if aggregated_authors.get(author_id):
                    if aggregated_authors[author_id].get("works_search") is None:
                        aggregated_authors[author_id]["works_search"] = []
                    aggregated_authors[author_id]["works_search"].append(work_id)

        return aggregated_authors

    def _shared_topics_batches(
        self, aggregated_authors: Dict[str, Any], min_share: int = 1
    ):
        author_batches: Dict[int, Dict[str, Any]] = {}

        for author_id, author_val in aggregated_authors.items():
            relevant_topics_share = author_val.get("relevant_topics_share")
            if relevant_topics_share < min_share:
                continue

            if author_batches.get(relevant_topics_share) is None:
                author_batches[relevant_topics_share] = {}
            author_batches[relevant_topics_share][author_id] = author_val

        return author_batches


if __name__ == "__main__":
    searcher = ExpertSearch()

    query = "wild bee population decline bee monitoring"
    result = asyncio.run(searcher.search_experts(query=query))

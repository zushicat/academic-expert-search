import asyncio
import collections
import json
from statistics import median, mean, stdev, quantiles
from time import sleep
from typing import Dict, Any, List, Set, Tuple

from classes.ExpertQuery import ExpertQuery
from helpers.filehandler import read_json_file, write_json_file

from src.models.expert_search_models import (
    ExpertSearch_Response,
    ExpertSearch_Works,
    ExpertSearch_Work,
    ExpertSearch_Topics,
    ExpertSearch_Institutions,
    ExpertSearch_Author,
    ExpertSearch_Authors,
    ExpertSearch_Meta,
)

import requests


class ExpertSearch:
    def __init__(self):
        self.class_name = self.__class__.__name__
        self.expert_query = ExpertQuery()

    # ************
    # The actual processing call (i.e. from router)
    # ************
    async def search_experts(
        self,
        query: str,
        use_fulltext_search: bool = False,
        create_queries: bool = False,
    ) -> ExpertSearch_Response:
        # ***
        # Step 1
        # ***
        print("ExpertSearch 1 ---> _search_works")

        search_results, generated_queries = await self._search_works(
            query=query,
            limit=20,
            year_cutoff=2020,
            use_fulltext_search=use_fulltext_search,
            create_queries=create_queries,
        )

        print("ExpertSearch 2 ---> _get_reference_author_ids")
        reference_author_openalex_ids, works = self._get_reference_author_ids(
            search_results
        )

        # DEBUG
        # write_json_file(
        #     f"{self.class_name}/mock-responses/1_openalex_search_response_works.json",
        #     data=search_results,
        # )

        # ***
        # Step 2
        # ***
        print("ExpertSearch 3 ---> _request_reference_authors")

        reference_author_results = await self._request_reference_authors(
            reference_author_openalex_ids
        )

        # DEBUG
        # write_json_file(
        #     f"{self.class_name}/mock-responses/2_reference_authors.json",
        #     data=reference_author_results,
        # )

        print("ExpertSearch 4 ---> _get_reference_author_topics")
        collected_topics_reference_authors, topics = self._get_reference_author_topics(
            reference_author_results
        )

        print("ExpertSearch 5 ---> _get_most_shared_topics")
        best_match_topics = self._get_most_shared_topics(
            collected_topics_reference_authors
        )

        # keep best_match_topics in topics, only
        topics = {
            topic_id: topic_val
            for topic_id, topic_val in topics.items()
            if topic_id.split("/")[-1] in best_match_topics
        }

        # ***
        # Step 3
        # ***
        author_count = len(collected_topics_reference_authors)

        print(
            "ExpertSearch 6 ---> _get_most_shared_topics_combinations | _get_authors_by_topics"
        )
        topics_filter = self._get_most_shared_topics_combinations(
            best_match_topics=best_match_topics,
            author_count=author_count,
            core_threshold=0.85,
        )

        authors_by_topics = self._get_authors_by_topics(
            topics_filter=topics_filter, limit=100
        )

        # DEBUG
        # write_json_file(
        #     f"{self.class_name}/mock-responses/3_authors_by_topics.json",
        #     data=authors_by_topics,
        # )

        # ***
        # Step 4
        # ***
        print("ExpertSearch 7 ---> _aggregate_authors")
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

        # merge
        print(
            "ExpertSearch 8 ---> aggregated_authors_source_search | _assign_search_works_authors"
        )
        aggregated_authors = aggregated_authors_source_search
        for key, val in aggregated_authors_source_topics.items():
            if key not in aggregated_authors:
                aggregated_authors[key] = val

        # only keep authors that have more than 1 shared topics
        aggregated_authors = {
            k: v
            for k, v in aggregated_authors.items()
            if v.get("relevant_topics_share") > 0
        }

        aggregated_authors = self._assign_search_works_authors(
            aggregated_authors, works
        )

        # ***
        # Step 5: Putting it all together and return
        # ***
        # dicts to models
        authors_models: Dict[str, ExpertSearch_Author] = {}
        for author_id, author in aggregated_authors.items():
            data = dict(author)
            data["two_yr_mean_citedness"] = data.pop("2yr_mean_citedness", None)
            authors_models[author_id] = ExpertSearch_Author(**data)

        authors_models, topic_share_batches = self._sort_batch_authors_by_topics_count(
            authors_dict=authors_models
        )

        works_models: Dict[str, ExpertSearch_Author] = {}
        for work_id, work in works.items():
            try:
                works_models[work_id] = ExpertSearch_Work(**work)
            except:
                pass

        search_response = ExpertSearch_Response(
            topics=ExpertSearch_Topics(topics),
            works=ExpertSearch_Works(works_models),
            institutions=ExpertSearch_Institutions(institutions),
            authors=ExpertSearch_Authors(authors_models),
            meta=ExpertSearch_Meta(
                query=query,
                generated_queries=generated_queries,
                reference_author_count=author_count,
                author_count=len(authors_models),
                works_count=len(works),
                institutions_count=len(institutions),
                best_match_topics=best_match_topics,
                topics_filter=topics_filter,
                authors_topic_share_counts=topic_share_batches,
            ),
        )

        return search_response

    # ***********
    # STEP 1: use Openalex search on works and get Openalex ids of reference authors
    # ***********
    async def _search_works(
        self,
        query: str,
        limit: int = 20,
        year_cutoff: int = 2020,
        use_fulltext_search: bool = False,
        create_queries: bool = False,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        # ***
        # debug
        # Simulate Openalex request: use mock data
        # Use top 20 or so in order to only get relevant results
        # ***
        # sleep(1)
        # json_data = read_json_file(
        #     "ExpertSearch/mock-responses/1_openalex_search_response_works.json"
        # )

        queries: List[str] = []
        query_results: List[str] = []

        num_new_queries = 3

        if create_queries:
            query_results = await self.expert_query.create_queries(
                query=query, num_new_queries=num_new_queries
            )
            if query_results:
                queries = query_results
        else:
            queries.append(query)

        # ***
        # collect and depublicat by ids.openalex
        # ***
        all_results = []

        for query in queries:
            if use_fulltext_search:
                request_url = f"https://api.openalex.org/works?search={query}&filter=type:article,publication_year:>{year_cutoff-1}&per_page={limit}&select=ids,title,publication_year,relevance_score,authorships,primary_topic"
            else:
                request_url = f"https://api.openalex.org/works?filter=title_and_abstract.search:{query},type:article,publication_year:>{year_cutoff-1}&per_page={limit}&select=ids,title,publication_year,relevance_score,authorships,primary_topic"

            response = requests.get(request_url)
            json_data = response.json()
            all_results.extend(json_data.get("results"))

        # deduplicate
        distinct_by_openalex = {}
        for work in all_results:
            openalex_id = (work.get("ids") or {}).get("openalex")
            if openalex_id:
                distinct_by_openalex[openalex_id] = work

        return list(distinct_by_openalex.values()), query_results

    def _get_reference_author_ids(
        self, search_results: List[Dict[str, Any]]
    ) -> Tuple[Set[str], Dict[str, Any]]:
        author_ids: Set[str] = set()
        works: Dict[str, Any] = {}

        # ***
        # collect distinct author ids
        # ***
        for work in search_results:
            # ***
            # process work
            # ***
            work_id = work.get("ids").get("openalex")
            tmp_work = {
                "openalex_id": work_id,
                "doi": (work.get("ids") or {}).get("doi"),
                "title": work.get("title"),
                "publication_year": work.get("publication_year"),
                "relevance_score": work.get("relevance_score"),
                "primary_topic": (work.get("primary_topic") or {}).get("id"),
                "author_ids": [],
                "from_query_search": True,
            }

            # ***
            # process authors
            # ***
            for author in work.get("authorships") or []:
                author_data = author.get("author") or {}
                author_id = author_data.get("id")

                # if author.get("author_position") not in {"first", "last"}:
                #     continue

                tmp_work["author_ids"].append(author_id)

                if author_id:
                    author_ids.add(author_id.split("/")[-1])

            works[work_id] = tmp_work

        return author_ids, works

    # ***********
    # STEP 2: request reference authors (endpoint author) and get author topics
    # ***********
    # get author data
    # ***
    def _chunk_ids(self, ids: List[str], size: int = 25) -> List[List[str]]:
        return [ids[i : i + size] for i in range(0, len(ids), size)]

    async def _fetch_author_batch(self, session_ids: List[str]) -> List[Dict[str, Any]]:
        author_id_filter = "|".join(session_ids)
        request_url = (
            "https://api.openalex.org/authors"
            f"?filter=id:{author_id_filter}"
            "&select=id,display_name,ids,affiliations,summary_stats,topics"
        )
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: requests.get(request_url))
        try:
            return response.json().get("results") or []
        except Exception:
            return []

    async def _request_reference_authors(
        self, reference_author_openalex_ids: Set[str]
    ) -> List[Dict[str, Any]]:
        id_list = list(reference_author_openalex_ids)
        batches = self._chunk_ids(id_list, size=25)

        tasks = [self._fetch_author_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks)

        merged: List[Dict[str, Any]] = []

        for batch in results:
            merged.extend(batch)

        return merged

    # ***
    # analyze topics from authors
    # ***
    def _get_reference_author_topics(
        self, reference_author_results: List[Dict[str, Any]]
    ) -> Tuple[List[List[str]], Dict[str, Any]]:
        topic_ids: List[List[str]] = []
        topics: Dict[str, Any] = {}

        for result in reference_author_results:
            author_topics: List[str] = []
            for topic in result.get("topics") or []:
                topic_id = topic.get("id")
                if topic_id and topic_id not in topics:
                    topics[topic_id] = topic
                if topic_id:
                    author_topics.append(topic_id.split("/")[-1])
            topic_ids.append(author_topics)

        return topic_ids, topics

    def _get_most_shared_topics(
        self, collected_topics_reference_authors: List[List[str]]
    ) -> Dict[str, int]:
        # Count topics
        topics_counted: Dict[str, int] = {}
        for author_topics in collected_topics_reference_authors:
            for topic_id in author_topics:
                topics_counted[topic_id] = topics_counted.get(topic_id, 0) + 1

        # Filter: must appear more than once
        topics_counted = {k: v for k, v in topics_counted.items() if v > 1}

        if len(topics_counted) < 2:
            return topics_counted

        # Sort descending by count
        topics_counted = dict(
            sorted(topics_counted.items(), key=lambda i: i[1], reverse=True)
        )

        counts = list(topics_counted.values())

        # Calculate statistics
        q1, q2, q3 = quantiles(counts, n=4)  # quartiles
        iqr = q3 - q1
        avg = mean(counts)
        std = stdev(counts)

        # ===== Choose your filtering method =====

        # Method 1: Percentile-based (above 75th percentile)
        # threshold = q3

        # Method 2: IQR-based "mild outliers" (above Q3 + 0.5*IQR)
        threshold = q3 + 0.5 * iqr

        # Method 3: IQR-based "strong outliers" (above Q3 + 1.5*IQR)
        # threshold = q3 + 1.5 * iqr

        # Method 4: Z-score based (more than 1 std above mean)
        # threshold = avg + std

        # Method 5: Z-score based (more than 2 std above mean)
        # threshold = avg + 2 * std

        # Debug output
        # print(f"   Statistics: mean={avg:.2f}, std={std:.2f}, median={q2}")
        # print(f"   Quartiles: Q1={q1}, Q2={q2}, Q3={q3}, IQR={iqr}")
        # print(f"   Threshold: {threshold:.2f}")

        # Filter topics
        filtered_topics = {k: v for k, v in topics_counted.items() if v >= threshold}

        # print(f"   Kept {len(filtered_topics)} of {len(topics_counted)} topics")

        return filtered_topics

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
        strengths = {k: v / author_count for k, v in best_match_topics.items()}

        # ***
        # classify topics: core topics / optional tiopcs
        # ***
        core_topics = [k for k, s in strengths.items() if s >= core_threshold]
        optional_topics = [k for k, s in strengths.items() if s < core_threshold]

        # ***
        # sort by descending strength
        # ***
        core_topics.sort(key=lambda t: strengths[t], reverse=True)
        optional_topics.sort(key=lambda t: strengths[t], reverse=True)

        # ***************
        # actually build filter
        # - core topic MUST be present / optional topics CAN be present
        # - per documentation, higher shares on OR are at the top or results (?)
        # - Openalex logic filter seems kind of weird
        #
        # Maybe this is over-engineered and a simple OR concat is sufficient.
        # ***************
        if not core_topics:
            topics_filter = f'{"|".join(optional_topics)}'
        else:
            topics_filter = f'{"+".join(core_topics)}+({"|".join(optional_topics)})'

        return topics_filter

    def _get_authors_by_topics(
        self, topics_filter: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        # ***
        # Simulate Openalex request: use mock data
        # ***
        # sleep(1)
        # json_data = read_json_file(
        #     "ExpertSearch/mock-responses/3_authors_by_topics.json"
        # )

        request_url = f"https://api.openalex.org/authors?filter=topics.id:{topics_filter}&select=id,display_name,ids,affiliations,summary_stats,topics&sort=summary_stats.h_index:desc&per_page={limit}"

        response = requests.get(request_url)
        json_data = response.json()

        return json_data.get("results") or []

    # ***********
    # STEP 4: Aggregate responses
    # ***********
    def _aggregate_authors(
        self,
        author_list: List[Dict[str, Any]],
        best_match_topics: Dict[str, int],
        from_relevant_author_list: bool = False,
        institutions: Dict[str, Any] | None = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if institutions is None:
            institutions = {}

        relevant_topics = list(best_match_topics.keys())
        aggregate_authors: Dict[str, Any] = {}

        for author in author_list:
            author_openalex_id = author.get("id")
            tmp_author = {
                "openalex_id": author_openalex_id,
                "orcid_id": (author.get("ids") or {}).get("orcid"),
                "display_name": author.get("display_name"),
                "from_relevant_author_list": from_relevant_author_list,
                "2yr_mean_citedness": (author.get("summary_stats") or {}).get(
                    "2yr_mean_citedness"
                ),
                "h_index": (author.get("summary_stats") or {}).get("h_index"),
                "i10_index": (author.get("summary_stats") or {}).get("i10_index"),
                "relevant_topics": {t: False for t in relevant_topics},
                "relevant_topics_share": 0,
                "active_years_min": None,
                "active_years_max": None,
                "active_years_sum": None,
                "active_years_counted": None,
                "institutions": None,
                "instituitions_count": 0,
                "works_search": None,
                "works_author": None,
                "works_count": 0,
            }

            # ***
            # process topics
            # ***
            for topic in author.get("topics") or []:
                tid = topic.get("id", "").split("/")[-1]
                if tid in tmp_author["relevant_topics"]:
                    tmp_author["relevant_topics"][tid] = True

            tmp_author["relevant_topics_share"] = sum(
                tmp_author["relevant_topics"].values()
            )

            # ***
            # process affiliations: collect year activity
            # ***
            active_years: Dict[int, int] = {}
            for affiliation in author.get("affiliations") or []:
                years = affiliation.get("years") or []
                if not years:
                    continue

                for year in years:
                    active_years[year] = active_years.get(year, 0) + 1

                # ***
                # process institution
                # ***
                inst = affiliation.get("institution") or {}
                inst_id = inst.get("id")

                if inst_id:
                    # set institutions for author
                    if tmp_author["institutions"] is None:
                        tmp_author["institutions"] = []
                    tmp_author["institutions"].append(
                        {
                            "openalex_id": inst_id,
                            "year_start": min(years),
                            "year_end": max(years),
                        }
                    )
                    # set institution object
                    if inst_id not in institutions:
                        institutions[inst_id] = {
                            "openalex_id": inst_id,
                            "ror": inst.get("ror"),
                            "display_name": inst.get("display_name"),
                            "country_code": inst.get("country_code"),
                            "type": inst.get("type"),
                        }

            # ***
            # for authors: sort institutions by year_start
            # ***
            if tmp_author["institutions"]:
                tmp_author["institutions"].sort(key=lambda i: i["year_start"])
                tmp_author["instituitions_count"] = len(tmp_author["institutions"])

            # ***
            # year activity in activities / institutions
            # Multiple counts per year can be a signal for
            # a) mismatches regarding the disambiguation
            # b) high coorporation activity with different institutions that year (nor necessarily employment per se)
            # ***
            if active_years:
                active_years = collections.OrderedDict(sorted(active_years.items()))
                tmp_author["active_years_counted"] = active_years
                tmp_author["active_years_sum"] = len(active_years)
                tmp_author["active_years_min"] = min(active_years)
                tmp_author["active_years_max"] = max(active_years)

            aggregate_authors[author_openalex_id] = tmp_author

        return aggregate_authors, institutions

    def _assign_search_works_authors(self, aggregated_authors, works):
        for work_id, work_val in works.items():
            for author_id in work_val.get("author_ids") or []:
                if author_id in aggregated_authors:
                    if aggregated_authors[author_id].get("works_search") is None:
                        aggregated_authors[author_id]["works_search"] = []
                    aggregated_authors[author_id]["works_search"].append(work_id)

                    # increment works count
                    aggregated_authors[author_id]["works_count"] += 1
        return aggregated_authors

    # ***********
    # STEP 5: Sorting and batches (by matching topics count)
    # ***********
    def _sort_batch_authors_by_topics_count(
        self, authors_dict: Dict[str, ExpertSearch_Author]
    ) -> Tuple[Dict[str, ExpertSearch_Author], Dict[int, int]]:
        # sort authors by relevant_topics_share (desc)
        # sorted_items = sorted(
        #     authors_dict.items(),
        #     key=lambda item: item[1].relevant_topics_share,
        #     reverse=True,
        # )
        sorted_authors = collections.OrderedDict(
            sorted(
                authors_dict.items(),
                key=lambda item: item[1].relevant_topics_share,
                reverse=True,
            )
        )

        # build batches: {relevant_topics_share: count}
        topic_share_batches: Dict[int, int] = {}
        for author in sorted_authors.values():
            share = int(author.relevant_topics_share)
            topic_share_batches[share] = topic_share_batches.get(share, 0) + 1

        # re-wrap into ExpertSearch_Authors
        # sorted_authors = dict(sorted_items)

        return sorted_authors, topic_share_batches


if __name__ == "__main__":
    searcher = ExpertSearch()

    # query = "spruce forest drought"
    # query = "wild bee population decline bee monitoring"
    query = "Forest and woodland stand structural complexity"
    # query = "Deep learning"
    # query = "Transformers without Normalization"

    result = asyncio.run(searcher.search_experts(query=query))

    # write_json_file(
    #     "ExpertRecommender/mock-responses/0_search_result.json",
    #     data=result.model_dump(),
    # )

    # print(json.dumps(result.model_dump()["works"], ensure_ascii=False))
    # print("-" * 100)
    print(json.dumps(result.model_dump()["meta"], ensure_ascii=False, indent=2))

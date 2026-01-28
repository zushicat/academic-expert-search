import asyncio
import collections
from datetime import datetime
import json
import math
from time import sleep
from typing import Dict, Any, List, Set, Tuple

from classes.RecommenderClasses.ExpertGraph import ExpertGraph
from classes.RecommenderClasses.ExpertUpdate import ExpertUpdate
from classes.RecommenderClasses.ExpertAnalysis import ExpertAnalysis
from classes.ExpertQuery import ExpertQuery

from helpers.filehandler import read_json_file, write_json_file
from helpers.toon import encode_toon

from models.expert_search_models import (
    ExpertSearch_Response,
    ExpertSearch_Works,
    ExpertSearch_Work,
    ExpertSearch_Topics,
    ExpertSearch_Institutions,
    ExpertSearch_Institution,
    ExpertSearch_AuthorInstitution,
    ExpertSearch_Author,
    ExpertSearch_Authors,
    ExpertSearch_Meta,
)

from models.expert_recommender_models import (
    ExpertRecommender_ExpertConnection,
    ExpertRecommender_AuthorScores,
    ExpertRecommender_Author,
    ExpertRecommender_Authors,
    ExpertRecommender_Response,
    ExpertRecommender_Meta,
)

import aiohttp
import networkx as nx
import requests


class ExpertRecommender:
    def __init__(self, top_perc_found_authors: float = 0.8):
        self.class_name = self.__class__.__name__
        self.top_perc_found_authors = top_perc_found_authors

    # ************
    # The actual processing call (i.e. from router)
    # ************
    async def recommend_experts(
        self,
        search_result: ExpertSearch_Response,
        create_expert_summaries: bool = False,
    ):
        meta = search_result.meta  # .model_dump()
        topics = search_result.topics  # .model_dump()
        works = search_result.works  # .model_dump()
        institutions = search_result.institutions  # .model_dump()
        authors = search_result.authors  # .model_dump()

        # ***
        # STEP 1: filter author (and the rest) on authors_topic_share_counts
        # - use threshold on topic share (authors)
        # ***
        print("ExpertRecommender 1 ---> _get_top_topic_share")
        top_counts = self._get_top_topic_share(
            meta=meta, top_perc=self.top_perc_found_authors
        )

        print("ExpertRecommender 2 ---> _filter_search_result")
        authors, works, institutions = self._filter_search_result(
            works=works,
            institutions=institutions,
            authors=authors,
            top_counts=top_counts,
        )

        # ***
        # Step 2: get and process works for all authors
        # ***
        current_year = datetime.now().year
        years_back = 3

        print("ExpertRecommender 3 ---> _get_works")
        works_from_authors = await self._get_works(
            author_ids=authors.root,
            topics_filter=meta.topics_filter,
            min_year=current_year - years_back,
        )

        # ***
        # DEBUG
        # ***
        # write_json_file(
        #     file_path=f"{self.class_name}/mock-responses/1_works_from_authors_0_8.json",
        #     data=works_from_authors,
        # )

        # works_from_authors = read_json_file(
        #     file_path=f"{self.class_name}/mock-responses/1_works_from_authors_0_8.json"
        # )
        #
        # ***
        print("ExpertRecommender 4 ---> _processworks_from_authors")
        works, authors = self._processworks_from_authors(
            works_from_authors=works_from_authors, works=works, authors=authors
        )

        # ***
        # Step 3: Analyze graph (authors)
        # -> class ExpertGraph
        #    - graph: ExpertGraph instance
        #    - graph.graph: nx.MultiGraph
        # ***
        print(
            "ExpertRecommender 5 ---> ExpertGraph | get_best_experts | get_connected_authors"
        )
        graph = ExpertGraph(search_result=search_result)
        authors_by_score = graph.get_best_experts()
        author_connections = graph.get_connected_authors()

        # ***
        # Step 4: Filter and update by relevance
        # -> class ExpertUpdate
        # ***
        print(
            "ExpertRecommender 6 ---> update_author_scores | update_author_connections"
        )
        update = ExpertUpdate()
        authors_by_score = update.update_author_scores(
            authors_by_score=authors_by_score, author_connections=author_connections
        )

        # filter authors_by_score by score cutoff and keep only relevant authors
        score_cutoff = 0.5
        authors_by_score = {
            k: v for k, v in authors_by_score.items() if v.overall_score >= score_cutoff
        }

        aggregated_author_connections = update.update_author_connections(
            author_connections=author_connections,
            relevant_author_ids=list(authors_by_score.keys()),
        )

        # update search results objects:
        # filter out irrelevant stuff not connected to authors_by_score
        # overwrite / typecast author from ExpertSearch_Authors to Dict[str, ExpertRecommender_Author]
        print("ExpertRecommender 7 ---> update search results")
        works, institutions, authors = update.update_search_result_objects(
            authors=authors,
            works=works,
            institutions=institutions,
            graph=graph.graph,
            relevant_author_ids=list(authors_by_score.keys()),
        )

        # add scores and connections to authors
        # store min/max author scores
        author_min_score: float = 0.0
        author_max_score: float = 0.0
        for k, v in authors.root.items():
            v.scores = authors_by_score.get(k)
            v.expert_connections = aggregated_author_connections.get(k)

            if author_min_score == 0.0:
                author_min_score = v.scores.overall_score
            if author_max_score == 0.0:
                author_max_score = v.scores.overall_score

            if v.scores.overall_score < author_min_score:
                author_min_score = v.scores.overall_score
            if v.scores.overall_score > author_max_score:
                author_max_score = v.scores.overall_score

        # sort authors by author.scores.obverall_score
        sorted_authors = collections.OrderedDict(
            sorted(
                authors.root.items(),
                key=lambda item: item[1].scores.overall_score,
                reverse=True,
            )
        )
        authors = ExpertRecommender_Authors(**sorted_authors)

        # ***
        # Step 5: Process / analyze author works (LLM)
        # -> class ExpertAnalysis
        #    - get summary from author's works titles
        # ***
        if create_expert_summaries:
            print("ExpertRecommender 8 ---> create_expert_summaries")
            analyzer = ExpertAnalysis()
            authors_works_summary = await analyzer.analyze_author(
                authors=authors, works=works
            )  # use default batch_size and max_concurrency from env

            for author_id, summary in authors_works_summary.items():
                try:
                    authors.root[author_id].summary = summary
                except KeyError:
                    try:
                        authors.root[f"https://openalex.org/{author_id}"].summary = (
                            summary
                        )
                    except KeyError:
                        pass

        # ***
        # Step 6: Putting it all together and return
        # ***
        # recommender_response = ExpertRecommender_Response(
        #     topics=topics,
        #     works=works,
        #     institutions=institutions,
        #     authors=authors,
        #     meta=ExpertRecommender_Meta(
        #         author_count=len(authors.root),
        #         works_count=len(works.root),
        #         institutions_count=len(institutions.root),
        #         search=meta,
        #     ),
        # )

        # return recommender_response.model_dump()

        # Serialize to dicts first to avoid nested model validation issues
        response_data = {
            "topics": topics.model_dump(),
            "works": works.model_dump(),
            # "institutions": institutions.model_dump(),
            "authors": authors.model_dump(),
            "meta": {
                "author_count": len(authors.root),
                "works_count": len(works.root),
                "institutions_count": len(institutions.root),
                "author_min_score": round(author_min_score, 3),
                "author_max_score": round(author_max_score, 3),
                "search": meta.model_dump() if meta else None,
            },
        }

        return response_data

    # ***********
    # STEP 1: filter author (and the rest) on authors_topic_share_counts
    # - use threshold on topic share (authors)
    # ***********
    def _get_top_topic_share(self, meta: ExpertSearch_Works, top_perc: float = 0.7):
        authors_topic_share_counts = meta.authors_topic_share_counts
        max_count = round(max(authors_topic_share_counts.keys()) * top_perc)

        return max_count

    def _filter_search_result(
        self,
        works: ExpertSearch_Works,
        institutions: ExpertSearch_Institutions,
        authors: ExpertSearch_Authors,
        top_counts: int,
    ):
        # ***
        # filter authors on relevant_topics_share ---
        # ***
        valid_author_ids = set()
        invalid_author_ids = set()

        for author_id, author in list(authors.root.items()):
            if (
                author.relevant_topics_share >= top_counts
                and author.relevant_topics_share > 0
            ):
                valid_author_ids.add(author_id)
            else:
                invalid_author_ids.add(author_id)
                authors.root.pop(author_id, None)

        # ***
        # filter works
        # ***
        invalid_work_ids = set()

        for work_id, work in list(works.root.items()):
            if not work.author_ids:
                invalid_work_ids.add(work_id)
                works.root.pop(work_id, None)
                continue

            if not any(author_id in valid_author_ids for author_id in work.author_ids):
                invalid_work_ids.add(work_id)
                works.root.pop(work_id, None)

        # ***
        # filter institutions
        # ***
        institution_ref_count = {}

        for author in authors.root.values():
            if not author.institutions:
                continue
            for inst in author.institutions:
                institution_ref_count[inst.openalex_id] = (
                    institution_ref_count.get(inst.openalex_id, 0) + 1
                )

        invalid_institution_ids = set()
        for inst_id in list(institutions.root.keys()):
            if institution_ref_count.get(inst_id, 0) == 0:
                invalid_institution_ids.add(inst_id)
                institutions.root.pop(inst_id, None)

        # ***
        # cleanup dangling references
        # ***
        for author in authors.root.values():
            if author.works_search:
                author.works_search = [
                    wid for wid in author.works_search if wid in works.root
                ]

            if author.institutions:
                author.institutions = [
                    inst
                    for inst in author.institutions
                    if inst.openalex_id in institutions.root
                ]

        return authors, works, institutions

    # ***********
    # Step 2: get and process works for all authors
    # ***********
    async def _get_works(
        self, topics_filter: str, author_ids: List[str], min_year: int
    ):
        AUTHOR_BATCH_SIZE = 25
        PER_PAGE = 200
        MAX_RPS = 10

        author_ids = [author_id.split("/")[-1] for author_id in author_ids]
        author_filter = "|".join(author_ids[:50])

        base_params = (
            f"filter=type:article,"
            f"publication_year:>{min_year-1},"
            f"topics.id:{topics_filter},"
            f"author.id:{author_filter},"
            f"has_doi:true&select=ids,title,publication_year,authorships,primary_topic"
        )

        semaphore = asyncio.Semaphore(MAX_RPS)

        async def fetch_page(session: aiohttp.ClientSession, url: str):
            async with semaphore:
                async with session.get(url) as resp:
                    if resp.status == 429:
                        await asyncio.sleep(1)
                        return await fetch_page(session, url)
                    resp.raise_for_status()
                    return await resp.json()

        async with aiohttp.ClientSession() as session:
            first_url = (
                f"https://api.openalex.org/works?{base_params}&per_page=1&page=1"
            ).strip()
            first = await fetch_page(session, first_url)

            total_count = first["meta"]["count"]
            total_pages = math.ceil(total_count / PER_PAGE)

            urls = [
                f"https://api.openalex.org/works?{base_params}&per_page={PER_PAGE}&page={page}"
                for page in range(1, total_pages + 1)
            ]

            tasks = [fetch_page(session, url) for url in urls]
            responses = await asyncio.gather(*tasks)

        works = []
        for r in responses:
            works.extend(r.get("results", []))

        return works

    def _processworks_from_authors(
        self,
        works_from_authors: List[Dict[str, Any]],
        works: ExpertSearch_Topics,
        authors: ExpertSearch_Authors,
    ):
        for current_work in works_from_authors:
            # ***
            # process work
            # ***
            current_work_id = current_work.get("ids").get("openalex")

            # already stored: skip
            if works.root.get(current_work_id):
                continue

            tmp_work = {
                "openalex_id": current_work_id,
                "doi": (current_work.get("ids") or {}).get("doi"),
                "title": current_work.get("title"),
                "publication_year": current_work.get("publication_year"),
                "relevance_score": current_work.get("relevance_score"),
                "primary_topic": (current_work.get("primary_topic") or {}).get("id"),
                "author_ids": [],
                "from_query_search": False,
            }

            # ***
            # process authors
            # ***
            for author_in_work in current_work.get("authorships") or []:
                author_in_work_id = author_in_work.get("author").get("id")

                # author id is not in authors object: skip
                if authors.root.get(author_in_work_id) is None:
                    continue

                # store author id in current work object
                tmp_work["author_ids"].append(author_in_work_id)

                # store current work id in author object
                author = authors.root[author_in_work_id]
                if author.works_search is None:
                    author.works_search = []

                if author.works_author is None:
                    author.works_author = []
                author.works_author.append(current_work_id)
                author.works_count += 1

            # add current_work_id:tmp_work to works
            works.root[current_work_id] = ExpertSearch_Work(**tmp_work)

        # return updated objects
        return works, authors


if __name__ == "__main__":
    top_perc_found_authors = 0.8
    recommender = ExpertRecommender(top_perc_found_authors=top_perc_found_authors)

    search_response = read_json_file(
        "ExpertRecommender/mock-responses/0_search_result.json"
    )
    result = asyncio.run(
        recommender.recommend_experts(
            search_result=ExpertSearch_Response.model_validate(search_response),
            create_expert_summaries=False,
        )
    )

    # print(
    #     json.dumps(list(result.model_dump()["authors"].values())[0], ensure_ascii=False)
    # )

    print(json.dumps(list(result["authors"].values())[0], ensure_ascii=False))

import asyncio
import collections
from time import sleep
from typing import Dict, Any, List, Set, Tuple

from helpers.filehandler import read_json_file, write_json_file

from src.models.expert_search_models import (
    ExpertSearch_Response,
    ExpertSearch_Works,
    ExpertSearch_Topics,
    ExpertSearch_Institutions,
    ExpertSearch_Author,
    ExpertSearch_Authors,
    ExpertSearch_Meta,
)

import requests


class ExpertRecommender:
    def __init__(self, top_perc_found_authors: float = 0.8):
        self.class_name = self.__class__.__name__
        self.top_perc_found_authors = top_perc_found_authors

    # ************
    # The actual processing call (i.e. from router)
    # ************
    async def recommend_experts(self, search_result: ExpertSearch_Response):
        meta = topics = search_result.meta  # .model_dump()
        topics = search_result.topics  # .model_dump()
        works = search_result.works  # .model_dump()
        institutions = search_result.institutions  # .model_dump()
        authors = search_result.authors  # .model_dump()

        # ***
        # Step 1
        # ***
        top_counts = self._get_top_topic_share(
            meta=meta, top_perc=self.top_perc_found_authors
        )
        print(top_counts)

        authors, works, institutions = self._filter_search_result(
            works=works,
            institutions=institutions,
            authors=authors,
            top_counts=top_counts,
        )

        print(
            len(authors.model_dump()),
            len(works.model_dump()),
            len(institutions.model_dump()),
        )

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


if __name__ == "__main__":
    top_perc_found_authors = 0.8
    recommender = ExpertRecommender(top_perc_found_authors=top_perc_found_authors)

    search_response = read_json_file(
        "ExpertRecommender/mock-responses/0_search_result.json"
    )
    result = asyncio.run(
        recommender.recommend_experts(
            search_result=ExpertSearch_Response.model_validate(search_response)
        )
    )

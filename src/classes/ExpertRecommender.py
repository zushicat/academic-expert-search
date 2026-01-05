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

        self._filter_search_result(
            works=works,
            institutions=institutions,
            authors=authors,
            top_counts=top_counts,
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
        invalid_author_ids = []
        invalid_institution_ids = []
        invalid_works_ids = []

        # first
        # for each author: check if relevant_topics_share is >= or < top_counts
        # only keep relevant_topics_share >= top_counts
        # if relevant_topics_share < top_counts: relevant_topics_share >= top_counts in invalid_author_ids

        # then check the references to works and instritutions:
        # if a work and an institution gas ONLY references to authors that are removed (invalid)
        # then remove this work or institution


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

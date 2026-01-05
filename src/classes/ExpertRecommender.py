import asyncio
import collections
from datetime import datetime
import json
import math
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

        authors, works, institutions = self._filter_search_result(
            works=works,
            institutions=institutions,
            authors=authors,
            top_counts=top_counts,
        )

        # ***
        # Step 2
        # ***
        current_year = datetime.now().year

        works = await self._get_works(
            author_ids=authors.root,
            topics_filter=meta.topics_filter,
            min_year=current_year - 5,
        )

        # ***
        # Step 2
        # ***
        # graph = self._build_graph(search_result=search_result)
        # best_authors = self._get_best_experts(graph=graph)
        # print(len(best_authors))
        # print()
        # print(json.dumps(best_authors))

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
        PER_PAGE = 200
        MAX_RPS = 10

        author_ids = [author_id.split("/")[-1] for author_id in author_ids]
        author_filter = "|".join(author_ids)

        base_params = (
            f"filter=type:article,"
            f"publication_year:>{min_year-1},"
            f"topics.id:{topics_filter},"
            f"author.id:{author_filter},"
            f"has_doi:true"
            "&select=id,ids,title,publication_year,relevance_score,"
            "authorships,cited_by_count,primary_topic,topics"
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
                f"https://api.openalex.org/works?{base_params}" "&per_page=1&page=1"
            )
            first = await fetch_page(session, first_url)

            total_count = first["meta"]["count"]
            total_pages = math.ceil(total_count / PER_PAGE)

            urls = [
                f"https://api.openalex.org/works?{base_params}"
                f"&per_page={PER_PAGE}&page={page}"
                for page in range(1, total_pages + 1)
            ]

            tasks = [fetch_page(session, url) for url in urls]
            responses = await asyncio.gather(*tasks)

        works = []
        for r in responses:
            works.extend(r.get("results", []))

        print(f"Fetched {len(works)} works (expected {total_count})")

        return works

    # ***********
    # Step 3: graph from search results
    # ***********
    def _build_graph(self, search_result: ExpertSearch_Response) -> nx.MultiGraph:
        G = nx.MultiGraph()

        for topic in search_result.topics.root.values():
            G.add_node(
                topic.id,
                node_type="topic",
                display_name=topic.display_name,
                score=topic.score,
                field=topic.field,
                subfield=topic.subfield,
                domain=topic.domain,
            )

        for work in search_result.works.root.values():
            G.add_node(
                work.openalex_id,
                node_type="work",
                title=work.title,
                publication_year=work.publication_year,
                relevance_score=work.relevance_score,
                cited_by_count=work.cited_by_count,
                from_query_search=work.from_query_search,
            )

            for topic_id in work.topics:
                if topic_id in G:
                    G.add_edge(
                        work.openalex_id,
                        topic_id,
                        edge_type="has_topic",
                        is_primary=(topic_id == work.primary_topic),
                    )

        for author in search_result.authors.root.values():
            G.add_node(
                author.openalex_id,
                node_type="author",
                display_name=author.display_name,
                h_index=author.h_index,
                i10_index=author.i10_index,
                two_yr_mean_citedness=author.two_yr_mean_citedness,
                relevant_topics_share=author.relevant_topics_share,
                active_years_min=author.active_years_min,
                active_years_max=author.active_years_max,
            )

            for topic_id, is_relevant in author.relevant_topics.items():
                if not is_relevant:
                    continue

                # relevant_topics uses short IDs (e.g. T10487), graph uses full OpenAlex URLs
                full_topic_id = topic_id
                if not topic_id.startswith("https://"):
                    full_topic_id = f"https://openalex.org/{topic_id}"

                if full_topic_id in G:
                    G.add_edge(
                        author.openalex_id,
                        full_topic_id,
                        edge_type="expertise",
                        weight=author.relevant_topics_share,
                    )

        for work in search_result.works.root.values():
            for author_id in work.author_ids:
                if author_id in G:
                    G.add_edge(
                        author_id,
                        work.openalex_id,
                        edge_type="authored",
                        from_query_search=work.from_query_search,
                    )

        for inst in search_result.institutions.root.values():
            G.add_node(
                inst.openalex_id,
                node_type="institution",
                display_name=inst.display_name,
                country_code=inst.country_code,
                type=inst.type,
            )

        for author in search_result.authors.root.values():
            if not author.institutions:
                continue

            for inst in author.institutions:
                if inst.openalex_id in G:
                    G.add_edge(
                        author.openalex_id,
                        inst.openalex_id,
                        edge_type="affiliated_with",
                        year_start=inst.year_start,
                        year_end=inst.year_end,
                    )

        return G

    def _get_best_experts(self, graph: nx.MultiGraph):
        current_year = datetime.now().year

        # collect author nodes
        authors = [
            n for n, d in graph.nodes(data=True) if d.get("node_type") == "author"
        ]

        if not authors:
            return []

        topic_raw = {}
        impact_raw = {}
        productivity_raw = {}
        recency_raw = {}

        # ---- compute raw scores ----
        for author in authors:
            data = graph.nodes[author]

            # Topic expertise: sum of expertise edge weights
            topic_score = 0.0
            for _, _, edata in graph.edges(author, data=True):
                if edata.get("edge_type") == "expertise":
                    topic_score += edata.get("weight", 0.0)
            topic_raw[author] = topic_score

            # Impact: dampened bibliometrics
            h = data.get("h_index") or 0
            i10 = data.get("i10_index") or 0
            citedness = data.get("two_yr_mean_citedness") or 0

            impact_raw[author] = (
                0.6 * math.log1p(h)
                + 0.3 * math.log1p(i10)
                + 0.1 * math.log1p(citedness)
            )

            # Productivity: number of authored works
            authored_works = [
                nbr
                for nbr, edata in graph[author].items()
                for e in edata.values()
                if e.get("edge_type") == "authored"
            ]
            productivity_raw[author] = len(set(authored_works))

            # Recency: based on most recent publication year
            years = []
            for work in set(authored_works):
                year = graph.nodes[work].get("publication_year")
                if isinstance(year, int):
                    years.append(year)

            if years:
                years_since = max(0, current_year - max(years))
                recency_raw[author] = 1.0 / (1.0 + years_since)
            else:
                recency_raw[author] = 0.0

        # ---- normalization helper ----
        def normalize(scores):
            max_val = max(scores.values())
            if max_val == 0:
                return {k: 0.0 for k in scores}
            return {k: v / max_val for k, v in scores.items()}

        topic = normalize(topic_raw)
        impact = normalize(impact_raw)
        productivity = normalize(productivity_raw)
        recency = normalize(recency_raw)

        # ---- final score ----
        results = []
        for author in authors:
            score = (
                0.40 * topic[author]
                + 0.30 * impact[author]
                + 0.20 * productivity[author]
                + 0.10 * recency[author]
            )

            results.append(
                (
                    author,
                    score,
                    {
                        "topic": topic[author],
                        "impact": impact[author],
                        "productivity": productivity[author],
                        "recency": recency[author],
                    },
                )
            )

        # sort descending by score
        results.sort(key=lambda x: x[1], reverse=True)

        return results


if __name__ == "__main__":
    top_perc_found_authors = 0.6  # 0.8
    recommender = ExpertRecommender(top_perc_found_authors=top_perc_found_authors)

    search_response = read_json_file(
        "ExpertRecommender/mock-responses/0_search_result.json"
    )
    result = asyncio.run(
        recommender.recommend_experts(
            search_result=ExpertSearch_Response.model_validate(search_response)
        )
    )

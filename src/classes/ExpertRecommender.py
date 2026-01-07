import asyncio
import collections
from datetime import datetime
import json
import math
from time import sleep
from typing import Dict, Any, List, Set, Tuple

from helpers.filehandler import read_json_file, write_json_file
from helpers.toon import encode_toon

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
        # current_year = datetime.now().year
        # years_back = 3

        # works_from_authors = await self._get_works(
        #     author_ids=authors.root,
        #     topics_filter=meta.topics_filter,
        #     min_year=current_year - years_back,
        # )

        # ***
        # DEBUG
        # ***
        # write_json_file(
        #     file_path=f"{self.class_name}/mock-responses/1_works_from_authors_0_8.json",
        #     data=works_from_authors,
        # )

        works_from_authors = read_json_file(
            file_path=f"{self.class_name}/mock-responses/1_works_from_authors_0_8.json"
        )

        works, authors = self._processworks_from_authors(
            works_from_authors=works_from_authors, works=works, authors=authors
        )

        # ***
        # Step 3: Analyze graph (authors)
        # ***
        graph = self._build_graph(search_result=search_result)
        authors_by_score = self._get_best_experts(graph=graph)
        author_connections = self._get_connected_authors(graph=graph)

        authors_by_score = self._update_author_scores(
            authors_by_score=authors_by_score, author_connections=author_connections
        )

        # filter authors_by_score by score cutoff and keep only relevant authors
        score_cutoff = 0.6
        authors_by_score = {
            k: v
            for k, v in authors_by_score.items()
            if v["overall_score"] >= score_cutoff
        }
        # print(len(authors_by_score))
        # print(json.dumps(authors_by_score))

        aggregated_author_connections = self._update_author_connections(
            author_connections=author_connections,
            relevant_author_ids=list(authors_by_score.keys()),
        )

        # print(json.dumps(aggregated_author_connections))
        print(
            json.dumps(
                authors.root["https://openalex.org/A5070924304"].model_dump(),
                ensure_ascii=False,
            )
        )

        # ***
        # Step 4
        # ***
        # batch = []
        # for author_id in list(authors_by_score.keys())[:2]:
        #     author = authors.root[author_id]
        #     author_works_ids = author.works_search + author.works_author

        #     collected_works_titles = {"openalex_id": author_id, "publications": {}}

        #     for author_works_id in author_works_ids:
        #         title = works.root[author_works_id].title
        #         publication_year = works.root[author_works_id].publication_year

        #         if collected_works_titles["publications"].get(publication_year) is None:
        #             collected_works_titles["publications"][publication_year] = []
        #         collected_works_titles["publications"][publication_year].append(title)

        #     batch.append(collected_works_titles)

        # print(len(batch))
        # print()
        # toon_data = encode_toon(batch)
        # print(toon_data)

        # print(authors.root["https://openalex.org/A5070924304"].model_dump())
        # author = authors.root["https://openalex.org/A5070924304"]

        # author_id = author.openalex_id
        # author_works_ids = author.works_search + author.works_author

        # collected_works_titles = {"openalex_id": author_id, "publications": {}}

        # for author_works_id in author_works_ids:
        #     title = works.root[author_works_id].title
        #     publication_year = works.root[author_works_id].publication_year

        #     if collected_works_titles["publications"].get(publication_year) is None:
        #         collected_works_titles["publications"][publication_year] = []
        #     collected_works_titles["publications"][publication_year].append(title)

        # toon_data = encode_toon(collected_works_titles)
        # print(toon_data)

        # from toon_format import estimate_savings, compare_formats

        # json_data = collected_works_titles

        # result = estimate_savings(json_data)
        # print(f"Saves {result['savings_percent']:.1f}% tokens")

        # # Get formatted comparison
        # print(compare_formats(json_data))

        # print(json.dumps(collected_works_titles, ensure_ascii=False))

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
            "&select=ids,title,publication_year,"
            "authorships,primary_topic"
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

    # ***********
    # Step 3: Analyze graph (authors)
    # - graph from search results
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
                from_query_search=work.from_query_search,
            )

            if work.primary_topic in G:  # topic id
                G.add_edge(
                    work.openalex_id,
                    work.primary_topic,
                    edge_type="has_topic",
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
                works_count=author.works_count,
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

        # ******
        # compute raw scores
        # ******
        for author in authors:
            data = graph.nodes[author]

            # ***
            # Topic expertise: sum of expertise edge weights
            # ***
            topic_score = 0.0
            for _, _, edata in graph.edges(author, data=True):
                if edata.get("edge_type") == "expertise":
                    topic_score += edata.get("weight", 0.0)
            topic_raw[author] = topic_score

            # ***
            # Impact: dampened bibliometrics
            # ***
            h = data.get("h_index") or 0
            i10 = data.get("i10_index") or 0
            citedness = data.get("two_yr_mean_citedness") or 0

            impact_raw[author] = (
                0.8 * math.log1p(h)
                + 0.3 * math.log1p(i10)
                + 0.1 * math.log1p(citedness)
            )

            # ***
            # Productivity: number of authored works
            # ***
            authored_works = [
                nbr
                for nbr, edata in graph[author].items()
                for e in edata.values()
                if e.get("edge_type") == "authored"
            ]
            productivity_raw[author] = len(set(authored_works))

            # ***
            # Recency: based on most recent publication year
            # ***
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

        # ******
        # normalization helper
        # ******
        def normalize(scores):
            max_val = max(scores.values())
            if max_val == 0:
                return {k: 0.0 for k in scores}
            return {k: v / max_val for k, v in scores.items()}

        topic = normalize(topic_raw)
        impact = normalize(impact_raw)
        productivity = normalize(productivity_raw)
        recency = normalize(recency_raw)

        # ******
        # result format helper
        # ******
        def format_results(raw_results: List[List[Any]]) -> Dict[str, Any]:
            results: Dict[str, Any] = {}
            for raw_result in raw_results:
                author_id = raw_result[0]
                tmp = {"openalex_id": author_id, "overall_score": raw_result[1]}
                for k, v in raw_result[2].items():
                    tmp[k] = v

                results[author_id] = tmp
            return results

        # ******
        # final score
        # ******
        raw_results = []
        for author in authors:
            score = (
                0.40 * topic[author]
                + 0.30 * impact[author]
                + 0.20 * productivity[author]
                + 0.10 * recency[author]
            )

            raw_results.append(
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
        raw_results.sort(key=lambda x: x[1], reverse=True)

        # format and return orderend dict
        results = format_results(raw_results=raw_results)

        return results

    def _get_connected_authors(self, graph: nx.MultiGraph):
        """
        Detect author groups using Option A-2:
        - Groups are cliques formed by authors on the same work or institution
        - Groups are deduplicated by identical author membership
        - No transitive closure, no topics
        """
        # --- collect author nodes
        authors = {
            n for n, d in graph.nodes(data=True) if d.get("node_type") == "author"
        }

        # =============================
        # Co-authorship cliques (works)
        # =============================
        coauthor_groups = {}

        for node, data in graph.nodes(data=True):
            if data.get("node_type") != "work":
                continue

            work_id = node
            work_authors = []

            for nbr, edata_dict in graph[work_id].items():
                for edata in edata_dict.values():
                    if edata.get("edge_type") == "authored" and nbr in authors:
                        work_authors.append(nbr)

            if len(work_authors) < 2:
                continue

            key = frozenset(work_authors)
            if key not in coauthor_groups:
                coauthor_groups[key] = {
                    "authors": list(key),
                    "works": [work_id],
                    "size": len(key),
                }
            else:
                coauthor_groups[key]["works"].append(work_id)

        # =============================
        # Institution cliques
        # =============================
        institution_groups = {}

        for node, data in graph.nodes(data=True):
            if data.get("node_type") != "institution":
                continue

            inst_id = node
            inst_authors = []

            for nbr, edata_dict in graph[inst_id].items():
                for edata in edata_dict.values():
                    if edata.get("edge_type") == "affiliated_with" and nbr in authors:
                        inst_authors.append(nbr)

            if len(inst_authors) < 2:
                continue

            key = frozenset(inst_authors)
            if key not in institution_groups:
                institution_groups[key] = {
                    "authors": list(key),
                    "institutions": [inst_id],
                    "size": len(key),
                }
            else:
                institution_groups[key]["institutions"].append(inst_id)

        # =============================
        # Assign group IDs
        # =============================
        coauthor_group_list = []
        for idx, group in enumerate(coauthor_groups.values()):
            group["group_id"] = idx
            coauthor_group_list.append(group)

        institution_group_list = []
        for idx, group in enumerate(institution_groups.values()):
            group["group_id"] = idx
            institution_group_list.append(group)

        # =============================
        # Author membership index
        # =============================
        author_membership = {
            a: {"coauthor_groups": [], "institution_groups": []} for a in authors
        }

        for group in coauthor_group_list:
            gid = group["group_id"]
            for author in group["authors"]:
                author_membership[author]["coauthor_groups"].append(gid)

        for group in institution_group_list:
            gid = group["group_id"]
            for author in group["authors"]:
                author_membership[author]["institution_groups"].append(gid)

        # =============================
        # Connectivity scores
        # =============================
        work_score_raw = {a: 0 for a in authors}
        institution_score_raw = {a: 0 for a in authors}

        for group in coauthor_group_list:
            increment = group.get("size", 0) - 1
            if increment <= 0:
                continue
            for author in group["authors"]:
                work_score_raw[author] += increment

        for group in institution_group_list:
            increment = group.get("size", 0) - 1
            if increment <= 0:
                continue
            for author in group["authors"]:
                institution_score_raw[author] += increment

        max_work = max(work_score_raw.values()) or 1
        max_inst = max(institution_score_raw.values()) or 1

        for author in authors:
            work_norm = work_score_raw[author] / max_work
            inst_norm = institution_score_raw[author] / max_inst

            author_membership[author].update(
                {
                    "connectivity_score_works": round(work_norm, 3),
                    "connectivity_score_institutions": round(inst_norm, 3),
                    "connectivity_score": round((0.5 * work_norm + 0.5 * inst_norm), 3),
                }
            )

        # --- sort authors by connectivity score (desc)
        author_membership_sorted = dict(
            sorted(
                author_membership.items(),
                key=lambda x: x[1].get("connectivity_score", 0),
                reverse=True,
            )
        )

        return {
            "by_coauthorship": coauthor_group_list,
            "by_institution": institution_group_list,
            "author_membership": author_membership_sorted,
        }

    def _update_author_scores(
        self, authors_by_score: Dict[str, Any], author_connections: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add author connectivity score to authors_by_score"""
        for author_id, author_data in author_connections.get(
            "author_membership"
        ).items():
            authors_by_score[author_id].update(
                {
                    "connectivity_score_works": author_data.get(
                        "connectivity_score_works"
                    ),
                    "connectivity_score_institutions": author_data.get(
                        "connectivity_score_institutions"
                    ),
                    "connectivity_score": author_data.get("connectivity_score"),
                }
            )

        return authors_by_score

    def _update_author_connections(
        self, author_connections: Dict[str, Any], relevant_author_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Aggregates connections like so:
            {
                "author_123": {
                    "author_456": {
                        connected_by_work: <bool>,
                        connected_by_affiliation: <bool>
                    }
                }
            }
        Aggregate author-to-author connections based on:
        - shared coauthorship groups
        - shared institution groups
        """
        aggregated: Dict[str, Dict[str, Dict[str, bool]]] = {}

        coauthor_groups = author_connections.get("by_coauthorship", [])
        institution_groups = author_connections.get("by_institution", [])
        author_membership = author_connections.get("author_membership", {})

        # ***
        # Pre-index groups by group_id for fast lookup
        # ***
        coauthor_by_id = {g["group_id"]: g for g in coauthor_groups}
        institution_by_id = {g["group_id"]: g for g in institution_groups}

        for author_id, membership in author_membership.items():
            aggregated.setdefault(author_id, {})
            # ***
            # Co-authorship connections
            # ***
            for group_id in membership.get("coauthor_groups", []):
                group = coauthor_by_id.get(group_id)

                if not group:
                    continue

                for other_author in group.get("authors", []):
                    if other_author == author_id:
                        continue
                    if other_author not in relevant_author_ids:
                        continue

                    aggregated[author_id].setdefault(
                        other_author,
                        {
                            "connected_by_work": False,
                            "connected_by_affiliation": False,
                        },
                    )
                    aggregated[author_id][other_author]["connected_by_work"] = True

            # ***
            # Institution connections
            # ***
            for group_id in membership.get("institution_groups", []):
                group = institution_by_id.get(group_id)

                if not group:
                    continue

                for other_author in group.get("authors", []):
                    if other_author == author_id:
                        continue
                    if other_author not in relevant_author_ids:
                        continue

                    aggregated[author_id].setdefault(
                        other_author,
                        {
                            "connected_by_work": False,
                            "connected_by_affiliation": False,
                        },
                    )
                    aggregated[author_id][other_author][
                        "connected_by_affiliation"
                    ] = True

        return aggregated


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

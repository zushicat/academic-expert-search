from typing import Dict, Any, List, Set, Tuple

from models.expert_search_models import (
    ExpertSearch_Works,
    ExpertSearch_Institutions,
    ExpertSearch_Authors,
)

from models.expert_recommender_models import (
    ExpertRecommender_ExpertConnection,
    ExpertRecommender_AuthorScores,
    ExpertRecommender_Author,
    ExpertRecommender_Authors,
)

import networkx as nx


class ExpertUpdate:
    def __init__(self):
        self.class_name = self.__class__.__name__

    def update_author_scores(
        self, authors_by_score: Dict[str, Any], author_connections: Dict[str, Any]
    ) -> Dict[str, ExpertRecommender_AuthorScores]:
        """Convert raw score dicts to ExpertRecommender_AuthorScores and add connectivity."""
        updated: Dict[str, ExpertRecommender_AuthorScores] = {}

        membership = author_connections.get("author_membership", {})

        for author_id, raw_scores in authors_by_score.items():
            # Instantiate score model from raw values
            scores = ExpertRecommender_AuthorScores(**raw_scores)

            author_data = membership.get(author_id)
            if author_data:
                scores.connectivity_score_works = author_data.get(
                    "connectivity_score_works", 0.0
                )
                scores.connectivity_score_institutions = author_data.get(
                    "connectivity_score_institutions", 0.0
                )
                scores.connectivity_score = author_data.get("connectivity_score", 0.0)

            updated[author_id] = scores

        return updated

    def update_author_connections(
        self, author_connections: Dict[str, Any], relevant_author_ids: List[str]
    ) -> Dict[str, List[ExpertRecommender_ExpertConnection]]:
        """
        Aggregate author-to-author connections as flattened lists:
            {
                "author_123": [
                    ExpertRecommender_ExpertConnection(
                        openalex_id="author_456",
                        connected_by_work=True,
                        connected_by_affiliation=False,
                    )
                ]
            }
        """
        aggregated: Dict[str, Dict[str, ExpertRecommender_ExpertConnection]] = {}

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
                        ExpertRecommender_ExpertConnection(openalex_id=other_author),
                    )
                    aggregated[author_id][other_author].connected_by_work = True

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
                        ExpertRecommender_ExpertConnection(openalex_id=other_author),
                    )
                    aggregated[author_id][other_author].connected_by_affiliation = True

        # ***
        # Convert inner dicts to lists
        # ***
        return {
            author_id: list(connections.values())
            for author_id, connections in aggregated.items()
        }

    def update_search_result_objects(
        self,
        works: ExpertSearch_Works,
        institutions: ExpertSearch_Institutions,
        authors: ExpertSearch_Authors,
        graph: nx.MultiDiGraph,
        relevant_author_ids: List[str],
    ) -> Tuple[
        ExpertSearch_Works,
        ExpertSearch_Institutions,
        ExpertRecommender_Authors,
    ]:
        """
        Remove works, institutions, and authors that have no connection with
        relevant author ids, using graph topology.

        Rules:
        - Works are kept if authored by a relevant author or from_query_search
        - Institutions are kept if affiliated with a relevant author
        - Authors are kept if:
          * relevant author
          * connected to kept works or institutions
          * or have topic expertise edges
        """
        relevant_author_ids = set(relevant_author_ids)

        # ***
        # 1. Filter works
        # ***
        kept_work_ids: Set[str] = set()

        for work_id, work in works.root.items():
            if work.from_query_search:
                kept_work_ids.add(work_id)
                continue

            if work_id not in graph:
                continue

            for nbr, edata_dict in graph[work_id].items():
                if nbr not in relevant_author_ids:
                    continue
                for e in edata_dict.values():
                    if e.get("edge_type") == "authored":
                        kept_work_ids.add(work_id)
                        break
                if work_id in kept_work_ids:
                    break

        works.root = {k: v for k, v in works.root.items() if k in kept_work_ids}

        # ***
        # 2. Filter institutions
        # ***
        kept_institution_ids: Set[str] = set()

        for inst_id in institutions.root.keys():
            if inst_id not in graph:
                continue

            for nbr, edata_dict in graph[inst_id].items():
                if nbr not in relevant_author_ids:
                    continue
                for e in edata_dict.values():
                    if e.get("edge_type") == "affiliated_with":
                        kept_institution_ids.add(inst_id)
                        break
                if inst_id in kept_institution_ids:
                    break

        institutions.root = {
            k: v for k, v in institutions.root.items() if k in kept_institution_ids
        }

        # ***
        # 3. Filter and transform authors
        # ***
        recommender_authors: Dict[str, ExpertRecommender_Author] = {}

        for author_id in relevant_author_ids:
            search_author = authors.root.get(author_id)
            if not search_author:
                continue

            # Merge works_search and works_author into distinct works list
            merged_works = set()
            if getattr(search_author, "works_search", None):
                merged_works.update(search_author.works_search)
            if getattr(search_author, "works_author", None):
                merged_works.update(search_author.works_author)

            works_list = list(merged_works) if merged_works else None

            # use original openalex id for topic ids
            tmp_relevant_topics = {
                f"https://openalex.org/{topic_id}": val
                for topic_id, val in search_author.relevant_topics.items()
            }

            recommender_authors[author_id] = ExpertRecommender_Author(
                openalex_id=search_author.openalex_id,
                orcid_id=search_author.orcid_id,
                display_name=search_author.display_name,
                two_yr_mean_citedness=search_author.two_yr_mean_citedness,
                h_index=search_author.h_index,
                i10_index=search_author.i10_index,
                scores=None,
                expert_connections=None,
                relevant_topics=tmp_relevant_topics,
                relevant_topics_share=search_author.relevant_topics_share,
                active_years_min=search_author.active_years_min,
                active_years_max=search_author.active_years_max,
                active_years_sum=search_author.active_years_sum,
                active_years_counted=search_author.active_years_counted,
                institutions=search_author.institutions,
                instituitions_count=len(search_author.institutions or []),
                works=works_list,
                works_count=len(works_list or []),
            )

        return works, institutions, ExpertRecommender_Authors(recommender_authors)

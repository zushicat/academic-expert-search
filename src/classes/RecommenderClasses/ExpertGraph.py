from datetime import datetime
import math
from typing import Dict, Any, List, Set, Tuple

from models.expert_search_models import ExpertSearch_Response

import networkx as nx


class ExpertGraph:
    def __init__(self, search_result: ExpertSearch_Response):
        self.class_name = self.__class__.__name__
        self.graph: nx.MultiGraph = self.build_graph(search_result=search_result)

    def build_graph(self, search_result: ExpertSearch_Response) -> nx.MultiGraph:
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

    def get_best_experts(self) -> Dict[str, Any]:
        current_year = datetime.now().year

        # collect author nodes
        authors = [
            n for n, d in self.graph.nodes(data=True) if d.get("node_type") == "author"
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
            data = self.graph.nodes[author]

            # ***
            # Topic expertise: sum of expertise edge weights
            # ***
            topic_score = 0.0
            for _, _, edata in self.graph.edges(author, data=True):
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
                for nbr, edata in self.graph[author].items()
                for e in edata.values()
                if e.get("edge_type") == "authored"
            ]
            productivity_raw[author] = len(set(authored_works))

            # ***
            # Recency: based on most recent publication year
            # ***
            years = []
            for work in set(authored_works):
                year = self.graph.nodes[work].get("publication_year")
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
                tmp = {"overall_score": raw_result[1]}
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

    def get_connected_authors(self) -> Dict[str, Any]:
        """
        Detect author groups using Option A-2:
        - Groups are cliques formed by authors on the same work or institution
        - Groups are deduplicated by identical author membership
        - No transitive closure, no topics
        """
        # collect author nodes
        authors = {
            n for n, d in self.graph.nodes(data=True) if d.get("node_type") == "author"
        }

        # ***
        # Co-authorship cliques (works)
        # ***
        coauthor_groups = {}

        for node, data in self.graph.nodes(data=True):
            if data.get("node_type") != "work":
                continue

            work_id = node
            work_authors = []

            for nbr, edata_dict in self.graph[work_id].items():
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

        # ***
        # Institution cliques
        # ***
        institution_groups = {}

        for node, data in self.graph.nodes(data=True):
            if data.get("node_type") != "institution":
                continue

            inst_id = node
            inst_authors = []

            for nbr, edata_dict in self.graph[inst_id].items():
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

        # ***
        # Assign group IDs
        # ***
        coauthor_group_list = []
        for idx, group in enumerate(coauthor_groups.values()):
            group["group_id"] = idx
            coauthor_group_list.append(group)

        institution_group_list = []
        for idx, group in enumerate(institution_groups.values()):
            group["group_id"] = idx
            institution_group_list.append(group)

        # ***
        # Author membership index
        # ***
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

        # ***
        # Connectivity scores
        # ***
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

        # sort authors by connectivity score (desc)
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

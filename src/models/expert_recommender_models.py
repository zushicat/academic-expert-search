from typing import Any, Dict, List

from models.expert_search_models import (
    ExpertSearch_Response,
    ExpertSearch_Works,
    ExpertSearch_Work,
    ExpertSearch_Topics,
    ExpertSearch_Institutions,
    ExpertSearch_Institution,
    ExpertSearch_AuthorInstitution,
    ExpertSearch_Meta,
)

from pydantic import BaseModel, RootModel


class ExpertRecommender_ExpertConnection(BaseModel):
    openalex_id: str
    connected_by_work: bool = False
    connected_by_affiliation: bool = False


class ExpertRecommender_AuthorScores(BaseModel):
    overall_score: float = 0.0
    topic: float = 0.0
    impact: float = 0.0
    productivity: float = 0.0
    recency: float = 0.0
    connectivity_score_works: float = 0.0
    connectivity_score_institutions: float = 0.0
    connectivity_score: float = 0.0


class ExpertRecommender_Author(BaseModel):
    openalex_id: str
    orcid_id: str | None
    display_name: str
    # from_relevant_author_list: bool

    two_yr_mean_citedness: float | None
    h_index: int | None
    i10_index: int | None

    scores: List[ExpertRecommender_AuthorScores] | None

    relevant_topics: Dict[str, bool]
    relevant_topics_share: int

    active_years_min: int | None
    active_years_max: int | None
    active_years_sum: int | None
    active_years_counted: Dict[int, int] | None

    institutions: List[ExpertSearch_AuthorInstitution] | None
    instituitions_count: int

    works: List[str] | None
    works_count: int = 0

    expert_connections: List[ExpertRecommender_ExpertConnection] | None


class ExpertRecommender_Authors(RootModel[Dict[str, ExpertRecommender_Author]]):
    pass

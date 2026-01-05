from typing import Any, Dict, List

from pydantic import BaseModel, RootModel


class ExpertSearch_Work(BaseModel):
    openalex_id: str
    doi: str | None
    title: str
    publication_year: int | None
    relevance_score: float | None
    cited_by_count: int | None
    primary_topic: str | None
    topics: List[str]
    author_ids: List[str]
    from_query_search: bool = False


class ExpertSearch_Works(RootModel[Dict[str, ExpertSearch_Work]]):
    pass


class ExpertSearch_Topic(BaseModel):
    id: str
    display_name: str | None = None
    score: float | None = None
    subfield: Dict[str, Any] | None = None
    field: Dict[str, Any] | None = None
    domain: Dict[str, Any] | None = None


class ExpertSearch_Topics(RootModel[Dict[str, ExpertSearch_Topic]]):
    pass


class ExpertSearch_Institution(BaseModel):
    openalex_id: str
    ror: str | None = None
    display_name: str | None = None
    country_code: str | None = None
    type: str | None = None


class ExpertSearch_Institutions(RootModel[Dict[str, ExpertSearch_Institution]]):
    pass


class ExpertSearch_AuthorInstitution(BaseModel):
    openalex_id: str
    year_start: int
    year_end: int


class ExpertSearch_Author(BaseModel):
    openalex_id: str
    orcid_id: str | None
    display_name: str
    from_relevant_author_list: bool

    two_yr_mean_citedness: float | None
    h_index: int | None
    i10_index: int | None

    relevant_topics: Dict[str, bool]
    relevant_topics_share: int

    active_years_min: int | None
    active_years_max: int | None
    active_years_sum: int | None
    active_years_counted: Dict[int, int] | None

    institutions: List[ExpertSearch_AuthorInstitution] | None
    instituitions_count: int

    works_search: List[str] | None


class ExpertSearch_Authors(RootModel[Dict[str, ExpertSearch_Author]]):
    pass


class ExpertSearch_Meta(BaseModel):
    query: str
    reference_author_count: int
    author_count: int
    works_count: int
    institutions_count: int
    best_match_topics: Dict[str, int]
    topics_filter: str
    authors_topic_share_counts: Dict[int, int]


class ExpertSearch_Response(BaseModel):
    topics: ExpertSearch_Topics
    works: ExpertSearch_Works
    institutions: ExpertSearch_Institutions
    authors: ExpertSearch_Authors
    meta: ExpertSearch_Meta

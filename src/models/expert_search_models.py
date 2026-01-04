from typing import Any, Dict, List, Tuple

from pydantic import BaseModel


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


class ExpertSearch_Works(BaseModel):
    __root__: Dict[str, ExpertSearch_Work]


class ExpertSearch_Topic(BaseModel):
    id: str
    display_name: str | None = None
    score: float | None = None
    subfield: Dict[str, Any] | None = None
    field: Dict[str, Any] | None = None
    domain: Dict[str, Any] | None = None


class ExpertSearch_Topics(BaseModel):
    __root__: Dict[str, ExpertSearch_Topic]


class ExpertSearch_Institution(BaseModel):
    openalex_id: str
    display_name: str | None = None
    country_code: str | None = None
    type: str | None = None


class ExpertSearch_Institutions(BaseModel):
    __root__: Dict[str, ExpertSearch_Institution]


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


class ExpertSearch_Authors(BaseModel):
    __root__: Dict[str, ExpertSearch_Author]


class ExpertSearch_Meta(BaseModel):
    query: str
    reference_author_count: int
    author_count: int
    works_count: int
    institutions_count: int
    best_match_topics: Dict[str, int]
    topics_filter: str


class ExpertSearch_Response(BaseModel):
    topics: ExpertSearch_Topics
    works: ExpertSearch_Works
    institutions: ExpertSearch_Institutions
    authors: ExpertSearch_Authors
    meta: ExpertSearch_Meta

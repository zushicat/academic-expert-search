from typing import Any, Dict, List

from pydantic import BaseModel, RootModel


class ExpertSearchResponse_Work(BaseModel):
    openalex_id: str
    doi: str | None
    title: str
    publication_year: int | None
    primary_topic: str | None
    author_ids: List[str]


class ExpertSearchResponse_Topic(BaseModel):
    id: str
    display_name: str | None = None


class ExpertSearchResponse_Institution(BaseModel):
    openalex_id: str
    ror: str | None = None
    display_name: str | None = None
    country_code: str | None = None
    type: str | None = None


class ExpertSearchResponse_AuthorInstitution(BaseModel):
    openalex_id: str
    year_start: int
    year_end: int


class ExpertSearchResponse_Author(BaseModel):
    openalex_id: str
    orcid_id: str | None
    display_name: str

    two_yr_mean_citedness: float | None
    h_index: int | None
    i10_index: int | None

    relevant_topics: List[
        str
    ]  # list of topics i.e. https://openalex.org/T10487 which are set true
    relevant_topics_share: int

    active_years_min: int | None
    active_years_max: int | None
    active_years_sum: int | None

    institutions: List[ExpertSearchResponse_AuthorInstitution] | None
    instituitions_count: int

    works_search: List[str] | None
    works_search_count: int = 0

from typing import Any, Dict, List

from pydantic import BaseModel, RootModel


class ExpertRecommenderResponse_Topic(BaseModel):
    id: str
    display_name: str | None = None


class ExpertRecommenderResponse_Work(BaseModel):
    openalex_id: str
    doi: str | None
    title: str
    publication_year: int | None
    primary_topic: str | None
    author_ids: List[str]


class ExpertRecommenderResponse_Institution(BaseModel):
    openalex_id: str
    ror: str | None = None
    display_name: str | None = None
    country_code: str | None = None
    type: str | None = None


class ExpertRecommenderResponse_AuthorInstitution(BaseModel):
    openalex_id: str
    year_start: int
    year_end: int


class ExpertRecommenderResponse_Author(BaseModel):
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

    institutions: List[ExpertRecommenderResponse_AuthorInstitution] | None
    instituitions_count: int

    works: List[str] | None
    works_count: int = 0

    summary: str | None = None

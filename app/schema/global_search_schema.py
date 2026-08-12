import typing
from enum import Enum

import strawberry
from strawberry.types import Info

from app.clients.opensearch.opensearch_client import run_global_search
from app.exception.UserException import REException
from app.utils.log_utils import log_msg


@strawberry.enum
class SearchEntityType(Enum):
    USER = "USER"
    POST = "POST"
    PROPERTY = "PROPERTY"
    COMMENT = "COMMENT"


@strawberry.enum
class SearchSort(Enum):
    RELEVANCE = "RELEVANCE"


@strawberry.input
class PaginationInput:
    page: int = 0
    size: int = 20


@strawberry.input
class GlobalSearchRequest:
    keyword: str
    entityTypes: typing.Optional[typing.List[SearchEntityType]] = None
    pagination: typing.Optional[PaginationInput] = None
    sortBy: SearchSort = SearchSort.RELEVANCE


@strawberry.type
class SearchResult:
    id: str
    entityType: SearchEntityType
    title: str
    bio: typing.Optional[str] = None
    description: typing.Optional[str] = None
    imageUrl: typing.Optional[str] = None
    location: typing.Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "SearchResult":
        return cls(
            id=data["id"],
            entityType=SearchEntityType(data["entityType"]),
            title=data["title"],
            bio=data.get("bio"),
            description=data.get("description"),
            imageUrl=data.get("imageUrl"),
            location=data.get("location"),
        )


@strawberry.type
class GlobalSearchResponse:
    totalHits: int
    page: int
    size: int
    results: typing.List[SearchResult]


@strawberry.type
class Query:
    @strawberry.field
    def globalSearch(self, info: Info, request: GlobalSearchRequest) -> GlobalSearchResponse:
        log_msg("debug", f"Query.globalSearch keyword={request.keyword!r}")
        try:
            pagination = request.pagination or PaginationInput()
            entity_types = (
                [entity.value for entity in request.entityTypes]
                if request.entityTypes
                else None
            )

            total_hits, page, size, raw_results = run_global_search(
                keyword=request.keyword,
                entity_types=entity_types,
                page=pagination.page,
                size=pagination.size,
            )

            return GlobalSearchResponse(
                totalHits=total_hits,
                page=page,
                size=size,
                results=[SearchResult.from_dict(item) for item in raw_results],
            )
        except Exception as exc:
            log_msg("error", f"globalSearch failed: {exc}")
            raise REException(
                "SEARCH_FAILED",
                "Global search failed",
                str(exc),
            ).to_graphql_error()

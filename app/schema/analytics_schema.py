from datetime import datetime, timezone

import strawberry
from graphql import GraphQLError
from strawberry.types import Info

from app.clients.clickhouse.analytics_repository import (
    fetch_comment_analytics,
    fetch_post_analytics,
    fetch_property_analytics,
    fetch_user_analytics,
    to_iso_date,
)
from app.exception.UserException import REException
from app.utils.jwt_utils import decode_jwt_token, get_token
from app.utils.log_utils import log_msg


def _viewer_id(token: str) -> str:
    if not token:
        return ""
    try:
        payload = decode_jwt_token(token)
        return str(payload.get("sub") or payload.get("user_id") or "").strip()
    except Exception:
        return ""


def _viewer_role(token: str) -> str:
    if not token:
        return ""
    try:
        payload = decode_jwt_token(token)
        return str(payload.get("role") or "").strip().upper()
    except Exception:
        return ""


def _require_admin(token: str) -> str:
    user_id = _viewer_id(token)
    if not user_id:
        raise REException("UNAUTHORIZED", "Login required", "Missing user").to_graphql_error()
    if _viewer_role(token) != "ADMIN":
        raise REException("FORBIDDEN", "Admin access required", "Not admin").to_graphql_error()
    return user_id


def _validate_range(from_date: datetime, to_date: datetime) -> None:
    start = from_date if from_date.tzinfo else from_date.replace(tzinfo=timezone.utc)
    end = to_date if to_date.tzinfo else to_date.replace(tzinfo=timezone.utc)
    if start > end:
        raise REException(
            "INVALID_DATE_RANGE",
            "fromDate must be before toDate",
            "Invalid analytics date range",
        ).to_graphql_error()
    if (end - start).days > 366:
        raise REException(
            "INVALID_DATE_RANGE",
            "Date range cannot exceed 366 days",
            "Narrow the analytics window",
        ).to_graphql_error()


@strawberry.input
class UserAnalyticsRequest:
    fromDate: datetime
    toDate: datetime


@strawberry.type
class DailyCount:
    date: str
    count: int
    uniqueUsers: int


@strawberry.type
class NamedCount:
    name: str
    count: int
    uniqueUsers: int


@strawberry.type
class TopEntity:
    id: str
    code: str
    name: str
    city: str
    views: int
    saves: int
    likes: int


@strawberry.type
class UserAnalyticsResponse:
    totalUsers: int
    dailyActiveUsers: int
    monthlyActiveUsers: int
    newRegistrations: int
    loginCount: int
    engagedUsers: int
    platformEngagedUsers: int
    follows: int
    sessions: int
    loginTrends: list[DailyCount]
    loginsByMethod: list[NamedCount]
    loginsByDevice: list[NamedCount]


@strawberry.type
class PropertyAnalyticsResponse:
    totalViews: int
    uniqueViewers: int
    uniqueProperties: int
    saves: int
    shares: int
    ratings: int
    reports: int
    avgViewDurationSeconds: int
    viewsByDay: list[DailyCount]
    topProperties: list[TopEntity]


@strawberry.type
class PostAnalyticsResponse:
    totalViews: int
    uniqueViewers: int
    uniquePosts: int
    likes: int
    unlikes: int
    shares: int
    saves: int
    comments: int
    reports: int
    avgViewDurationSeconds: int
    viewsByDay: list[DailyCount]
    topPosts: list[TopEntity]


@strawberry.type
class CommentAnalyticsResponse:
    commentsCreated: int
    uniqueCommenters: int
    likes: int
    reports: int
    replies: int
    commentsByDay: list[DailyCount]


def _daily_counts(rows: list[dict]) -> list[DailyCount]:
    return [
        DailyCount(
            date=to_iso_date(row["date"]),
            count=row["count"],
            uniqueUsers=row["uniqueUsers"],
        )
        for row in rows
    ]


def _named_counts(rows: list[dict]) -> list[NamedCount]:
    return [
        NamedCount(name=row["name"], count=row["count"], uniqueUsers=row["uniqueUsers"])
        for row in rows
    ]


def _top_entities(rows: list[dict]) -> list[TopEntity]:
    return [
        TopEntity(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            city=row["city"],
            views=row["views"],
            saves=row["saves"],
            likes=row["likes"],
        )
        for row in rows
    ]


@strawberry.type
class Query:
    @strawberry.field
    def userAnalytics(self, info: Info, request: UserAnalyticsRequest) -> UserAnalyticsResponse:
        token = get_token(info)
        _require_admin(token)
        _validate_range(request.fromDate, request.toDate)
        log_msg("info", f"userAnalytics from={request.fromDate} to={request.toDate}")
        try:
            data = fetch_user_analytics(request.fromDate, request.toDate)
            log_msg(
                "info",
                "userAnalytics result "
                f"totalUsers={data['totalUsers']} dau={data['dailyActiveUsers']} "
                f"logins={data['loginCount']} trends={len(data['loginTrends'])}",
            )
            return UserAnalyticsResponse(
                totalUsers=data["totalUsers"],
                dailyActiveUsers=data["dailyActiveUsers"],
                monthlyActiveUsers=data["monthlyActiveUsers"],
                newRegistrations=data["newRegistrations"],
                loginCount=data["loginCount"],
                engagedUsers=data["engagedUsers"],
                platformEngagedUsers=data["platformEngagedUsers"],
                follows=data["follows"],
                sessions=data["sessions"],
                loginTrends=_daily_counts(data["loginTrends"]),
                loginsByMethod=_named_counts(data["loginsByMethod"]),
                loginsByDevice=_named_counts(data["loginsByDevice"]),
            )
        except GraphQLError:
            raise
        except Exception as exc:
            log_msg("error", f"userAnalytics failed: {exc}")
            raise REException(
                "ANALYTICS_FAILED",
                "Failed to load user analytics",
                str(exc),
            ).to_graphql_error()

    @strawberry.field
    def propertyAnalytics(self, info: Info, request: UserAnalyticsRequest) -> PropertyAnalyticsResponse:
        token = get_token(info)
        _require_admin(token)
        _validate_range(request.fromDate, request.toDate)
        log_msg("info", f"propertyAnalytics from={request.fromDate} to={request.toDate}")
        try:
            data = fetch_property_analytics(request.fromDate, request.toDate)
            log_msg(
                "info",
                "propertyAnalytics result "
                f"views={data['totalViews']} properties={data['uniqueProperties']} "
                f"days={len(data['viewsByDay'])}",
            )
            return PropertyAnalyticsResponse(
                totalViews=data["totalViews"],
                uniqueViewers=data["uniqueViewers"],
                uniqueProperties=data["uniqueProperties"],
                saves=data["saves"],
                shares=data["shares"],
                ratings=data["ratings"],
                reports=data["reports"],
                avgViewDurationSeconds=data["avgViewDurationSeconds"],
                viewsByDay=_daily_counts(data["viewsByDay"]),
                topProperties=_top_entities(data["topProperties"]),
            )
        except GraphQLError:
            raise
        except Exception as exc:
            log_msg("error", f"propertyAnalytics failed: {exc}")
            raise REException(
                "ANALYTICS_FAILED",
                "Failed to load property analytics",
                str(exc),
            ).to_graphql_error()

    @strawberry.field
    def postAnalytics(self, info: Info, request: UserAnalyticsRequest) -> PostAnalyticsResponse:
        token = get_token(info)
        _require_admin(token)
        _validate_range(request.fromDate, request.toDate)
        log_msg("info", f"postAnalytics from={request.fromDate} to={request.toDate}")
        try:
            data = fetch_post_analytics(request.fromDate, request.toDate)
            log_msg(
                "info",
                "postAnalytics result "
                f"views={data['totalViews']} posts={data['uniquePosts']} "
                f"days={len(data['viewsByDay'])}",
            )
            return PostAnalyticsResponse(
                totalViews=data["totalViews"],
                uniqueViewers=data["uniqueViewers"],
                uniquePosts=data["uniquePosts"],
                likes=data["likes"],
                unlikes=data["unlikes"],
                shares=data["shares"],
                saves=data["saves"],
                comments=data["comments"],
                reports=data["reports"],
                avgViewDurationSeconds=data["avgViewDurationSeconds"],
                viewsByDay=_daily_counts(data["viewsByDay"]),
                topPosts=_top_entities(data["topPosts"]),
            )
        except GraphQLError:
            raise
        except Exception as exc:
            log_msg("error", f"postAnalytics failed: {exc}")
            raise REException(
                "ANALYTICS_FAILED",
                "Failed to load post analytics",
                str(exc),
            ).to_graphql_error()

    @strawberry.field
    def commentAnalytics(self, info: Info, request: UserAnalyticsRequest) -> CommentAnalyticsResponse:
        token = get_token(info)
        _require_admin(token)
        _validate_range(request.fromDate, request.toDate)
        log_msg("info", f"commentAnalytics from={request.fromDate} to={request.toDate}")
        try:
            data = fetch_comment_analytics(request.fromDate, request.toDate)
            log_msg(
                "info",
                "commentAnalytics result "
                f"created={data['commentsCreated']} commenters={data['uniqueCommenters']} "
                f"days={len(data['commentsByDay'])}",
            )
            return CommentAnalyticsResponse(
                commentsCreated=data["commentsCreated"],
                uniqueCommenters=data["uniqueCommenters"],
                likes=data["likes"],
                reports=data["reports"],
                replies=data["replies"],
                commentsByDay=_daily_counts(data["commentsByDay"]),
            )
        except GraphQLError:
            raise
        except Exception as exc:
            log_msg("error", f"commentAnalytics failed: {exc}")
            raise REException(
                "ANALYTICS_FAILED",
                "Failed to load comment analytics",
                str(exc),
            ).to_graphql_error()

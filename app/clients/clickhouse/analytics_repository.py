from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from app.clients.clickhouse.clickhouse_client import get_clickhouse_client

# Reuse worker threads so each keeps a thread-local ClickHouse client.
# clickhouse-connect forbids concurrent queries on the same client/session.
_QUERY_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="ch-analytics")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _query_one(sql: str, parameters: Dict[str, Any]) -> Tuple[Any, ...]:
    result = get_clickhouse_client().query(sql, parameters=parameters)
    if not result.result_rows:
        return tuple()
    return result.result_rows[0]


def _query_rows(sql: str, parameters: Dict[str, Any]) -> List[Tuple[Any, ...]]:
    result = get_clickhouse_client().query(sql, parameters=parameters)
    return list(result.result_rows or [])


def _range_params(from_date: datetime, to_date: datetime) -> Dict[str, Any]:
    start = _utc(from_date)
    end = _utc(to_date)
    dau_date = end.date()
    mau_from = dau_date - timedelta(days=29)
    return {
        "from_ts": start,
        "to_ts": end,
        "dau_date": dau_date,
        "mau_from": mau_from,
        "to_date": dau_date,
    }


def fetch_user_analytics(from_date: datetime, to_date: datetime) -> Dict[str, Any]:
    params = _range_params(from_date, to_date)

    summary_sql = """
        SELECT
            uniqExactIf(user_id, event_type = 'USER_REGISTERED') AS total_users,
            uniqExactIf(user_id, event_date = {dau_date:Date}) AS daily_active_users,
            uniqExactIf(user_id, event_date >= {mau_from:Date}) AS monthly_active_users,
            countIf(event_type = 'USER_REGISTERED' AND event_time >= {from_ts:DateTime64(3)} AND event_time <= {to_ts:DateTime64(3)}) AS new_registrations,
            countIf(event_type = 'USER_LOGIN' AND event_time >= {from_ts:DateTime64(3)} AND event_time <= {to_ts:DateTime64(3)}) AS login_count,
            uniqExactIf(user_id, event_time >= {from_ts:DateTime64(3)} AND event_time <= {to_ts:DateTime64(3)}) AS engaged_users,
            countIf(event_type = 'USER_FOLLOWED' AND event_time >= {from_ts:DateTime64(3)} AND event_time <= {to_ts:DateTime64(3)}) AS follows,
            countIf(event_type = 'USER_SESSION_STARTED' AND event_time >= {from_ts:DateTime64(3)} AND event_time <= {to_ts:DateTime64(3)}) AS sessions
        FROM user_activity_event
        WHERE event_date <= {to_date:Date}
    """

    trends_sql = """
        SELECT
            event_date,
            count() AS login_count,
            uniqExact(user_id) AS unique_users
        FROM user_activity_event
        WHERE event_type = 'USER_LOGIN'
          AND event_time >= {from_ts:DateTime64(3)}
          AND event_time <= {to_ts:DateTime64(3)}
        GROUP BY event_date
        ORDER BY event_date
    """

    method_sql = """
        SELECT
            if(login_method = '', 'unknown', login_method) AS name,
            count() AS login_count,
            uniqExact(user_id) AS unique_users
        FROM user_activity_event
        WHERE event_type = 'USER_LOGIN'
          AND event_time >= {from_ts:DateTime64(3)}
          AND event_time <= {to_ts:DateTime64(3)}
        GROUP BY name
        ORDER BY login_count DESC
    """

    device_sql = """
        SELECT
            if(device_type = '', 'unknown', device_type) AS name,
            count() AS login_count,
            uniqExact(user_id) AS unique_users
        FROM user_activity_event
        WHERE event_type = 'USER_LOGIN'
          AND event_time >= {from_ts:DateTime64(3)}
          AND event_time <= {to_ts:DateTime64(3)}
        GROUP BY name
        ORDER BY login_count DESC
    """

    platform_sql = """
        SELECT uniqExact(user_id)
        FROM (
            SELECT user_id FROM user_activity_event
            WHERE event_time >= {from_ts:DateTime64(3)} AND event_time <= {to_ts:DateTime64(3)}
            UNION ALL
            SELECT user_id FROM property_activity_event
            WHERE event_time >= {from_ts:DateTime64(3)} AND event_time <= {to_ts:DateTime64(3)}
            UNION ALL
            SELECT user_id FROM post_activity_event
            WHERE event_time >= {from_ts:DateTime64(3)} AND event_time <= {to_ts:DateTime64(3)}
            UNION ALL
            SELECT user_id FROM comment_activity_event
            WHERE event_time >= {from_ts:DateTime64(3)} AND event_time <= {to_ts:DateTime64(3)}
        )
    """

    summary_f = _QUERY_POOL.submit(_query_one, summary_sql, params)
    trends_f = _QUERY_POOL.submit(_query_rows, trends_sql, params)
    method_f = _QUERY_POOL.submit(_query_rows, method_sql, params)
    device_f = _QUERY_POOL.submit(_query_rows, device_sql, params)
    platform_f = _QUERY_POOL.submit(_query_one, platform_sql, params)
    summary = summary_f.result()
    trends = trends_f.result()
    methods = method_f.result()
    devices = device_f.result()
    platform = platform_f.result()

    return {
        "totalUsers": _as_int(summary[0] if summary else 0),
        "dailyActiveUsers": _as_int(summary[1] if summary else 0),
        "monthlyActiveUsers": _as_int(summary[2] if summary else 0),
        "newRegistrations": _as_int(summary[3] if summary else 0),
        "loginCount": _as_int(summary[4] if summary else 0),
        "engagedUsers": _as_int(summary[5] if summary else 0),
        "follows": _as_int(summary[6] if summary else 0),
        "sessions": _as_int(summary[7] if summary else 0),
        "platformEngagedUsers": _as_int(platform[0] if platform else 0),
        "loginTrends": [
            {"date": row[0], "count": _as_int(row[1]), "uniqueUsers": _as_int(row[2])}
            for row in trends
        ],
        "loginsByMethod": [
            {"name": str(row[0] or "unknown"), "count": _as_int(row[1]), "uniqueUsers": _as_int(row[2])}
            for row in methods
        ],
        "loginsByDevice": [
            {"name": str(row[0] or "unknown"), "count": _as_int(row[1]), "uniqueUsers": _as_int(row[2])}
            for row in devices
        ],
    }


def fetch_property_analytics(from_date: datetime, to_date: datetime) -> Dict[str, Any]:
    params = _range_params(from_date, to_date)

    summary_sql = """
        SELECT
            countIf(event_type = 'PROPERTY_VIEWED') AS views,
            uniqExactIf(user_id, event_type = 'PROPERTY_VIEWED') AS unique_viewers,
            uniqExact(property_id) AS unique_properties,
            countIf(event_type = 'PROPERTY_SAVED') AS saves,
            countIf(event_type = 'PROPERTY_SHARED') AS shares,
            countIf(event_type = 'PROPERTY_RATED') AS ratings,
            countIf(event_type = 'PROPERTY_REPORTED') AS reports,
            ifNotFinite(avgIf(view_duration, event_type = 'PROPERTY_VIEWED' AND view_duration > 0), 0) AS avg_view_duration
        FROM property_activity_event
        WHERE event_time >= {from_ts:DateTime64(3)}
          AND event_time <= {to_ts:DateTime64(3)}
    """

    daily_sql = """
        SELECT
            event_date,
            countIf(event_type = 'PROPERTY_VIEWED') AS views,
            uniqExactIf(user_id, event_type = 'PROPERTY_VIEWED') AS unique_users
        FROM property_activity_event
        WHERE event_time >= {from_ts:DateTime64(3)}
          AND event_time <= {to_ts:DateTime64(3)}
        GROUP BY event_date
        ORDER BY event_date
    """

    top_sql = """
        SELECT
            toString(property_id) AS id,
            any(property_code) AS code,
            any(project_name) AS name,
            any(city) AS city,
            countIf(event_type = 'PROPERTY_VIEWED') AS views,
            countIf(event_type = 'PROPERTY_SAVED') AS saves
        FROM property_activity_event
        WHERE event_time >= {from_ts:DateTime64(3)}
          AND event_time <= {to_ts:DateTime64(3)}
        GROUP BY property_id
        ORDER BY views DESC
        LIMIT 10
    """

    summary_f = _QUERY_POOL.submit(_query_one, summary_sql, params)
    daily_f = _QUERY_POOL.submit(_query_rows, daily_sql, params)
    top_f = _QUERY_POOL.submit(_query_rows, top_sql, params)
    summary = summary_f.result()
    daily = daily_f.result()
    top = top_f.result()

    return {
        "totalViews": _as_int(summary[0] if summary else 0),
        "uniqueViewers": _as_int(summary[1] if summary else 0),
        "uniqueProperties": _as_int(summary[2] if summary else 0),
        "saves": _as_int(summary[3] if summary else 0),
        "shares": _as_int(summary[4] if summary else 0),
        "ratings": _as_int(summary[5] if summary else 0),
        "reports": _as_int(summary[6] if summary else 0),
        "avgViewDurationSeconds": _as_int(summary[7] if summary else 0),
        "viewsByDay": [
            {"date": row[0], "count": _as_int(row[1]), "uniqueUsers": _as_int(row[2])}
            for row in daily
        ],
        "topProperties": [
            {
                "id": str(row[0] or ""),
                "code": str(row[1] or ""),
                "name": str(row[2] or ""),
                "city": str(row[3] or ""),
                "views": _as_int(row[4]),
                "saves": _as_int(row[5]),
                "likes": 0,
            }
            for row in top
        ],
    }


def fetch_post_analytics(from_date: datetime, to_date: datetime) -> Dict[str, Any]:
    params = _range_params(from_date, to_date)

    summary_sql = """
        SELECT
            countIf(event_type = 'POST_VIEWED') AS views,
            uniqExactIf(user_id, event_type = 'POST_VIEWED') AS unique_viewers,
            uniqExact(post_id) AS unique_posts,
            countIf(event_type = 'POST_LIKED') AS likes,
            countIf(event_type = 'POST_UNLIKED') AS unlikes,
            countIf(event_type = 'POST_SHARED') AS shares,
            countIf(event_type = 'POST_SAVED') AS saves,
            countIf(event_type = 'POST_COMMENTED') AS comments,
            countIf(event_type = 'POST_REPORTED') AS reports,
            ifNotFinite(avgIf(view_duration, event_type = 'POST_VIEWED' AND view_duration > 0), 0) AS avg_view_duration
        FROM post_activity_event
        WHERE event_time >= {from_ts:DateTime64(3)}
          AND event_time <= {to_ts:DateTime64(3)}
    """

    daily_sql = """
        SELECT
            event_date,
            countIf(event_type = 'POST_VIEWED') AS views,
            uniqExactIf(user_id, event_type = 'POST_VIEWED') AS unique_users
        FROM post_activity_event
        WHERE event_time >= {from_ts:DateTime64(3)}
          AND event_time <= {to_ts:DateTime64(3)}
        GROUP BY event_date
        ORDER BY event_date
    """

    top_sql = """
        SELECT
            toString(post_id) AS id,
            any(post_code) AS code,
            any(city) AS city,
            countIf(event_type = 'POST_VIEWED') AS views,
            countIf(event_type = 'POST_SAVED') AS saves,
            countIf(event_type = 'POST_LIKED') AS likes
        FROM post_activity_event
        WHERE event_time >= {from_ts:DateTime64(3)}
          AND event_time <= {to_ts:DateTime64(3)}
        GROUP BY post_id
        ORDER BY views DESC
        LIMIT 10
    """

    summary_f = _QUERY_POOL.submit(_query_one, summary_sql, params)
    daily_f = _QUERY_POOL.submit(_query_rows, daily_sql, params)
    top_f = _QUERY_POOL.submit(_query_rows, top_sql, params)
    summary = summary_f.result()
    daily = daily_f.result()
    top = top_f.result()

    return {
        "totalViews": _as_int(summary[0] if summary else 0),
        "uniqueViewers": _as_int(summary[1] if summary else 0),
        "uniquePosts": _as_int(summary[2] if summary else 0),
        "likes": _as_int(summary[3] if summary else 0),
        "unlikes": _as_int(summary[4] if summary else 0),
        "shares": _as_int(summary[5] if summary else 0),
        "saves": _as_int(summary[6] if summary else 0),
        "comments": _as_int(summary[7] if summary else 0),
        "reports": _as_int(summary[8] if summary else 0),
        "avgViewDurationSeconds": _as_int(summary[9] if summary else 0),
        "viewsByDay": [
            {"date": row[0], "count": _as_int(row[1]), "uniqueUsers": _as_int(row[2])}
            for row in daily
        ],
        "topPosts": [
            {
                "id": str(row[0] or ""),
                "code": str(row[1] or ""),
                "name": str(row[1] or ""),
                "city": str(row[2] or ""),
                "views": _as_int(row[3]),
                "saves": _as_int(row[4]),
                "likes": _as_int(row[5]),
            }
            for row in top
        ],
    }


def fetch_comment_analytics(from_date: datetime, to_date: datetime) -> Dict[str, Any]:
    params = _range_params(from_date, to_date)

    summary_sql = """
        SELECT
            countIf(event_type = 'COMMENT_CREATED') AS comments_created,
            uniqExactIf(user_id, event_type = 'COMMENT_CREATED') AS unique_commenters,
            countIf(event_type = 'COMMENT_LIKED') AS likes,
            countIf(event_type = 'COMMENT_REPORTED') AS reports,
            countIf(event_type = 'COMMENT_CREATED' AND parent_comment_id IS NOT NULL) AS replies
        FROM comment_activity_event
        WHERE event_time >= {from_ts:DateTime64(3)}
          AND event_time <= {to_ts:DateTime64(3)}
    """

    daily_sql = """
        SELECT
            event_date,
            countIf(event_type = 'COMMENT_CREATED') AS comments_created,
            uniqExactIf(user_id, event_type = 'COMMENT_CREATED') AS unique_users
        FROM comment_activity_event
        WHERE event_time >= {from_ts:DateTime64(3)}
          AND event_time <= {to_ts:DateTime64(3)}
        GROUP BY event_date
        ORDER BY event_date
    """

    summary_f = _QUERY_POOL.submit(_query_one, summary_sql, params)
    daily_f = _QUERY_POOL.submit(_query_rows, daily_sql, params)
    summary = summary_f.result()
    daily = daily_f.result()

    return {
        "commentsCreated": _as_int(summary[0] if summary else 0),
        "uniqueCommenters": _as_int(summary[1] if summary else 0),
        "likes": _as_int(summary[2] if summary else 0),
        "reports": _as_int(summary[3] if summary else 0),
        "replies": _as_int(summary[4] if summary else 0),
        "commentsByDay": [
            {"date": row[0], "count": _as_int(row[1]), "uniqueUsers": _as_int(row[2])}
            for row in daily
        ],
    }


def to_iso_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)

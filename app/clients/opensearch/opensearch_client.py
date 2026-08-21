import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from dotenv import load_dotenv
from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError

from app.utils.log_utils import log_msg

load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=True)

_client_lock = threading.Lock()
_opensearch_client: Optional[OpenSearch] = None


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    if value is None:
        return None
    return value.strip().strip('"').strip("'")


DEFAULT_INDICES = {
    "USER": _env("OPENSEARCH_USER_INDEX", "user_index") or "user_index",
    "POST": _env("OPENSEARCH_POST_INDEX", "post_index") or "post_index",
    "PROPERTY": _env("OPENSEARCH_PROPERTY_INDEX", "property_index") or "property_index",
    "COMMENT": _env("OPENSEARCH_COMMENT_INDEX", "comment_index") or "comment_index",
}

MULTI_SEARCH_INDICES = [
    DEFAULT_INDICES["USER"],
    DEFAULT_INDICES["POST"],
    DEFAULT_INDICES["PROPERTY"],
    DEFAULT_INDICES["COMMENT"],
]

INDEX_TO_ENTITY = {
    "user_index": "USER",
    "post_index": "POST",
    "property_index": "PROPERTY",
    "comment_index": "COMMENT",
    "comments_index": "COMMENT",
}

SEARCH_FIELDS = [
    "title^3",
    "content",
    "description",
    "fullName^3",
    "bio",
    "location",
    "city",
    "role",
    "builderName",
]


def get_opensearch_client() -> OpenSearch:
    global _opensearch_client
    with _client_lock:
        if _opensearch_client is not None:
            return _opensearch_client

        host = _env("OPENSEARCH_HOST", "localhost")
        port = int(_env("OPENSEARCH_PORT", "9200") or "9200")
        scheme = (_env("OPENSEARCH_SCHEME", "http") or "http").lower()
        username = _env("OPENSEARCH_USERNAME")
        password = _env("OPENSEARCH_PASSWORD")
        uris = _env("OPENSEARCH_URIS")
        if uris:
            parsed = urlparse(uris)
            if parsed.hostname:
                host = parsed.hostname
            if parsed.port:
                port = parsed.port
            if parsed.scheme:
                scheme = parsed.scheme.lower()

        http_auth = (username, password) if username and password else None
        use_ssl = scheme == "https"

        _opensearch_client = OpenSearch(
            hosts=[{"host": host, "port": port, "scheme": scheme}],
            http_auth=http_auth,
            use_ssl=use_ssl,
            verify_certs=use_ssl,
            ssl_show_warn=False,
            timeout=20,
        )
        return _opensearch_client


def _indices_for_entity_types(entity_types: Optional[List[str]]) -> List[str]:
    if not entity_types:
        return list(MULTI_SEARCH_INDICES)

    indices: List[str] = []
    for entity_type in entity_types:
        index_name = DEFAULT_INDICES.get(entity_type.upper())
        if index_name and index_name not in indices:
            indices.append(index_name)
    return indices


def _entity_for_index(index_name: str) -> str:
    bare = (index_name or "").split(":")[-1]
    if bare in INDEX_TO_ENTITY:
        return INDEX_TO_ENTITY[bare]
    for key, entity in INDEX_TO_ENTITY.items():
        if bare.endswith(key):
            return entity
    return "USER"


def _location_from_source(source: Dict[str, Any]) -> Optional[str]:
    city = (source.get("city") or "").strip()
    state = (source.get("state") or "").strip()
    if city and state:
        return f"{city}, {state}"
    return city or state or source.get("location")


def _map_hit_to_result(hit: Dict[str, Any]) -> Dict[str, Any]:
    source = hit.get("_source", {}) or {}
    entity_type = _entity_for_index(hit.get("_index", ""))

    if entity_type == "USER":
        first_name = source.get("firstName") or ""
        last_name = source.get("lastName") or ""
        title = (source.get("fullName") or f"{first_name} {last_name}").strip()
        return {
            # Prefer UUID so UI can open profile / detail routes.
            "id": source.get("id") or source.get("userCode") or hit.get("_id", ""),
            "entityType": entity_type,
            "title": title or "User",
            "bio": source.get("role"),
            "description": source.get("bio"),
            "imageUrl": source.get("profilePhotoUrl"),
            "location": _location_from_source(source),
        }

    if entity_type == "POST":
        return {
            "id": source.get("id") or source.get("postCode") or hit.get("_id", ""),
            "entityType": entity_type,
            "title": source.get("title") or "Post",
            "bio": None,
            "description": source.get("content"),
            "imageUrl": source.get("thumbnailUrl"),
            "location": source.get("location"),
        }

    if entity_type == "PROPERTY":
        return {
            "id": source.get("id") or source.get("propertyCode") or hit.get("_id", ""),
            "entityType": entity_type,
            "title": source.get("title") or "Property",
            "bio": None,
            "description": source.get("description"),
            "imageUrl": source.get("thumbnailUrl"),
            "location": _location_from_source(source),
        }

    content = source.get("content") or ""
    return {
        "id": source.get("id") or source.get("commentId") or hit.get("_id", ""),
        "entityType": "COMMENT",
        "title": content[:120] if content else "Comment",
        "bio": None,
        "description": content,
        "imageUrl": None,
        "location": None,
    }


def run_global_search(
    keyword: str,
    entity_types: Optional[List[str]] = None,
    page: int = 0,
    size: int = 20,
) -> Tuple[int, int, int, List[Dict[str, Any]]]:
    keyword = (keyword or "").strip()
    if not keyword:
        return 0, page, size, []

    page = max(page, 0)
    size = max(min(size, 100), 1)
    indices = _indices_for_entity_types(entity_types)
    if not indices:
        return 0, page, size, []

    client = get_opensearch_client()
    query = {
        "multi_match": {
            "query": keyword,
            "fields": SEARCH_FIELDS,
            "type": "best_fields",
            "fuzziness": "AUTO",
        }
    }
    try:
        response = _multi_index_search(client, indices, query, page, size)
    except NotFoundError as exc:
        log_msg("warning", f"OpenSearch multi-index search 404 indices={indices}: {exc}")
        response = _msearch_indices(client, indices, query, page, size)

    hits = response.get("hits", {})
    total = hits.get("total", 0)
    total_hits = total.get("value", total) if isinstance(total, dict) else int(total or 0)
    results = [_map_hit_to_result(hit) for hit in hits.get("hits", [])]
    return total_hits, page, size, results


def _multi_index_search(
    client: OpenSearch,
    indices: List[str],
    query: Dict[str, Any],
    page: int,
    size: int,
) -> Dict[str, Any]:
    return client.search(
        index=indices,
        body={"from": page * size, "size": size, "query": query},
        ignore_unavailable=True,
        allow_no_indices=True,
    )


def _msearch_indices(
    client: OpenSearch,
    indices: List[str],
    query: Dict[str, Any],
    page: int,
    size: int,
) -> Dict[str, Any]:
    body: List[Dict[str, Any]] = []
    for index_name in indices:
        body.append({"index": index_name, "ignore_unavailable": True})
        body.append({"query": query, "from": 0, "size": size})

    try:
        response = client.msearch(body=body)
    except Exception as exc:
        log_msg("error", f"OpenSearch msearch failed indices={indices}: {exc}")
        return {"hits": {"total": {"value": 0}, "hits": []}}

    merged: List[Dict[str, Any]] = []
    for item in response.get("responses", []) or []:
        if item.get("error"):
            log_msg("warning", f"OpenSearch msearch shard error: {item.get('error')}")
            continue
        merged.extend((item.get("hits") or {}).get("hits") or [])

    merged.sort(key=lambda hit: hit.get("_score") or 0, reverse=True)
    start = page * size
    page_hits = merged[start:start + size]
    return {
        "hits": {
            "total": {"value": len(merged)},
            "hits": page_hits,
        }
    }

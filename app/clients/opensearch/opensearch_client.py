import os
import threading
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from opensearchpy import OpenSearch

load_dotenv()

_client_lock = threading.Lock()
_opensearch_client: Optional[OpenSearch] = None

DEFAULT_INDICES = {
    "USER": "user_index",
    "POST": "post_index",
    "PROPERTY": "property_index",
    "COMMENT": os.getenv("OPENSEARCH_COMMENT_INDEX", "comments_index"),
}

INDEX_TO_ENTITY = {
    "user_index": "USER",
    "post_index": "POST",
    "property_index": "PROPERTY",
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


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    if value is None:
        return None
    return value.strip().strip('"').strip("'")


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

        http_auth = (username, password) if username and password else None
        use_ssl = scheme == "https"

        _opensearch_client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_auth=http_auth,
            use_ssl=use_ssl,
            verify_certs=use_ssl,
            ssl_show_warn=False,
        )
        return _opensearch_client


def _indices_for_entity_types(entity_types: Optional[List[str]]) -> List[str]:
    if not entity_types:
        return list(dict.fromkeys(DEFAULT_INDICES.values()))

    indices: List[str] = []
    for entity_type in entity_types:
        index_name = DEFAULT_INDICES.get(entity_type.upper())
        if index_name and index_name not in indices:
            indices.append(index_name)
    return indices


def _location_from_source(source: Dict[str, Any]) -> Optional[str]:
    city = (source.get("city") or "").strip()
    state = (source.get("state") or "").strip()
    if city and state:
        return f"{city}, {state}"
    return city or state or source.get("location")


def _map_hit_to_result(hit: Dict[str, Any]) -> Dict[str, Any]:
    source = hit.get("_source", {}) or {}
    index_name = hit.get("_index", "")
    entity_type = INDEX_TO_ENTITY.get(index_name, "USER")

    if entity_type == "USER":
        first_name = source.get("firstName") or ""
        last_name = source.get("lastName") or ""
        title = (source.get("fullName") or f"{first_name} {last_name}").strip()
        return {
            "id": source.get("userCode") or source.get("id") or hit.get("_id", ""),
            "entityType": entity_type,
            "title": title or "User",
            "bio": source.get("role"),
            "description": source.get("bio"),
            "imageUrl": source.get("profilePhotoUrl"),
            "location": _location_from_source(source),
        }

    if entity_type == "POST":
        return {
            "id": source.get("postCode") or source.get("id") or hit.get("_id", ""),
            "entityType": entity_type,
            "title": source.get("title") or "Post",
            "bio": None,
            "description": source.get("content"),
            "imageUrl": source.get("thumbnailUrl"),
            "location": source.get("location"),
        }

    if entity_type == "PROPERTY":
        return {
            "id": source.get("propertyCode") or source.get("id") or hit.get("_id", ""),
            "entityType": entity_type,
            "title": source.get("title") or "Property",
            "bio": None,
            "description": source.get("description"),
            "imageUrl": source.get("thumbnailUrl"),
            "location": _location_from_source(source),
        }

    content = source.get("content") or ""
    return {
        "id": source.get("commentId") or source.get("id") or hit.get("_id", ""),
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
    body = {
        "from": page * size,
        "size": size,
        "query": {
            "multi_match": {
                "query": keyword,
                "fields": SEARCH_FIELDS,
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        },
    }

    response = client.search(index=indices, body=body)
    hits = response.get("hits", {})
    total = hits.get("total", 0)
    total_hits = total.get("value", total) if isinstance(total, dict) else int(total or 0)
    results = [_map_hit_to_result(hit) for hit in hits.get("hits", [])]
    return total_hits, page, size, results

"""
Create or update a Model Serving endpoint via REST API.

Free Edition UI often omits Compute scale-out and fails with
"Compute scale-out is required". Explicit workload_size in the API
payload is the community workaround.
"""

from __future__ import annotations

import json
from typing import Any

import requests


def get_api_context(dbutils: Any) -> tuple[str, str]:
    ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    return ctx.apiUrl().get(), ctx.apiToken().get()


def _headers(api_token: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}",
    }


def _workspace_host(api_root: str) -> str:
    return api_root.replace("https://", "").replace("http://", "").rstrip("/")


def build_served_entities_config(
    entity_name: str,
    entity_version: str,
    *,
    workload_size: str = "Small",
    scale_to_zero: bool = True,
) -> dict[str, Any]:
    return {
        "served_entities": [
            {
                "entity_name": entity_name,
                "entity_version": str(entity_version),
                "workload_size": workload_size,
                "scale_to_zero_enabled": scale_to_zero,
            }
        ]
    }


def build_served_models_config(
    entity_name: str,
    entity_version: str,
    *,
    workload_size: str = "Small",
    scale_to_zero: bool = True,
) -> dict[str, Any]:
    return {
        "served_models": [
            {
                "model_name": entity_name,
                "model_version": str(entity_version),
                "workload_size": workload_size,
                "scale_to_zero_enabled": scale_to_zero,
            }
        ]
    }


def endpoint_exists(api_root: str, headers: dict[str, str], endpoint_name: str) -> bool:
    resp = requests.get(f"{api_root}/api/2.0/serving-endpoints", headers=headers, timeout=60)
    resp.raise_for_status()
    endpoints = resp.json().get("endpoints", [])
    return any(item.get("name") == endpoint_name for item in endpoints)


def _post_endpoint(
    api_root: str, headers: dict[str, str], endpoint_name: str, config: dict[str, Any]
) -> requests.Response:
    return requests.post(
        f"{api_root}/api/2.0/serving-endpoints",
        headers=headers,
        json={"name": endpoint_name, "config": config},
        timeout=120,
    )


def _put_endpoint_config(
    api_root: str, headers: dict[str, str], endpoint_name: str, config: dict[str, Any]
) -> requests.Response:
    return requests.put(
        f"{api_root}/api/2.0/serving-endpoints/{endpoint_name}/config",
        headers=headers,
        json=config,
        timeout=120,
    )


def create_or_update_serving_endpoint(
    dbutils: Any,
    endpoint_name: str,
    entity_name: str,
    entity_version: str,
    *,
    workload_size: str = "Small",
    scale_to_zero: bool = True,
    model_uri: str | None = None,
) -> dict[str, Any]:
    """
    Create or update endpoint. Tries served_entities (UC) then served_models (legacy).
    Returns parsed JSON response and metadata for logging.
    """
    api_root, api_token = get_api_context(dbutils)
    headers = _headers(api_token)
    exists = endpoint_exists(api_root, headers, endpoint_name)

    configs = [
        ("served_entities", build_served_entities_config(
            entity_name, entity_version,
            workload_size=workload_size, scale_to_zero=scale_to_zero,
        )),
        ("served_models", build_served_models_config(
            entity_name, entity_version,
            workload_size=workload_size, scale_to_zero=scale_to_zero,
        )),
    ]

    last_response: requests.Response | None = None
    last_error: str | None = None

    for config_kind, config in configs:
        try:
            if exists:
                last_response = _put_endpoint_config(api_root, headers, endpoint_name, config)
            else:
                last_response = _post_endpoint(api_root, headers, endpoint_name, config)
            if last_response.ok:
                body = last_response.json() if last_response.text else {}
                return {
                    "ok": True,
                    "action": "update" if exists else "create",
                    "config_kind": config_kind,
                    "status_code": last_response.status_code,
                    "response": body,
                    "invocation_url": invocation_url(api_root, endpoint_name),
                }
            last_error = last_response.text
        except requests.RequestException as exc:
            last_error = str(exc)
            continue

    return {
        "ok": False,
        "action": "update" if exists else "create",
        "status_code": last_response.status_code if last_response else None,
        "error": last_error,
        "invocation_url": invocation_url(api_root, endpoint_name),
    }


def invocation_url(api_root: str, endpoint_name: str) -> str:
    return f"https://{_workspace_host(api_root)}/serving-endpoints/{endpoint_name}/invocations"


def print_deploy_result(result: dict[str, Any]) -> None:
    print(json.dumps(result, indent=2, default=str))
    if result.get("ok"):
        print(f"\nInvocation URL (for Worker secret):\n{result['invocation_url']}")
        print("\nWait until Serving UI shows Ready (cold start may take several minutes).")
    else:
        print("\nEndpoint API failed. Check error above or Serving UI build logs.")

"""Build the OpenAPI file the ZAP API scan reads.

ZAP's OpenAPI importer requests every operation once while it loads the file, before any
scope rule applies. A plain copy of the API's schema would therefore log the scan's own
session out, delete the fixture project and account, and leave every path parameter as a
literal placeholder that only reaches 404 and 422 answers. This script fetches the schema,
drops the operations that end a session or destroy data, and binds the fixture ids from
``fixtures.json`` into the paths, so the project routes are reached with real objects.

Run it after ``fixtures.py``::

    uv run python .github/dast/make_zap_spec.py dast-out

It writes ``<out dir>/zap/openapi.pruned.json`` and prints one status line.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

# (method, path template) pairs the scan must never send, for the same reasons as the
# operations disabled in schemathesis.toml.
DROPPED_OPERATIONS = frozenset(
    {
        ("post", "/api/v1/auth/logout"),
        ("post", "/api/v1/auth/refresh"),
        ("post", "/api/v1/auth/reset-password"),
        ("put", "/api/v1/users/me/password"),
        ("delete", "/api/v1/users/me"),
        ("delete", "/api/v1/users/me/photo"),
        ("post", "/api/v1/users/me/photo"),
        ("delete", "/api/v1/projects/{project_id}"),
        ("post", "/api/v1/projects/{project_id}/transfer-ownership"),
        ("delete", "/api/v1/projects/{project_id}/members/me"),
        ("delete", "/api/v1/projects/{project_id}/members/{user_id}"),
        ("delete", "/api/v1/projects/{project_id}/opinions"),
        ("delete", "/api/v1/projects/{project_id}/invitations/{invitation_id}"),
    }
)
BOUND_PARAMETERS = ("project_id", "user_id")


def prune_and_bind(spec: dict[str, Any], project_id: str, user_id: str) -> dict[str, Any]:
    """Drop the unsafe operations and replace the fixture path parameters with their ids.

    :param spec: The OpenAPI document as the API serves it
    :param project_id: Id of the fixture project of user A
    :param user_id: Id of fixture user A
    :return: The same document with the pruned and bound ``paths``
    """
    bound = {"project_id": project_id, "user_id": user_id}
    paths: dict[str, Any] = {}
    for path, item in spec["paths"].items():
        kept = {
            method: operation
            for method, operation in item.items()
            if (method, path) not in DROPPED_OPERATIONS
        }
        if not kept:
            continue
        new_path = path
        for name, value in bound.items():
            new_path = new_path.replace("{" + name + "}", value)
        if new_path != path:
            for operation in kept.values():
                operation["parameters"] = [
                    parameter
                    for parameter in operation.get("parameters", [])
                    if not (parameter["in"] == "path" and parameter["name"] in BOUND_PARAMETERS)
                ]
        paths[new_path] = {**paths.get(new_path, {}), **kept}
    spec["paths"] = paths
    return spec


def main() -> None:
    """Fetch the schema, prune and bind it, and write the file for ZAP."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_dir", type=Path, help="directory holding fixtures.json")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="where to fetch the schema")
    parser.add_argument(
        "--target", default="http://127.0.0.1:8000", help="server URL written into the file"
    )
    args = parser.parse_args()

    response = httpx.get(f"{args.api}/openapi.json", timeout=15)
    response.raise_for_status()
    fixtures = json.loads((args.out_dir / "fixtures.json").read_text())["users"]["A"]
    spec = prune_and_bind(response.json(), fixtures["project_id"], fixtures["user_id"])
    spec["servers"] = [{"url": args.target}]
    target = args.out_dir / "zap" / "openapi.pruned.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(spec, indent=1))
    operations = sum(
        1 for item in spec["paths"].values() for method in item if method != "parameters"
    )
    print(f"zap spec: {operations} operations kept")


if __name__ == "__main__":
    main()

"""Build the OpenAPI file the ZAP API scan reads.

ZAP's OpenAPI importer requests every operation once while it loads the file, before any
scope rule applies. A plain copy of the API's schema would therefore log the scan's own
session out, delete the fixture project and account, and leave every path parameter as a
literal placeholder that only reaches 404 and 422 answers. This script fetches the schema,
drops the operations that end a session or destroy data (the list is the one disabled in
``schemathesis.toml``), and binds the fixture ids from ``fixtures.json`` into the paths, so the
project routes are reached with real objects.

Run it after ``fixtures.py``::

    uv run python .github/dast/make_zap_spec.py dast-out

It writes ``<out dir>/zap/openapi.pruned.json`` and prints one status line.
"""

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any

import httpx

SCHEMATHESIS_CONFIG = Path(__file__).with_name("schemathesis.toml")
# The scan keeps this one, which schemathesis.toml disables: it sends logins with addresses it
# makes up, never those of the fixture users, so it cannot lock a fixture account.
KEPT_OPERATIONS = frozenset({("post", "/api/v1/auth/login")})
HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})
BOUND_PARAMETERS = ("project_id", "user_id")


def excluded_operations(config: Path = SCHEMATHESIS_CONFIG) -> frozenset[tuple[str, str]]:
    """Read the operations the scan must never send from the Schemathesis configuration.

    They are the operations ``schemathesis.toml`` disables, for the same reasons: they end a
    session, lock an account or destroy the data the rest of the run needs.

    :param config: The Schemathesis configuration file
    :return: Lower-case method and path template pairs, without the ones the scan keeps
    """
    operations = tomllib.loads(config.read_text())["operations"]
    pairs = (
        entry["include-name"].split(" ", 1) for entry in operations if entry.get("enabled") is False
    )
    return frozenset((method.lower(), path) for method, path in pairs) - KEPT_OPERATIONS


def prune_and_bind(
    spec: dict[str, Any], project_id: str, user_id: str, excluded: frozenset[tuple[str, str]]
) -> dict[str, Any]:
    """Drop the unsafe operations and replace the fixture path parameters with their ids.

    :param spec: The OpenAPI document as the API serves it
    :param project_id: Id of the fixture project of user A
    :param user_id: Id of fixture user A
    :param excluded: Method and path template pairs to drop, see :func:`excluded_operations`
    :return: The same document with the pruned and bound ``paths``
    """
    bound = {"project_id": project_id, "user_id": user_id}
    paths: dict[str, Any] = {}
    for path, item in spec["paths"].items():
        kept = {
            key: value
            for key, value in item.items()
            if key not in HTTP_METHODS or (key, path) not in excluded
        }
        if not HTTP_METHODS.intersection(kept):
            continue
        new_path = path
        for name, value in bound.items():
            new_path = new_path.replace("{" + name + "}", value)
        if new_path != path:
            for method in HTTP_METHODS.intersection(kept):
                kept[method]["parameters"] = [
                    parameter
                    for parameter in kept[method].get("parameters", [])
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
    spec = prune_and_bind(
        response.json(), fixtures["project_id"], fixtures["user_id"], excluded_operations()
    )
    spec["servers"] = [{"url": args.target}]
    target = args.out_dir / "zap" / "openapi.pruned.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(spec, indent=1))
    operations = sum(len(HTTP_METHODS.intersection(item)) for item in spec["paths"].values())
    print(f"zap spec: {operations} operations kept")


if __name__ == "__main__":
    main()

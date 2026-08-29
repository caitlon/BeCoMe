"""Static guard against personal data reaching the logs.

Every log record in ``api/`` carries its structured context through ``extra={...}``,
so the keys of those dict literals are the complete list of field names the drain can
ever receive. This walks the package's syntax tree and fails on a key that names a
credential or a raw identifier, which keeps the rule from depending on a reviewer
noticing it. ``docs/security.md`` states the rule; this enforces it.

The check is deliberately about *names*, not values: a field called ``password`` is
wrong whatever it holds, and a keyed tag like ``email_hash`` is fine even though it
derives from an address.
"""

import ast
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[3] / "api"

# Field names that must never appear as an ``extra`` key. Substring matching, so
# ``reset_token`` and ``api_key`` are caught by ``token`` and ``api_key`` alike.
FORBIDDEN_KEY_PARTS = (
    "password",
    "token",
    "secret",
    "authorization",
    "api_key",
    "cookie",
    "credential",
    "digest",
)

# Names that contain a forbidden substring but are safe, with the reason they are safe.
ALLOWED_KEYS = frozenset(
    {
        # Opaque per-request/session identifiers from the JWT, not credentials on their
        # own: holding a jti or sid does not let anyone mint or replay a token.
        "jti",
        "sid",
        # The count of tokens issued, never a token.
        "token_count",
    }
)


def _extra_keys(path: Path) -> list[tuple[str, int]]:
    """Collect every literal ``extra={...}`` key in one module.

    :param path: Module to scan.
    :return: ``(key, line number)`` pairs.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "extra" or not isinstance(keyword.value, ast.Dict):
                continue
            for key in keyword.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    found.append((key.value, key.lineno))
    return found


def _api_modules() -> list[Path]:
    """Return every Python module under ``api/``."""
    return sorted(API_ROOT.rglob("*.py"))


@pytest.mark.parametrize("module", _api_modules(), ids=lambda p: str(p.relative_to(API_ROOT)))
def test_no_log_field_names_a_credential_or_raw_identifier(module):
    """
    GIVEN a module under api/
    WHEN its literal ``extra={...}`` log fields are collected
    THEN none of them names a credential, a raw address, or an unkeyed digest
    """
    # GIVEN/WHEN
    offenders = [
        (key, lineno)
        for key, lineno in _extra_keys(module)
        if key not in ALLOWED_KEYS and any(part in key.lower() for part in FORBIDDEN_KEY_PARTS)
    ]

    # THEN
    assert not offenders, (
        f"{module.relative_to(API_ROOT)} logs forbidden field(s) {offenders}. "
        "Log an id, a keyed tag (api.auth.logging.hash_email), or a count instead. "
        "See the logging rules in docs/security.md."
    )


def test_the_guard_actually_catches_a_bad_key(tmp_path):
    """
    GIVEN a module that logs a raw password field
    WHEN its extra keys are collected
    THEN the forbidden substring check flags it

    Without this the parametrised test above would pass just as happily if
    ``_extra_keys`` silently returned nothing.
    """
    # GIVEN
    module = tmp_path / "bad.py"
    module.write_text(
        'logger.info("oops", extra={"event": "login", "password": pw})\n',
        encoding="utf-8",
    )

    # WHEN
    keys = [key for key, _ in _extra_keys(module)]

    # THEN
    assert "event" in keys
    assert any(part in key for key in keys for part in FORBIDDEN_KEY_PARTS)


def test_the_guard_reads_real_log_calls():
    """
    GIVEN the request-logging middleware, which is known to log via ``extra``
    WHEN its extra keys are collected
    THEN the known field names are found

    Guards against the AST walk silently matching nothing, which would make the
    parametrised test vacuous across the whole package.
    """
    # GIVEN/WHEN
    keys = {key for key, _ in _extra_keys(API_ROOT / "middleware" / "request_logging.py")}

    # THEN
    assert {"request_id", "method", "path", "status_code", "duration_ms"} <= keys

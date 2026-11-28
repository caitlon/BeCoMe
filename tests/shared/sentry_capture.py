"""An in-memory Sentry transport and the set-up that makes a test's ``init`` start fresh."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import sentry_sdk
import sentry_sdk.integrations as sentry_integrations
from sentry_sdk.transport import Transport

# Identifier of the SDK's Redis integration.
_REDIS = "redis"


class KeepEnvelopes(Transport):
    """A transport that keeps every envelope instead of sending it."""

    def __init__(self) -> None:
        super().__init__()
        self.envelopes: list[Any] = []

    def capture_envelope(self, envelope: Any) -> None:
        self.envelopes.append(envelope)

    def items(self, item_type: str) -> list[dict[str, Any]]:
        """Return the payloads of every envelope item of one type."""
        return [
            item.payload.json
            for envelope in self.envelopes
            for item in envelope.items
            if item.type == item_type
        ]

    def serialized(self) -> str:
        """Return every envelope payload as one string."""
        return json.dumps(
            [item.payload.json for envelope in self.envelopes for item in envelope.items],
            default=str,
        )


@contextmanager
def capturing_transport() -> Iterator[KeepEnvelopes]:
    """Yield the capturing transport, with the SDK set up as in a fresh process.

    The SDK records set-up integrations per process: an integration set up by an earlier
    ``init`` is kept by a later one, even when that ``init`` lists it in
    ``disabled_integrations``. A deployed process calls ``init`` once; a test worker calls
    it many times. So the Redis entry is taken out of both registries for the test, which
    makes ``init`` decide about it afresh, and the earlier state is put back afterwards. The
    client and the scopes are reset around the test too, and the client is left unset
    afterwards, not put back.
    """
    registries = (
        sentry_integrations._processed_integrations,
        sentry_integrations._installed_integrations,
    )
    earlier = [_REDIS in registry for registry in registries]
    for registry in registries:
        registry.discard(_REDIS)
    sentry_sdk.get_isolation_scope().clear()
    sentry_sdk.get_current_scope().clear()
    keep = KeepEnvelopes()
    try:
        yield keep
    finally:
        sentry_sdk.get_global_scope().set_client(None)
        sentry_sdk.get_isolation_scope().clear()
        sentry_sdk.get_current_scope().clear()
        for registry, was_there in zip(registries, earlier, strict=True):
            if was_there:
                registry.add(_REDIS)
            else:
                registry.discard(_REDIS)

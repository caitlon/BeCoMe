"""Every JSON request body a route accepts rejects unknown fields (extra='forbid').

The set of body models is derived from the routes rather than from a fixed list: every
model a route reads as its JSON body, including models nested inside it (the items of a
list, an optional member), found in the route's own dependency tree. A model that kept
``extra="ignore"`` would drop a forged field such as ``admin_id`` silently instead of
refusing the request.
"""

import typing
from collections.abc import Iterator

import pytest
from fastapi import params
from pydantic import BaseModel

from api.schemas.auth import ProjectDisposition
from api.schemas.calculation import ExpertInput
from api.schemas.opinion import OpinionCreate
from api.schemas.project import ProjectCreate
from tests.unit.api.route_table import api_routes, iter_dependants


def _models_in(annotation: object, seen: set[type[BaseModel]]) -> Iterator[type[BaseModel]]:
    """Yield every pydantic model named by a type annotation, at any depth.

    Unions, ``Annotated``, lists and mappings are opened up; a model is yielded and then
    searched through its own fields, so a model nested in a list inside a body is found.

    :param annotation: A type annotation as stored on a field.
    :param seen: Models already yielded, so a self-referencing model ends the walk.
    :return: Iterator over the models the annotation refers to.
    """
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if annotation in seen:
            return
        seen.add(annotation)
        yield annotation
        for field in annotation.model_fields.values():
            yield from _models_in(field.annotation, seen)
    elif typing.get_origin(annotation) is not None:
        for arg in typing.get_args(annotation):
            yield from _models_in(arg, seen)


def request_body_models() -> set[type[BaseModel]]:
    """Collect the models of every JSON request body in the application.

    Reads the body parameters of each route and of every dependency below it, because a
    body can be read by a dependency instead of the endpoint itself (the assistant chat
    does). Form and file parameters are not JSON bodies and are left out.

    :return: The body models, nested ones included.
    """
    found: set[type[BaseModel]] = set()
    for route in api_routes():
        for dependant in (route.dependant, *iter_dependants(route.dependant)):
            for field in dependant.body_params:
                if isinstance(field.field_info, params.Form | params.File):
                    continue
                found.update(_models_in(field.field_info.annotation, set()))
    return found


_BODY_MODELS = sorted(request_body_models(), key=lambda model: model.__name__)


def test_the_derivation_finds_the_known_bodies():
    """
    GIVEN the request bodies derived from the application's routes
    WHEN they are compared with models known to be bodies
    THEN top-level and nested ones are all found, so the check below is not vacuous

    ProjectCreate and OpinionCreate are read straight by an endpoint, ExpertInput sits
    inside a list in the calculate body, and ProjectDisposition inside a list in the
    account-deletion body.
    """
    # THEN
    assert {ProjectCreate, OpinionCreate, ExpertInput, ProjectDisposition} <= set(_BODY_MODELS)
    assert len(_BODY_MODELS) >= 10


@pytest.mark.parametrize("model", _BODY_MODELS, ids=lambda model: model.__name__)
def test_request_body_model_forbids_extra_fields(model):
    """
    GIVEN a model some route reads as its JSON request body
    WHEN its configuration is read
    THEN extra is "forbid", so a forged field is refused rather than dropped
    """
    # THEN
    assert model.model_config.get("extra") == "forbid"

from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import Union

from .protocol import (
    StartParams,
    RunParams,
    GoalsParams,
    PremisesParams,
    StateEqualParams,
    StateHashParams,
    SetWorkspaceParams,
    TocParams,
    AstParams,
    AstAtPosParams,
    GetStateAtPosParams,
    GetRootStateParams,
    ListNotationsInStatementParams,
)

from .response import (
    AstResponse,
    AstAtPosResponse,
    BaseResponse,
    CompleteGoalsResponse,
    GetRootStateResponse,
    GetStateAtPosResponse,
    GoalsResponse,
    ListNotationsInStatementResponse,
    PremisesResponse,
    RunResponse,
    SetWorkspaceResponse,
    StartResponse,
    StateEqualResponse,
    StateHashResponse,
    TocResponse,
)
Params = Union[
    ListNotationsInStatementParams,
    StartParams,
    GetStateAtPosParams,
    GetRootStateParams,
    RunParams,
    GoalsParams,
    PremisesParams,
    StateEqualParams,
    StateHashParams,
    SetWorkspaceParams,
    TocParams,
    AstParams,
    AstAtPosParams,
]

Responses = Union[
    AstResponse,
    AstAtPosResponse,
    BaseResponse,
    CompleteGoalsResponse,
    GetRootStateResponse,
    GetStateAtPosResponse,
    GoalsResponse,
    ListNotationsInStatementResponse,
    PremisesResponse,
    RunResponse,
    SetWorkspaceResponse,
    StartResponse,
    StateEqualResponse,
    StateHashResponse,
    TocResponse
]

@unique
class RouteName(StrEnum):
    START = "petanque/start"
    SET_WORKSPACE = "petanque/setWorkspace"
    RUN = "petanque/run"
    GOALS = "petanque/goals"
    # COMPLETE_GOALS = "petanque/goals"
    PREMISES = "petanque/premises"
    STATE_EQUAL= "petanque/state/eq"
    STATE_HASH = "petanque/state/hash"
    TOC = "petanque/toc"
    AST = "petanque/ast"
    AST_AT_POS = "petanque/ast_at_pos"
    GET_STATE_AT_POS = "petanque/get_state_at_pos"
    GET_ROOT_STATE = "petanque/get_root_state"
    LIST_NOTATIONS_IN_STATEMENTS = "petanque/list_notations_in_statement"

@dataclass(frozen=True)
class Route:
    params: Params
    response: Responses

PETANQUE_ROUTES: dict[RouteName, Route] = {
    RouteName.START: Route(StartParams, StartResponse),
    RouteName.SET_WORKSPACE: Route(SetWorkspaceParams, SetWorkspaceResponse),
    RouteName.RUN: Route(RunParams, RunResponse),
    RouteName.GOALS: Route(GoalsParams, GoalsResponse),
    # RouteName.COMPLETE_GOALS: Route(GoalsParams, CompleteGoalsResponse),
    RouteName.PREMISES: Route(PremisesParams, PremisesResponse),
    RouteName.STATE_EQUAL: Route(StateEqualParams, StateEqualResponse),
    RouteName.STATE_HASH: Route(StateHashParams, StateHashResponse),
    RouteName.TOC: Route(TocParams, TocResponse),
    RouteName.AST: Route(AstParams, AstResponse),
    RouteName.AST_AT_POS: Route(AstAtPosParams, AstAtPosResponse),
    RouteName.GET_STATE_AT_POS: Route(GetStateAtPosParams, GetStateAtPosResponse),
    RouteName.GET_ROOT_STATE: Route(GetRootStateParams, GetRootStateResponse),
    RouteName.LIST_NOTATIONS_IN_STATEMENTS: Route(ListNotationsInStatementParams, ListNotationsInStatementResponse)
}
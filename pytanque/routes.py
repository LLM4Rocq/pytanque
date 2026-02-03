from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import Union

from .protocol import (
    State,
    StartParams,
    StartResponse,
    RunParams,
    RunResponse,
    GoalsParams,
    GoalsResponse,
    PremisesParams,
    PremisesResponse,
    StateEqualParams,
    StateEqualResponse,
    StateHashParams,
    StateHashResponse,
    SetWorkspaceParams,
    SetWorkspaceResponse,
    TocParams,
    TocResponse,
    AstParams,
    AstResponse,
    AstAtPosParams,
    AstAtPosResponse,
    GetStateAtPosParams,
    GetStateAtPosResponse,
    GetRootStateParams,
    GetRootStateResponse,
    ListNotationsInStatementParams,
    ListNotationsInStatementResponse
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
class BaseRoute:
    params_cls: Params
    response_cls: Responses

    @staticmethod
    def extract_response(x: Responses):
        return x.value

@dataclass(frozen=True)
class InitialSessionRoute(BaseRoute):
    @staticmethod
    def extract_state(x: Responses) -> State:
        return State.from_json(x.to_json())

@dataclass(frozen=True)
class SessionRoute(BaseRoute):
    @staticmethod
    def extract_parent(x: Params) -> State:
        return x.st

@dataclass(frozen=True)
class UniversalRoute(BaseRoute):
    pass

@dataclass(frozen=True)
class GoalsRoute(BaseRoute):
    @staticmethod
    def extract_response(x: GoalsResponse):
        return x

@dataclass(frozen=True)
class ListNotationsInStatementRoute(BaseRoute):
    @staticmethod
    def extract_response(x:ListNotationsInStatementResponse):
        return x.st

Routes = Union[BaseRoute,
              InitialSessionRoute,
              SessionRoute,
              UniversalRoute,
              GoalsRoute,
              ListNotationsInStatementRoute
            ]

PETANQUE_ROUTES: dict[RouteName, Routes] = {
    RouteName.START: InitialSessionRoute(StartParams, StartResponse),
    RouteName.SET_WORKSPACE: UniversalRoute(SetWorkspaceParams, SetWorkspaceResponse),
    RouteName.RUN: SessionRoute(RunParams, RunResponse),
    RouteName.GOALS: GoalsRoute(GoalsParams, GoalsResponse),
    RouteName.PREMISES: BaseRoute(PremisesParams, PremisesResponse),
    RouteName.STATE_EQUAL: BaseRoute(StateEqualParams, StateEqualResponse),
    RouteName.STATE_HASH: BaseRoute(StateHashParams, StateHashResponse),
    RouteName.TOC: BaseRoute(TocParams, TocResponse),
    RouteName.AST: BaseRoute(AstParams, AstResponse),
    RouteName.AST_AT_POS: BaseRoute(AstAtPosParams, AstAtPosResponse),
    RouteName.GET_STATE_AT_POS: InitialSessionRoute(GetStateAtPosParams, GetStateAtPosResponse),
    RouteName.GET_ROOT_STATE: InitialSessionRoute(GetRootStateParams, GetRootStateResponse),
    RouteName.LIST_NOTATIONS_IN_STATEMENTS: ListNotationsInStatementRoute(ListNotationsInStatementParams, ListNotationsInStatementResponse)
}
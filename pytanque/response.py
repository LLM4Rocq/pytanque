from __future__ import annotations
from dataclasses import dataclass, field
from abc import abstractmethod, ABC
from typing import Any, Callable, Dict, List, NoReturn, Optional, Tuple, Union

from .protocol import (
    BaseAstResponse,
    BaseAstAtPosResponse,
    BaseGoalsResponse,
    BaseListNotationsInStatementResponse,
    BasePremisesResponse,
    BaseStateEqualResponse,
    BaseStateHashResponse,
    BaseTocResponse,
    Response,
    State
)

class BaseResponse(ABC):
    @classmethod
    def extract_response(cls, resp: Response):
        return cls.from_json(resp.result).value

    @classmethod
    @abstractmethod
    def from_json(cls, x: Response):
        pass

class AnyResponse:
    @classmethod
    def extract_response(cls, resp: Response) -> Any:
        return resp.result

class StartResponse(BaseResponse):
    @classmethod
    def extract_response(cls, resp: Response) -> State:
        return State.from_json(resp.result)

class SetWorkspaceResponse(BaseResponse):
    @classmethod
    def extract_response(cls, resp: Response) -> Any:
        return {}

class RunResponse(BaseResponse):
    @classmethod
    def extract_response(cls, resp: Response) -> State:
        return State.from_json(resp.result)

class GoalsResponse(BaseGoalsResponse, BaseResponse):
    @classmethod
    def extract_response(cls, resp: Response):
        if not resp.result:
            return []
        goals_resp = super().from_json(resp.result)
        return goals_resp.goals

class CompleteGoalsResponse(BaseGoalsResponse, BaseResponse):
    @classmethod
    def extract_response(cls, resp: Response):
        if not resp.result:
            return {}
        goals_resp = super().from_json(resp.result)
        return goals_resp

class PremisesResponse(BasePremisesResponse, BaseResponse):
    pass

class StateEqualResponse(BaseStateEqualResponse, BaseResponse):
    pass

class StateHashResponse(BaseStateHashResponse, BaseResponse):
    pass

class TocResponse(BaseTocResponse, BaseResponse):
    pass

class AstResponse(BaseAstResponse, BaseResponse):
    @classmethod
    def extract_response(cls, resp: Response):
        return resp.result["st"]

class AstAtPosResponse(BaseAstAtPosResponse, AnyResponse):
    pass

class GetStateAtPosResponse(BaseResponse):
    @classmethod
    def extract_response(cls, resp: Response):
        return State.from_json(resp.result)

class GetRootStateResponse(BaseResponse):
    @classmethod
    def extract_response(cls, resp: Response):
        return State.from_json(resp.result)

class ListNotationsInStatementResponse(BaseListNotationsInStatementResponse, BaseResponse):
    @classmethod
    def extract_response(cls, resp: Response):
        base = super().from_json(resp.result)
        return base.st
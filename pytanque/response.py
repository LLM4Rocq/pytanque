from __future__ import annotations
from dataclasses import dataclass, field
from abc import abstractmethod, ABC
from typing import Any, Callable, Dict, List, NoReturn, Optional, Tuple, Union


from .protocol import (
    BaseAstResponse,
    BaseAstAtPosResponse,
    BaseGetRootStateResponse,
    BaseGetStateAtPosResponse,
    BaseGoalsResponse,
    BaseListNotationsInStatementResponse,
    BasePremisesResponse,
    BaseRunResponse,
    BaseSetWorkspaceResponse,
    BaseStartResponse,
    BaseStateEqualResponse,
    BaseStateHashResponse,
    BaseTocResponse,
    Response,
    State
)

class BaseResponse(ABC):
    def extract_response(self):
        return self.value

    @classmethod
    @abstractmethod
    def from_json(cls, x: Response):
        pass

    @abstractmethod
    def to_json(cls, x: Response):
        pass

class AnyResponse(BaseResponse):
    pass

class SessionResponse(BaseResponse):
    def extract_response(self) -> State:
        return State.from_json(self.to_json())

class StartResponse(BaseStartResponse, SessionResponse):
    pass

class SetWorkspaceResponse(BaseSetWorkspaceResponse, AnyResponse):
    pass

class RunResponse(BaseRunResponse, SessionResponse):
    pass

class GoalsResponse(BaseGoalsResponse, BaseResponse):
    def extract_response(self) -> Any:
        return self

class PremisesResponse(BasePremisesResponse, BaseResponse):
    pass

class StateEqualResponse(BaseStateEqualResponse, BaseResponse):
    pass

class StateHashResponse(BaseStateHashResponse, BaseResponse):
    pass

class TocResponse(BaseTocResponse, BaseResponse):
    pass

class AstResponse(BaseAstResponse, BaseResponse):
    pass

class AstAtPosResponse(BaseAstAtPosResponse, AnyResponse):
    pass

class GetStateAtPosResponse(BaseGetStateAtPosResponse, SessionResponse):
    pass

class GetRootStateResponse(BaseGetRootStateResponse, SessionResponse):
    pass

class ListNotationsInStatementResponse(BaseListNotationsInStatementResponse, BaseResponse):
    def extract_response(self):
        return self.st
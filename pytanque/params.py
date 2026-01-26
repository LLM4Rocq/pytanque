from __future__ import annotations
from dataclasses import dataclass, field
from abc import abstractmethod, ABC
from typing import Any, Callable, Dict, List, NoReturn, Optional, Tuple, Union

from .protocol import (
    BaseAstAtPosParams,
    BaseAstParams,
    BaseGetRootStateParams,
    BaseGetStateAtPosParams,
    BaseGoalsParams,
    BaseListNotationsInStatementParams,
    BasePremisesParams,
    BaseRunParams,
    BaseSetWorkspaceParams,
    BaseStartParams,
    BaseStateEqualParams,
    BaseStateHashParams,
    BaseTocParams,
    State
)

class BaseParams:
    @classmethod
    @abstractmethod
    def from_json(cls, x):
        pass

    @abstractmethod
    def to_json(self):
        pass

class SessionParams(BaseParams):
    @abstractmethod
    def extract_parent(self) -> State:
        pass

class PrimitiveParams(BaseParams):
    pass

class UniversalParams(BaseParams):
    pass

class AstAtPosParams(BaseAstAtPosParams, BaseParams):
    pass

class AstParams(BaseAstParams, BaseParams):
    pass

class GetRootStateParams(BaseGetRootStateParams, PrimitiveParams):
    pass

class GoalsParams(BaseGoalsParams, BaseParams):
    pass

class GetStateAtPosParams(BaseGetStateAtPosParams, PrimitiveParams):
    pass

class ListNotationsInStatementParams(BaseListNotationsInStatementParams, BaseParams):
    pass

class PremisesParams(BasePremisesParams, BaseParams):
    pass

class RunParams(BaseRunParams, SessionParams):
    def extract_parent(self) -> State:
        return self.st

class SetWorkspaceParams(BaseSetWorkspaceParams, UniversalParams):
    pass

class StartParams(BaseStartParams, PrimitiveParams):
    pass

class StateEqualParams(BaseStateEqualParams, BaseParams):
    pass

class StateHashParams(BaseStateHashParams, BaseParams):
    pass

class TocParams(BaseTocParams, BaseParams):
    pass
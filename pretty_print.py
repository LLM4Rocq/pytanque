from typing import Any, Callable, TypeVar, Type


def pp_goal(self: Any) -> str:
    hyps = "\n".join(
        [
            f"{', '.join(h.names)} {':= ' + h.def_ if h.def_ else ''} : {h.ty}"
            for h in self.hyps
        ]
    )
    return f"{hyps}\n-----------------------------\n{self.ty}"


def pp_goals(self: Any) -> str:
    return "\n\n".join(map(lambda g: g.pp(), self.goals))


T = TypeVar("T")


def add_pp(pp: Callable[[T], None]) -> Callable[[Type[T]], Type[T]]:
    def class_decorator(cls: Type[T]) -> Type[T]:
        setattr(cls, "pp", pp)
        return cls

    return class_decorator

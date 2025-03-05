import socket
import json
import os
import pathlib
import logging
from typing import (
    Union,
    Any,
    Optional,
    Type,
    List,
)
from typing_extensions import Self
from types import TracebackType
from .protocol import (
    Request,
    Response,
    Failure,
    GetStateAtPosParams,
    GetRootStateParams,
    StartParams,
    Opts,
    RunParams,
    GoalsParams,
    PremisesParams,
    State,
    Goal,
    GoalsResponse,
    PremisesResponse,
    Inspect,
    InspectPhysical,
    InspectGoals,
    StateEqualParams,
    StateEqualResponse,
    StateHashParams,
    StateHashResponse,
    SetWorkspaceParams,
    TocParams,
    TocResponse,
)

Params = Union[
    StartParams,
    RunParams,
    GoalsParams,
    PremisesParams,
    StateEqualParams,
    StateHashParams,
    SetWorkspaceParams,
    TocParams,
]

logger = logging.getLogger(__name__)


class PetanqueError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message


inspectPhysical = Inspect(InspectPhysical())
inspectGoals = Inspect(InspectGoals())


def mk_request(id: int, params: Params) -> Request:
    match params:
        case GetStateAtPosParams():
            return Request(id, "petanque/get_state_at_pos", params.to_json())
        case GetRootStateParams():
            return Request(id, "petanque/get_root_state", params.to_json())
        case StartParams():
            return Request(id, "petanque/start", params.to_json())
        case RunParams():
            return Request(id, "petanque/run", params.to_json())
        case GoalsParams():
            return Request(id, "petanque/goals", params.to_json())
        case PremisesParams():
            return Request(id, "petanque/premises", params.to_json())
        case StateEqualParams():
            return Request(id, "petanque/state/eq", params.to_json())
        case StateHashParams():
            return Request(id, "petanque/state/hash", params.to_json())
        case SetWorkspaceParams():
            return Request(id, "petanque/setWorkspace", params.to_json())
        case TocParams():
            return Request(id, "petanque/toc", params.to_json())
        case _:
            raise PetanqueError(-32600, "Invalid request params")


def pp_goal(g: Goal) -> str:
    hyps = "\n".join(
        [
            f"{', '.join(h.names)} {':= ' + h.def_ if h.def_ else ''} : {h.ty}"
            for h in g.hyps
        ]
    )
    return f"{hyps}\n|-{g.ty}"


class Pytanque:
    """
    Petanque client to communicate with the Rocq theorem prover using JSON-RPC over a simple socket.
    """

    def __init__(self, host: str, port: int):
        """
        Open socket given the [host] and [port].
        """
        self.host = host
        self.port = port
        self.id = 0
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self) -> None:
        """
        Connect the socket to the server
        """
        self.socket.connect((self.host, self.port))
        logger.info(f"Connected to the socket")

    def close(self) -> None:
        """
        Close the socket
        """
        self.socket.close()
        logger.info(f"Socket closed")

    def __enter__(self) -> Self:
        self.connect()
        return self

    def query(self, params: Params, size: int = 4096) -> Response:
        """
        Send a query to the server using JSON-RPC protocol.
        """
        self.id += 1
        request = mk_request(self.id, params)
        payload = (json.dumps(request.to_json()) + "\n").encode()
        logger.info(f"Query Payload: {payload}")
        self.socket.sendall(payload)
        fragments = []
        while True:
            chunk = self.socket.recv(size)
            f = chunk.decode(errors="ignore")
            fragments.append(f)
            if f.endswith("\n"):
                break
        raw = "".join(fragments)
        try:
            logger.info(f"Query Response: {raw}")
            resp = Response.from_json_string(raw)
            if resp.id != self.id:
                raise PetanqueError(
                    -32603, f"Sent request {self.id}, got response {resp.id}"
                )
            return resp
        except ValueError:
            failure = Failure.from_json_string(raw)
            raise PetanqueError(failure.error.code, failure.error.message)

    def get_state_at_pos(
        self,
        file: str,
        point: tuple[int, int],
        opts: Optional[Opts] = None
    ) -> State:
        """
        Get the state at position `pos` in `file`.
        """
        path = os.path.abspath(file)
        uri = pathlib.Path(path).as_uri()
        row, col = point
        resp = self.query(GetStateAtPosParams(uri, row, col, opts))
        res = State.from_json(resp.result)
        logger.info(f"Get state at {(row, col)} in {uri} success")
        return res

    def get_root_state(
        self,
        file: str,
        opts: Optional[Opts] = None
    ) -> State:
        """
        Get the root state in `file`.
        """
        path = os.path.abspath(file)
        uri = pathlib.Path(path).as_uri()
        resp = self.query(GetRootStateParams(uri, opts))
        res = State.from_json(resp.result)
        logger.info(f"Get root state of {uri} success")
        return res

    def start(
        self,
        file: str,
        thm: str,
        pre_commands: Optional[str] = None,
        opts: Optional[Opts] = None,
    ) -> State:
        """
        Start the proof of [thm] defined in [file].
        """
        path = os.path.abspath(file)
        uri = pathlib.Path(path).as_uri()
        resp = self.query(StartParams(uri, thm, pre_commands, opts))
        res = State.from_json(resp.result)
        logger.info(f"Start success.")
        return res

    def set_workspace(
        self,
        debug: bool,
        dir: str,
    ):
        """
        Set the root directory.
        """
        path = os.path.abspath(dir)
        uri = pathlib.Path(path).as_uri()
        resp = self.query(SetWorkspaceParams(debug, uri))
        logger.info(f"Set workspace success.")

    def run_tac(
        self,
        state: State,
        tac: str,
        opts: Optional[Opts] = None,
        verbose: bool = False,
        timeout: Optional[int] = None,
    ) -> State:
        """
        Execute one tactic.
        """
        if timeout and tac.endswith("."):
            tac = f"Timeout {timeout} {tac}"
        resp = self.query(RunParams(state.st, tac, opts))
        res = State.from_json(resp.result)
        logger.info(f"Run tac {tac}.")
        if verbose:
            for i, g in enumerate(self.goals(res)):
                print(f"\nGoal {i}:\n{g.pp}\n")
        return res

    def goals(self, state: State, pretty: bool = True) -> List[Goal]:
        """
        Return the list of current goals.
        """
        resp = self.query(GoalsParams(state.st))
        if not resp.result:
            res = []
        else:
            res = GoalsResponse.from_json(resp.result).goals
        logger.info(f"Current goals: {res}")
        if pretty:
            for g in res:
                g.pp = pp_goal(g)
        return res

    def premises(self, state: State) -> Any:
        """
        Return the list of accessible premises.
        """
        resp = self.query(PremisesParams(state.st))
        res = PremisesResponse.from_json(resp.result)
        logger.info(f"Retrieved {len(res.value)} premises")
        return res.value

    def state_equal(self, st1: State, st2: State, kind: Inspect) -> Any:
        """
        Check if two states are equal.
        """
        resp = self.query(StateEqualParams(kind, st1.st, st2.st))
        res = StateEqualResponse.from_json(resp.result)
        logger.info(f"States equality {st1.st} = {st2.st} : {res.value}")
        return res.value

    def state_hash(self, state: State) -> Any:
        """
        Return the hash of a state.
        """
        resp = self.query(StateHashParams(state.st))
        res = StateHashResponse.from_json(resp.result)
        logger.info(f"States hash {state.st} = {res.value}")
        return res.value

    def toc(self, file: str) -> Any:
        """
        Return the TOC of a file.
        """
        path = os.path.abspath(file)
        uri = pathlib.Path(path).as_uri()
        resp = self.query(TocParams(uri))
        res = TocResponse.from_json(resp.result)
        logger.info(f"Retrieved TOC of {file}.")
        return res.value

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """
        Close the socket and exit.
        """
        self.close()

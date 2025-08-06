import socket
import json
import os
import pathlib
import logging
from typing import (
    Tuple,
    Union,
    Any,
    Optional,
    Type,

)
from typing_extensions import Self
from types import TracebackType
from .protocol import (
    Request,
    Response,
    Failure,
    Position,
    AstParams,
    AstAtPosParams,
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
    _atd_missing_json_field,
    _atd_bad_json
)

Params = Union[
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
]

logger = logging.getLogger(__name__)


class PetanqueError(Exception):
    """
    Exception raised for Petanque-specific errors.

    Parameters
    ----------
    code : int
        Error code from the Petanque server.
    message : str
        Error description from the server.

    Attributes
    ----------
    code : int
        Error code.
    message : str
        Error description.

    Examples
    --------
    >>> from pytanque import Pytanque, PetanqueError
    >>> try:
    ...     with Pytanque("127.0.0.1", 8765) as client:
    ...         state = client.start("./nonexistent.v", "theorem")
    ... except PetanqueError as e:
    ...     print(f"Petanque error {e.code}: {e.message}")
    """

    def __init__(self, code, message):
        self.code = code
        self.message = message


inspectPhysical = Inspect(InspectPhysical())
inspectGoals = Inspect(InspectGoals())


def mk_request(id: int, params: Params) -> Request:
    match params:
        case AstParams():
            return Request(id, "petanque/ast", params.to_json())
        case AstAtPosParams():
            return Request(id, "petanque/ast_at_pos", params.to_json())
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

    The Pytanque class provides a high-level interface for interactive theorem proving
    with Rocq/Coq through the Petanque server. It supports context manager protocol
    for automatic connection management.

    Parameters
    ----------
    host : str
        The hostname or IP address of the Petanque server.
    port : int
        The port number of the Petanque server.

    Attributes
    ----------
    host : str
        Server hostname.
    port : int
        Server port number.
    id : int
        Current request ID for JSON-RPC.
    socket : socket.socket
        TCP socket for server communication.

    Examples
    --------
    >>> from pytanque import Pytanque
    >>> with Pytanque("127.0.0.1", 8765) as client:
    ...     state = client.start("./examples/foo.v", "addnC")
    ...     state = client.run_tac(state, "induction n.", verbose=True)
    """

    def __init__(self, host: str, port: int):
        """
        Initialize a new Pytanque client instance.

        Parameters
        ----------
        host : str
            The hostname or IP address of the Petanque server.
        port : int
            The port number of the Petanque server.

        Examples
        --------
        >>> client = Pytanque("127.0.0.1", 8765)
        >>> client.connect()
        """
        self.host = host
        self.port = port
        self.id = 0
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self) -> None:
        """
        Establish connection to the Petanque server.

        Raises
        ------
        ConnectionError
            If connection to the server fails.
        OSError
            If socket creation fails.

        Examples
        --------
        >>> client = Pytanque("127.0.0.1", 8765)
        >>> client.connect()
        >>> client.close()
        """
        self.socket.connect((self.host, self.port))
        logger.info(f"Connected to the socket")

    def close(self) -> None:
        """
        Close the connection to the Petanque server.

        Examples
        --------
        >>> client = Pytanque("127.0.0.1", 8765)
        >>> client.connect()
        >>> client.close()
        """
        self.socket.close()
        logger.info(f"Socket closed")

    def __enter__(self) -> Self:
        self.connect()
        return self

    def query(self, params: Params, size: int = 4096) -> Response:
        """
        Send a low-level JSON-RPC query to the server.

        This is an internal method used by other high-level methods.
        Users should typically use the specific methods like start(), run_tac(), etc.

        Parameters
        ----------
        params : Params
            JSON-RPC parameters (one of StartParams, RunParams, GoalsParams, etc.).
        size : int, optional
            Buffer size for receiving response, by default 4096.

        Returns
        -------
        Response
            JSON-RPC response object containing the result.

        Raises
        ------
        PetanqueError
            If the query fails or the server returns an error.
        ValueError
            If the response format is invalid.

        Examples
        --------
        >>> from pytanque.protocol import StartParams
        >>> client = Pytanque("127.0.0.1", 8765)
        >>> client.connect()
        >>> params = StartParams("file:///path/to/file.v", "theorem_name")
        >>> response = client.query(params)
        >>> client.close()
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

    def ast(
        self,
        state: State,
        text: str
    ) -> dict:
        """
        Get the AST corresponding to `text` for the `state`.
        """
        resp = self.query(AstParams(state.st, text))
        res = resp.result["st"]
        logger.info(f"AST of {text}")
        return res

    def ast_at_pos(
        self,
        file: str,
        line: int,
        character: int,
        offset: int
    ) -> dict:
        """
        Get the AST at a certain position `line`, `character` and `offset` in `file`.
        """
        path = os.path.abspath(file)
        uri = pathlib.Path(path).as_uri()
        pos = Position(line, character, offset)
        resp = self.query(AstAtPosParams(uri, pos))
        res = resp.result["st"]
        logger.info(f"AST at {pos.to_json_string()} in {uri}")
        return res

    def get_state_at_pos(
        self,
        file: str,
        line: int,
        character: int,
        offset: int,
        opts: Optional[Opts] = None
    ) -> State:
        """
        Get the state at position `line`, `character` and `offset` in `file`.
        """
        path = os.path.abspath(file)
        uri = pathlib.Path(path).as_uri()
        pos = Position(line, character, offset)
        resp = self.query(GetStateAtPosParams(uri, pos, opts))
        res = State.from_json(resp.result)
        logger.info(f"Get state at {pos.to_json_string()} in {uri} success")
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
        Start a proof session for a specific theorem in a Coq/Rocq file.

        Parameters
        ----------
        file : str
            Path to the Coq/Rocq file containing the theorem.
        thm : str
            Name of the theorem to prove.
        pre_commands : str, optional
            Commands to execute before starting the proof, by default None.
        opts : Opts, optional
            Options for proof state management (memo and hash settings), by default None.

        Returns
        -------
        State
            The initial proof state containing:
            - st : int - State identifier
            - proof_finished : bool - Whether the proof is complete
            - hash : int, optional - Hash of the state

        Raises
        ------
        PetanqueError
            If theorem is not found or file cannot be loaded.
        ValueError
            If file path is invalid.

        Examples
        --------
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     state = client.start("./examples/foo.v", "addnC")
        ...     print(f"Initial state: {state.st}, finished: {state.proof_finished}")
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
        Set the root directory for the Coq/Rocq workspace.

        Parameters
        ----------
        debug : bool
            Enable debug mode for the workspace.
        dir : str
            Path to the workspace root directory.

        Raises
        ------
        PetanqueError
            If directory is invalid or inaccessible.

        Examples
        --------
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     client.set_workspace(debug=False, dir="./examples/")
        """
        path = os.path.abspath(dir)
        uri = pathlib.Path(path).as_uri()
        resp = self.query(SetWorkspaceParams(debug, uri))
        logger.info(f"Set workspace success.")

    def run(
        self,
        state: State,
        cmd: str,
        opts: Optional[Opts] = None,
        verbose: bool = False,
        timeout: Optional[int] = None,
    ) -> State:
        """
        Execute a tactic on the current proof state.

        Parameters
        ----------
        state : State
            The current proof state.
        cmd : str
            The tactic to execute (e.g., "induction n.", "auto.", "lia.").
        opts : Opts, optional
            Options for proof state management, by default None.
        verbose : bool, optional
            Whether to print goals after tactic execution, by default False.
        timeout : int, optional
            Timeout in seconds for tactic execution, by default None.

        Returns
        -------
        State
            The new proof state after tactic execution.

        Raises
        ------
        PetanqueError
            If tactic execution fails.
        TimeoutError
            If tactic execution exceeds timeout.

        Examples
        --------
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     state = client.start("./examples/foo.v", "addnC")
        ...     # Execute induction tactic with verbose output
        ...     state = client.run_tac(state, "induction n.", verbose=True)
        ...     # Execute with timeout
        ...     state = client.run_tac(state, "auto.", timeout=5)
        """
        if timeout and cmd.endswith("."):
            cmd = f"Timeout {timeout} {cmd}"
        resp = self.query(RunParams(state.st, cmd, opts))
        res = State.from_json(resp.result)
        logger.info(f"Run command {cmd}.")
        if verbose:
            for i, g in enumerate(self.goals(res)):
                print(f"\nGoal {i}:\n{g.pp}\n")
        return res

    def goals(self, state: State, pretty: bool = True) -> list[Goal]:
        """
        Retrieve the current goals for a proof state.

        Parameters
        ----------
        state : State
            The proof state to query.
        pretty : bool, optional
            Whether to add pretty-printed representation to goals, by default True.

        Returns
        -------
        list[Goal]
            List of current goals. Each Goal contains:
            - info : Any - Goal metadata
            - hyps : list[GoalHyp] - List of hypotheses
            - ty : str - Goal type
            - pp : str, optional - Pretty-printed representation (if pretty=True)

        Raises
        ------
        PetanqueError
            If state is invalid.

        Examples
        --------
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     state = client.start("./examples/foo.v", "addnC")
        ...     goals = client.goals(state)
        ...     print(f"Number of goals: {len(goals)}")
        ...     for i, goal in enumerate(goals):
        ...         print(f"Goal {i}: {goal.pp}")
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
        Get the list of accessible premises (lemmas, definitions) for the current state.

        Parameters
        ----------
        state : State
            The proof state to query.

        Returns
        -------
        Any
            List of accessible premises/lemmas for the current proof state.

        Raises
        ------
        PetanqueError
            If state is invalid.

        Examples
        --------
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     state = client.start("./examples/foo.v", "addnC")
        ...     premises = client.premises(state)
        ...     print(f"Available premises: {len(premises)}")
        """
        resp = self.query(PremisesParams(state.st))
        res = PremisesResponse.from_json(resp.result)
        logger.info(f"Retrieved {len(res.value)} premises")
        return res.value

    def state_equal(self, st1: State, st2: State, kind: Optional[Inspect] = None) -> bool:
        """
        Compare two proof states for equality.

        Parameters
        ----------
        st1 : State
            First state to compare.
        st2 : State
            Second state to compare.
        kind : Inspect
            Type of comparison (InspectPhysical or InspectGoals).

        Returns
        -------
        bool
            True if states are equal according to the specified comparison type.

        Raises
        ------
        PetanqueError
            If states are invalid.

        Examples
        --------
        >>> from pytanque import Pytanque, inspectPhysical, inspectGoals
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     state1 = client.start("./examples/foo.v", "addnC")
        ...     state2 = client.run_tac(state1, "induction n.")
        ...     # Compare physical state
        ...     physical_equal = client.state_equal(state1, state2, inspectPhysical)
        ...     # Compare goal structure
        ...     goals_equal = client.state_equal(state1, state2, inspectGoals)
        """
        resp = self.query(StateEqualParams(kind, st1.st, st2.st))
        res = StateEqualResponse.from_json(resp.result)
        logger.info(f"States equality {st1.st} = {st2.st} : {res.value}")
        return res.value

    def state_hash(self, state: State) -> int:
        """
        Get a hash value for a proof state.

        Parameters
        ----------
        state : State
            The state to hash.

        Returns
        -------
        int
            Hash value of the state.

        Raises
        ------
        PetanqueError
            If state is invalid.

        Examples
        --------
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     state = client.start("./examples/foo.v", "addnC")
        ...     hash_value = client.state_hash(state)
        ...     print(f"State hash: {hash_value}")
        """
        resp = self.query(StateHashParams(state.st))
        res = StateHashResponse.from_json(resp.result)
        logger.info(f"States hash {state.st} = {res.value}")
        return res.value

    def toc(self, file: str) -> list[tuple[str, Any]]:
        """
        Get the table of contents (available definitions and theorems) for a Coq/Rocq file.

        Parameters
        ----------
        file : str
            Path to the Coq/Rocq file.

        Returns
        -------
        list[tuple[str, Any]]
            list of (name, definition) pairs representing available definitions and theorems.

        Raises
        ------
        PetanqueError
            If file cannot be loaded.
        ValueError
            If file path is invalid.

        Examples
        --------
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     toc = client.toc("./examples/foo.v")
        ...     print("Available definitions:")
        ...     for name, definition in toc:
        ...         print(f"  {name}")
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
        Context manager exit method that automatically closes the connection.

        Parameters
        ----------
        exc_type : Optional[Type[BaseException]]
            Exception type if an exception occurred.
        exc_val : Optional[BaseException]
            Exception value if an exception occurred.
        exc_tb : Optional[TracebackType]
            Exception traceback if an exception occurred.

        Examples
        --------
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     # Connection is automatically managed
        ...     state = client.start("./examples/foo.v", "addnC")
        ... # Connection is automatically closed here
        """
        self.close()

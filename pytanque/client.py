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
    AstParams,
    AstAtPosParams
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


InspectPhysical = Inspect(InspectPhysical())
InspectGoals = Inspect(InspectGoals())


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

    Key features include:
    - Execute tactics and commands with the run() method
    - Access proof states with feedback containing all Rocq messages
    - Parse AST of commands with ast() and ast_at_pos()
    - Navigate file positions with get_state_at_pos() and get_root_state()
    - Inspect goals, premises, and proof state information

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
    ...     # Start a proof
    ...     state = client.start("./examples/foo.v", "addnC")
    ...     
    ...     # Execute commands and check feedback
    ...     state = client.run(state, "induction n.", verbose=True)
    ...     for level, msg in state.feedback:
    ...         print(f"Rocq message: {msg}")
    ...     
    ...     # Get AST of a command
    ...     ast = client.ast(state, "auto")
    ...     print("AST:", ast)
    ...     
    ...     # Get state at specific position in file
    ...     pos_state = client.get_state_at_pos("./examples/foo.v", line=3, character=0, offset=80)
    ...     print(f"State at position: {pos_state.st}")
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
        Get the Abstract Syntax Tree (AST) of a command parsed at a given state.

        Parameters
        ----------
        state : State
            The proof state providing the parsing context.
        text : str
            The command text to parse (e.g., "induction n", "Search nat").

        Returns
        -------
        dict
            The AST representation of the parsed command.

        Raises
        ------
        PetanqueError
            If the text cannot be parsed in the given state context.

        Examples
        --------
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     state = client.start("./examples/foo.v", "addnC")
        ...     
        ...     # Get AST for a tactic
        ...     ast = client.ast(state, "induction n.")
        ...     print("Tactic AST:", ast)
        ...     
        ...     # Get AST for a search command
        ...     ast = client.ast(state, "Search nat.")
        ...     print("Search AST:", ast)
        ...     
        ...     # Get AST for a complex expression
        ...     ast = client.ast(state, "fun x => x + 1.")
        ...     print("Expression AST:", ast)
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
        Get the Abstract Syntax Tree (AST) at a specific position in a file.

        Parameters
        ----------
        file : str
            Path to the Rocq/Coq file.
        line : int
            Line number (0-based indexing).
        character : int
            Character position within the line (0-based indexing).
        offset : int
            Byte offset from the beginning of the file.

        Returns
        -------
        dict
            The AST representation of the syntax element at the specified position.

        Raises
        ------
        PetanqueError
            If the position is invalid or the file cannot be parsed.
        ValueError
            If the file path is invalid.

        Examples
        --------
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     # Get AST at specific position in file
        ...     ast = client.ast_at_pos("./examples/foo.v", line=5, character=10, offset=150)
        ...     print("AST at position:", ast)
        ...     
        ...     # Get AST at theorem declaration
        ...     ast = client.ast_at_pos("./examples/foo.v", line=0, character=0, offset=0)
        ...     print("Theorem declaration AST:", ast)
        ...     
        ...     # Get AST at proof step
        ...     ast = client.ast_at_pos("./examples/foo.v", line=3, character=5, offset=80)
        ...     print("Proof step AST:", ast)
        """
        path = os.path.abspath(file)
        uri = pathlib.Path(path).as_uri()
        pos = Position(line, character, offset)
        resp = self.query(AstAtPosParams(uri, pos))
        res = resp.result
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
        Get the proof state at a specific position in a file.

        This method returns the proof state that would be active at the specified
        position, allowing you to inspect the context, goals, and available tactics
        at any point in a proof script.

        Parameters
        ----------
        file : str
            Path to the Rocq/Coq file.
        line : int
            Line number (0-based indexing).
        character : int
            Character position within the line (0-based indexing).
        offset : int
            Byte offset from the beginning of the file.
        opts : Opts, optional
            Options for proof state management, by default None.

        Returns
        -------
        State
            The proof state at the specified position, including:
            - st : int - State identifier
            - proof_finished : bool - Whether proof is complete at this point
            - feedback : List[Tuple[int, str]] - Messages from Rocq up to this point
            - hash : int, optional - State hash

        Raises
        ------
        PetanqueError
            If the position is invalid or the file cannot be processed.
        ValueError
            If the file path is invalid.

        Examples
        --------
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     # Get state at beginning of proof
        ...     state = client.get_state_at_pos("./examples/foo.v", line=2, character=0, offset=50)
        ...     print(f"State at start: {state.st}, finished: {state.proof_finished}")
        ...     
        ...     # Get state in middle of proof
        ...     state = client.get_state_at_pos("./examples/foo.v", line=5, character=10, offset=120)
        ...     goals = client.goals(state)
        ...     print(f"Goals at position: {len(goals)}")
        ...     
        ...     # Get state at end of proof
        ...     state = client.get_state_at_pos("./examples/foo.v", line=8, character=5, offset=200)
        ...     print(f"Proof finished: {state.proof_finished}")
        ...     
        ...     # Check feedback at specific position
        ...     for level, msg in state.feedback:
        ...         print(f"Feedback level {level}: {msg}")
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
        Get the initial (root) state of a document.

        This method returns the very first state of the document, before any
        commands or proofs have been executed. It represents the initial
        environment with all imports and definitions loaded.

        Parameters
        ----------
        file : str
            Path to the Rocq/Coq file.
        opts : Opts, optional
            Options for proof state management, by default None.

        Returns
        -------
        State
            The root state of the document, including:
            - st : int - State identifier for the initial state
            - proof_finished : bool - Always False for root state
            - feedback : List[Tuple[int, str]] - Initial messages (imports, etc.)
            - hash : int, optional - State hash

        Raises
        ------
        PetanqueError
            If the file cannot be loaded or processed.
        ValueError
            If the file path is invalid.

        Examples
        --------
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     # Get the root state of a file
        ...     root_state = client.get_root_state("./examples/foo.v")
        ...     print(f"Root state: {root_state.st}")
        ...     print(f"Proof finished: {root_state.proof_finished}")  # Always False
        ...     
        ...     # Check what's available in the initial environment
        ...     premises = client.premises(root_state)
        ...     print(f"Available in root context: {len(premises)} premises")
        ...     
        ...     # Compare with state at specific position
        ...     pos_state = client.get_state_at_pos("./examples/foo.v", line=3, character=0, offset=80)
        ...     print(f"Root state: {root_state.st}, Position state: {pos_state.st}")
        ...     
        ...     # Check initial feedback
        ...     for level, msg in root_state.feedback:
        ...         print(f"Initial feedback level {level}: {msg}")
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
        Execute a command on the current proof state.

        This method replaces run_tac and supports both tactics and other Rocq commands
        like Search, Print, Check, etc. The returned state includes feedback containing
        all messages from Rocq (errors, warnings, search results, etc.).

        Parameters
        ----------
        state : State
            The current proof state.
        cmd : str
            The command to execute. Can be:
            - Tactics: "induction n.", "auto.", "lia."
            - Search commands: "Search nat.", "SearchPattern (_ + _)."
            - Print commands: "Print list.", "Print Assumptions."
            - Check commands: "Check (fun x => x)."
        opts : Opts, optional
            Options for proof state management, by default None.
        verbose : bool, optional
            Whether to print goals after command execution, by default False.
        timeout : int, optional
            Timeout in seconds for command execution, by default None.

        Returns
        -------
        State
            The new proof state after command execution.
            The state.feedback field contains a list of (level, message) tuples with
            all messages from Rocq including errors, warnings, and command outputs.

        Raises
        ------
        PetanqueError
            If command execution fails.
        TimeoutError
            If command execution exceeds timeout.

        Examples
        --------
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     state = client.start("./examples/foo.v", "addnC")
        ...     
        ...     # Execute tactic
        ...     state = client.run(state, "induction n.", verbose=True)
        ...     
        ...     # Execute search command and check feedback
        ...     state = client.run(state, "Search nat.")
        ...     for level, msg in state.feedback:
        ...         print(f"Level {level}: {msg}")
        ...     
        ...     # Execute print command
        ...     state = client.run(state, "Print list.")
        ...     print("Print output in feedback:", state.feedback)
        ...     
        ...     # Execute check command
        ...     state = client.run(state, "Check (1 + 1).")
        ...     
        ...     # Execute with timeout
        ...     state = client.run(state, "auto.", timeout=5)
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
        >>> from pytanque import Pytanque, InspectPhysical, InspectGoals
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     state1 = client.start("./examples/foo.v", "addnC")
        ...     state2 = client.run(state1, "induction n.")
        ...     # Compare physical state
        ...     physical_equal = client.state_equal(state1, state2, InspectPhysical)
        ...     # Compare goal structure
        ...     goals_equal = client.state_equal(state1, state2, InspectGoals)
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

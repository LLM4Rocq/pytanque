from __future__ import annotations
import socket
import json
import os
import pathlib
import logging
import subprocess
from dataclasses import fields
from enum import StrEnum
import functools

from typing import (
    Tuple,
    Union,
    List,
    Any,
    Optional,
    Type,
)
import requests
from typing_extensions import Self
from types import TracebackType
from .protocol import (
    Request,
    Response,
    Failure,
    Position,
    StartParams,
    Opts,
    RunParams,
    GoalsParams,
    PremisesParams,
    State,
    Goal,
    Inspect,
    InspectPhysical,
    InspectGoals,
    StateEqualParams,
    StateHashParams,
    SetWorkspaceParams,
    TocParams,
    TocElement,
    AstParams,
    AstAtPosParams,
    GetStateAtPosParams,
    GetRootStateParams,
    ListNotationsParams,
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
    ListNotationsParams,
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


def mk_request(id: int, params: Params, route: str, project_state=True) -> Request:
    # TODO: update petanque to remove project_state?
    params_json = params.to_json()
    if project_state:
        for f in fields(params):
            value = getattr(params, f.name)
            if isinstance(value, State):
                params_json[f.name] = params_json[f.name]['st']
    return Request(id, route, params_json)

def send_request(route: str, response_cls:BaseResponse, is_session=False, continues_session=False):
    """
    Send the return parameters to `mk_request` through the given route.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(self: Pytanque, *args, **kwargs):
            params = fn(self, *args, **kwargs)
            res = self.query(params, route)
            return response_cls.extract_response(res)
        wrapper.__send_request__ = route
        wrapper.__is_session__ = is_session
        wrapper.__continues_session = continues_session
        if continues_session and not is_session:
            raise PetanqueError(f"is_session is set to False in the send_request decorator for {fn.__name__},\
                                 while continue_session is set to True.")
        return wrapper
    return decorator

def pp_goal(g: Goal) -> str:
    hyps = "\n".join(
        [
            f"{', '.join(h.names)} {':= ' + h.def_ if h.def_ else ''} : {h.ty}"
            for h in g.hyps
        ]
    )
    return f"{hyps}\n|-{g.ty}"

class PytanqueMode(StrEnum):
    STDIO = 'stdio'
    SOCKET = 'socket'
    HTTP = 'http'


class Pytanque:
    """
    Petanque client to communicate with the Rocq theorem prover using JSON-RPC over a socket or subprocess.

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
    host : str, optional
        The hostname or IP address of the Petanque server (for socket mode).
    port : int, optional
        The port number of the Petanque server (for socket mode).
    use_subprocess : bool, optional
        Whether to use subprocess mode with "pet" command, by default False.

    Attributes
    ----------
    host : str
        Server hostname (socket mode only).
    port : int
        Server port number (socket mode only).
    id : int
        Current request ID for JSON-RPC.
    socket : socket.socket
        TCP socket for server communication (socket mode only).
    process : subprocess.Popen
        Subprocess handle (subprocess mode only).
    mode : str
        Communication mode: "socket" or "subprocess".

    Examples
    --------
    Socket mode:
    >>> from pytanque import Pytanque
    >>> with Pytanque("127.0.0.1", 8765) as client:
    ...     state = client.start("./examples/foo.v", "addnC")

    Stdio mode:
    >>> with Pytanque(stdio=True) as client:
    ...     state = client.start("./examples/foo.v", "addnC")
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        stdio: bool = False,
        mode: PytanqueMode = PytanqueMode.SOCKET
    ):
        """
        Initialize a new Pytanque client instance.

        Parameters
        ----------
        host : str, optional
            The hostname or IP address of the Petanque server (for socket mode).
        port : int, optional
            The port number of the Petanque server (for socket mode).
        stdio : bool, optional
            Whether to use stdio mode with "pet" command, by default False.

        Examples
        --------
        Socket mode:
        >>> client = Pytanque("127.0.0.1", 8765)
        >>> client.connect()

        Stdio mode:
        >>> client = Pytanque(stdio=True)
        >>> client.connect()
        """
        if stdio or mode == PytanqueMode.STDIO:
            self.mode = PytanqueMode.STDIO
            self.process = None
            self.host = None
            self.port = None
            self.socket = None
        elif mode == PytanqueMode.SOCKET:
            self.mode = PytanqueMode.SOCKET
            self.host = host
            self.port = port
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.process = None
        elif mode == PytanqueMode.HTTP:
            self.mode = PytanqueMode.HTTP
            self.host = None
            self.port = None
            self.socket = None
            self.process = None
        else:
            raise ValueError(
                "Must specify either (host, port) for socket mode or stdio=True for stdio mode"
            )

        self.id = 0

    def connect(self) -> None:
        """
        Establish connection to the Petanque server or spawn subprocess.

        Raises
        ------
        ConnectionError
            If connection to the server fails (socket mode).
        OSError
            If socket creation fails or subprocess spawning fails.

        Examples
        --------
        Socket mode:
        >>> client = Pytanque("127.0.0.1", 8765)
        >>> client.connect()
        >>> client.close()

        Stdio mode:
        >>> client = Pytanque(stdio=True)
        >>> client.connect()
        >>> client.close()
        """
        if self.mode == PytanqueMode.SOCKET:
            self.socket.connect((self.host, self.port))
            logger.info(f"Connected to the socket")
        elif self.mode == PytanqueMode.STDIO:
            self.process = subprocess.Popen(
                ["pet"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
            )
            logger.info(f"Spawned pet subprocess")
        elif self.mode == PytanqueMode.HTTP:
            logger.info("No connection required for HTTP mode.")

    def close(self) -> None:
        """
        Close the connection to the Petanque server or terminate subprocess.

        Examples
        --------
        Socket mode:
        >>> client = Pytanque("127.0.0.1", 8765)
        >>> client.connect()
        >>> client.close()

        Stdio mode:
        >>> client = Pytanque(stdio=True)
        >>> client.connect()
        >>> client.close()
        """
        if self.mode == PytanqueMode.SOCKET:
            self.socket.close()
            logger.info(f"Socket closed")
        elif self.mode == PytanqueMode.STDIO:
            if self.process:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
                logger.info(f"Pet subprocess terminated")
        elif self.mode == PytanqueMode.HTTP:
            logger.info("No closing process required for HTTP mode.")

    def __enter__(self) -> Self:
        self.connect()
        return self

    def _read_socket_response(self, size: int) -> str:
        fragments = []
        while True:
            chunk = self.socket.recv(size)
            f = chunk.decode(errors="ignore")
            fragments.append(f)
            if f.endswith("\n"):
                break
        return "".join(fragments)

    def _send_request_message(self, payload: Any) -> None:
        url = f"http://{self.host}:{self.port}"
        response = requests.post(
            url,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        try:
            _ = response.json()
        except json.JSONDecodeError as e:
            raise PetanqueError(
                -32700, f"Invalid JSON response: {response.text}"
            ) from e
        return response.text

    def _send_lsp_message(self, json_payload: str) -> None:
        """Send a JSON-RPC message using LSP format (Content-Length header + JSON)."""
        content_length = len(json_payload.encode("utf-8"))
        lsp_message = f"Content-Length: {content_length}\r\n\r\n{json_payload}"

        logger.info(f"Sending LSP message: {json_payload.strip()}")
        self.process.stdin.write(lsp_message.encode("utf-8"))
        self.process.stdin.flush()

    def _read_lsp_response(self) -> str:
        """Read a JSON-RPC response using LSP format, skipping notifications."""
        while True:
            # Read Content-Length header
            header_line = self.process.stdout.readline().decode("utf-8")
            if not header_line:
                raise PetanqueError(-32603, "No response from pet process")

            if not header_line.startswith("Content-Length:"):
                continue  # Skip other headers or empty lines

            # Parse content length and read JSON content
            content_length = int(header_line.split(":")[1].strip())
            self.process.stdout.readline()  # Skip empty line separator

            # Read exact number of bytes and decode to UTF-8
            json_bytes = self.process.stdout.read(content_length)
            json_content = json_bytes.decode("utf-8")
            logger.info(f"Received LSP message: {json_content.strip()}")

            try:
                response_data = json.loads(json_content)
            except json.JSONDecodeError as e:
                raise PetanqueError(
                    -32700, f"Invalid JSON response: {json_content}"
                ) from e

            # Skip notifications (messages without matching request id)
            if "id" not in response_data:
                logger.info(f"Skipping notification: {response_data}")
                continue

            return json_content

    def query(self, params: Params, route: str, size: int = 4096) -> Response:
        """
        Send a low-level JSON-RPC query to the server or subprocess.

        This is an internal method used by other high-level methods.
        Users should typically use the specific methods like start(), run_tac(), etc.

        Parameters
        ----------
        params : Params
            JSON-RPC parameters (one of StartParams, RunParams, GoalsParams, etc.).
        size : int, optional
            Buffer size for receiving response, by default 4096 (socket mode only).

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
        project_state = (self.mode != PytanqueMode.HTTP)
        # TODO: Maybe update petanque so that it takes whole state as input instead of state.st
        request = mk_request(self.id, params, route, project_state=project_state)
        payload = json.dumps(request.to_json()) + "\n"
        logger.info(f"Query Payload: {payload}")

        if self.mode == PytanqueMode.SOCKET:
            self.socket.sendall(payload.encode())
            raw = self._read_socket_response(size)
        elif self.mode == PytanqueMode.STDIO:
            self._send_lsp_message(payload)
            raw = self._read_lsp_response()
        elif self.mode == PytanqueMode.HTTP:
            raw = self._send_request_message(payload)
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

    @send_request("petanque/start", StartResponse, is_session=True)
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
        return StartParams(uri, thm, pre_commands, opts)

    @send_request("petanque/setWorkspace", SetWorkspaceResponse)
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
        return SetWorkspaceParams(debug, uri)

    @send_request("petanque/run", RunResponse, is_session=True, continues_session=True)
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
        params = RunParams(state.st, cmd, opts)
        return params

    @send_request("petanque/goals", GoalsResponse)
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
        params = GoalsParams(state.st)
        return params

    @send_request("petanque/goals", CompleteGoalsResponse)
    def complete_goals(self, state: State, pretty: bool = True) -> Any:
        """
        Return the complete goal information.
        """
        params = GoalsParams(state.st)
        return params

    @send_request("petanque/premises", PremisesResponse)
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
        params = PremisesParams(state.st)
        return params

    @send_request("petanque/state/eq", StateEqualResponse)
    def state_equal(self, st1: State, st2: State, kind: Inspect) -> bool:
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
        # Hack: JSON representation of variant without arg should be a list, e.g., ["Physical"]
        params = StateEqualParams([kind], st1.st, st2.st)
        return params

    @send_request("petanque/state/hash", StateHashResponse)
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
        params = StateHashParams(state.st)
        return params
    
    @send_request("petanque/toc", TocResponse)
    def toc(self, file: str) -> list[tuple[str, List[TocElement]]]:
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
        params = TocParams(uri)
        return params

    @send_request("petanque/ast", AstResponse)
    def ast(self, state: State, text: str) -> dict:
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
        params = AstParams(state.st, text)
        return params

    @send_request("petanque/ast_at_pos", AstAtPosResponse)
    def ast_at_pos(
        self,
        file: str,
        line: int,
        character: int,
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
        ...     ast = client.ast_at_pos("./examples/foo.v", line=5, character=10)
        ...     print("AST at position:", ast)
        ...
        ...     # Get AST at theorem declaration
        ...     ast = client.ast_at_pos("./examples/foo.v", line=0, character=0)
        ...     print("Theorem declaration AST:", ast)
        ...
        ...     # Get AST at proof step
        ...     ast = client.ast_at_pos("./examples/foo.v", line=3, character=5)
        ...     print("Proof step AST:", ast)
        """
        path = os.path.abspath(file)
        uri = pathlib.Path(path).as_uri()
        pos = Position(line, character)
        params = AstAtPosParams(uri, pos)
        return params

    @send_request("petanque/get_state_at_pos", GetStateAtPosResponse, is_session=True)
    def get_state_at_pos(
        self, file: str, line: int, character: int, opts: Optional[Opts] = None
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
        ...     state = client.get_state_at_pos("./examples/foo.v", line=2, character=0)
        ...     print(f"State at start: {state.st}, finished: {state.proof_finished}")
        ...
        ...     # Get state in middle of proof
        ...     state = client.get_state_at_pos("./examples/foo.v", line=5, character=10)
        ...     goals = client.goals(state)
        ...     print(f"Goals at position: {len(goals)}")
        ...
        ...     # Get state at end of proof
        ...     state = client.get_state_at_pos("./examples/foo.v", line=8, character=5)
        ...     print(f"Proof finished: {state.proof_finished}")
        ...
        ...     # Check feedback at specific position
        ...     for level, msg in state.feedback:
        ...         print(f"Feedback level {level}: {msg}")
        """
        path = os.path.abspath(file)
        uri = pathlib.Path(path).as_uri()
        pos = Position(line, character)
        params = GetStateAtPosParams(uri, pos, opts)
        return params

    @send_request("petanque/get_root_state", GetRootStateResponse, is_session=True)
    def get_root_state(self, file: str, opts: Optional[Opts] = None) -> State:
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
        ...     pos_state = client.get_state_at_pos("./examples/foo.v", line=3, character=0)
        ...     print(f"Root state: {root_state.st}, Position state: {pos_state.st}")
        ...
        ...     # Check initial feedback
        ...     for level, msg in root_state.feedback:
        ...         print(f"Initial feedback level {level}: {msg}")
        """
        path = os.path.abspath(file)
        uri = pathlib.Path(path).as_uri()
        params = GetRootStateParams(uri, opts)
        return params

    @send_request("petanque/list_notations_in_statement", ListNotationsInStatementResponse)
    def list_notations_in_statement(self, state: State, statement: str) -> list[dict]:
        """
        Get the list of notations appearing in a theorem/lemma statement.

        This method analyzes a proposition or type statement (the part after the colon
        in a Lemma/Theorem/Proposition declaration) and returns all notations that appear
        in it, along with their interpretations in the given state.

        IMPORTANT: This only works on statements, not on arbitrary
        Coq commands or terms. For example, it works on "Lemma foo: n + m = m + n"  but not on "Goal n + m = m + n" or "Check (n + m)".

        Parameters
        ----------
        state : State
            The proof state providing the parsing context.
        statement : str
            The statement to analyze - must be a proposition or type expression.

        Returns
        -------
        list[dict]
            A list of the notations found in the statement with path, secpath, notation, and scope.

        Raises
        ------
        PetanqueError
            If the statement cannot be parsed in the given state context.

        Examples
        --------
        >>> with Pytanque("127.0.0.1", 8765) as client:
        ...     # Start a proof to get a state with notations in scope
        ...     state = client.start("./examples/foo.v", "addnC")
        ...
        ...     # Works: List notations in a statement (proposition/type)
        ...     notations = client.list_notations_in_statement(state, "Lemma foo: 2 * 1 + 0 / 1 = 2")
        ...     print(f"Found {len(notations)} notations")
        """
        params = ListNotationsParams(state.st, statement)
        return params

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

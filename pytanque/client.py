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
from .routes import PETANQUE_ROUTES, Params, RouteName

from .routes import (
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
    Responses
)
from .protocol import (
    Inspect,
    InspectGoals,
    InspectPhysical,
    State,
    Request,
    Goal,
    Response,
    Failure,
    Opts,
    Position,
    TocElement,
    GoalsResponse,
    NotationInfo
)

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


def mk_request(id: int, params: Params, route: RouteName, project_state=True) -> Request:
    # TODO: update petanque to remove project_state?
    params_json = params.to_json()
    if project_state:
        for f in fields(params):
            value = getattr(params, f.name)
            if isinstance(value, State):
                params_json[f.name] = params_json[f.name]['st']
    return Request(id, route.value, params_json)

def route(route_name: RouteName):
    """
    Send the return parameters to `mk_request` through the given route.
    """
    route = PETANQUE_ROUTES[route_name]
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(self: Pytanque, *args, **kwargs):
            timeout = kwargs.pop("timeout", None)
            params = fn(self, *args, **kwargs)
            resp = self.query(route_name, params, timeout=timeout)
            if not resp and resp is not False:
                return None
            return route.extract_response(resp)
            
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
    >>> # Socket mode
    >>> from pytanque import Pytanque
    >>> with Pytanque("127.0.0.1", 8765) as client:
    ...     state = client.start("./examples/foo.v", "addnC")

    >>> # Stdio mode
    >>> with Pytanque(stdio=True) as client:
    ...     state = client.start("./examples/foo.v", "addnC")
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
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
        >>> # Socket mode
        >>> client = Pytanque("127.0.0.1", 8765)
        >>> client.connect()

        >>> # Stdio mode
        >>> client = Pytanque(stdio=True)
        >>> client.connect()
        """
        self.process = None
        self.host = None
        self.port = None
        self.socket = None
        self.session_id = None
        self.mode = mode
        self.id = 0
        if mode == PytanqueMode.STDIO:
            return
        elif not host or not port:
            raise ValueError(
                "Must specify (host, port) for socket/http mode"
            )
        match mode:
            case PytanqueMode.SOCKET:
                self.mode = PytanqueMode.SOCKET
                self.host = host
                self.port = port
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            case PytanqueMode.HTTP:
                self.mode = PytanqueMode.HTTP
                self.host = host
                self.port = port

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
        >>> # Socket mode
        >>> client = Pytanque("127.0.0.1", 8765)
        >>> client.connect()
        >>> client.close()

        >>> # Stdio mode
        >>> client = Pytanque(stdio=True)
        >>> client.connect()
        >>> client.close()
        """
        match self.mode:
            case PytanqueMode.SOCKET:
                self.socket.connect((self.host, self.port))
                logger.info(f"Connected to the socket")
            case PytanqueMode.STDIO:
                self.process = subprocess.Popen(
                    ["pet"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=False,
                )
                logger.info(f"Spawned pet subprocess")
            case PytanqueMode.HTTP:
                url = f"http://{self.host}:{self.port}/login"
                response = requests.get(url)
                self.session_id = response.json()['session_id']

    def close(self) -> None:
        """
        Close the connection to the Petanque server or terminate subprocess.

        Examples
        --------
        >>> # Socket mode
        >>> client = Pytanque("127.0.0.1", 8765)
        >>> client.connect()
        >>> client.close()

        >>> # Stdio mode
        >>> client = Pytanque(stdio=True)
        >>> client.connect()
        >>> client.close()
        """
        match self.mode:
            case PytanqueMode.SOCKET:
                self.socket.close()
                logger.info(f"Socket closed")
            case PytanqueMode.STDIO:
                if self.process:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait()
                    logger.info(f"Pet subprocess terminated")
            case PytanqueMode.HTTP:
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

    def _send_request_message(self, route_name:RouteName, payload: Any, timeout: Optional[float]=None) -> None:
        url = f"http://{self.host}:{self.port}/rpc"
        payload['timeout'] = timeout
        payload['route_name'] = route_name
        payload['session_id'] = self.session_id
        response = requests.post(
            url,
            json=payload,
            timeout=timeout
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
    
    def query(
        self,
        route_name: RouteName,
        params: Params,
        size: int = 4096,
        timeout: Optional[float] = None
    ) -> Optional[Responses]:
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
        request = mk_request(self.id, params, route_name, project_state=project_state)
        payload = request.to_json()
        logger.info(f"Query Payload: {payload}")

        match self.mode:
            case PytanqueMode.SOCKET:
                #TODO: Improve timeout precision
                self.socket.settimeout(timeout)
                try:
                    payload = json.dumps(payload) + "\n"
                    self.socket.sendall(payload.encode())
                    raw = self._read_socket_response(size)
                except TimeoutError:
                    raise PetanqueError(
                        -33000, f"Timeout on {self.id}"
                    )
            case PytanqueMode.STDIO:
                if timeout:
                    logging.warning("Timeout not supported on Stdio mode.")
                payload = json.dumps(payload) + "\n"
                self._send_lsp_message(payload)
                raw = self._read_lsp_response()
            case PytanqueMode.HTTP:
                raw = self._send_request_message(route_name, payload, timeout=timeout)
        try:
            logger.info(f"Query Response: {raw}".strip())
            resp = Response.from_json_string(raw)
            if resp.id != self.id:
                raise PetanqueError(
                    -32603, f"Sent request {self.id}, got response {resp.id}"
                )
            if not resp.result and resp.result is not False:
                return None
            response_cls = PETANQUE_ROUTES[route_name].response_cls
            return response_cls.from_json(resp.result)
        except ValueError as e:
            failure = Failure.from_json_string(raw)
            raise PetanqueError(failure.error.code, failure.error.message)

    @route(RouteName.START)
    def start(
        self,
        file: str,
        thm: str,
        pre_commands: Optional[str] = None,
        opts: Optional[Opts] = None,
        timeout: Optional[float] = None
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

    @route(RouteName.SET_WORKSPACE)
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

    @route(RouteName.RUN)
    def run(
        self,
        state: State,
        cmd: str,
        opts: Optional[Opts] = None,
        verbose: bool = False,
        timeout: Optional[float] = None
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
        params = RunParams(state, cmd, opts)
        return params

    def goals(self, state: State, pretty: bool = True, timeout: Optional[float] = None) -> list[Goal]:
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
        complete_goals = self.complete_goals(state)
        if not complete_goals:
            return []
        goals = complete_goals.goals
        if pretty:
            for g in goals:
                g.pp = pp_goal(g)
        return goals

    @route(RouteName.GOALS)
    def complete_goals(self, state: State, timeout: Optional[float] = None) -> GoalsResponse:
        """
        Return the complete goal information for the given proof state.

        Unlike :meth:`goals`, this method returns the full :class:`GoalsResponse` object,
        including not only the active goals but also the proof stack, shelf, and given-up goals.

        Parameters
        ----------
        state : State
            The proof state to query.
        timeout : float, optional
            Timeout in seconds for the request.

        Returns
        -------
        GoalsResponse
            The complete goals response containing:
            - goals : list[Goal] - Active goals to prove
            - stack : list - The proof stack (for focused goals)
            - shelf : list - Shelved goals
            - given_up : list - Goals that have been given up

        Raises
        ------
        PetanqueError
            If state is invalid.

        See Also
        --------
        goals : Higher-level method returning only the list of active goals.
        """
        params = GoalsParams(state)
        return params

    @route(RouteName.PREMISES)
    def premises(self, state: State, timeout: Optional[float] = None) -> Any:
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
        params = PremisesParams(state)
        return params

    @route(RouteName.STATE_EQUAL)
    def state_equal(self, st1: State, st2: State, kind: Inspect, timeout: Optional[float] = None) -> bool:
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
        params = StateEqualParams([kind], st1, st2)
        return params

    @route(RouteName.STATE_HASH)
    def state_hash(self, state: State, timeout: Optional[float] = None) -> int:
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
        params = StateHashParams(state)
        return params
    
    @route(RouteName.TOC)
    def toc(self, file: str, timeout: Optional[float] = None) -> list[tuple[str, List[TocElement]]]:
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

    @route(RouteName.AST)
    def ast(
        self,
        state: State,
        text: str,
        timeout: Optional[float] = None
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
        params = AstParams(state, text)
        return params

    @route(RouteName.AST_AT_POS)
    def ast_at_pos(
        self,
        file: str,
        line: int,
        character: int,
        timeout: Optional[float] = None
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

    @route(RouteName.GET_STATE_AT_POS)
    def get_state_at_pos(
        self,
        file: str,
        line: int,
        character: int,
        opts: Optional[Opts] = None,
        timeout: Optional[float] = None
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

    @route(RouteName.GET_ROOT_STATE)
    def get_root_state(self, file: str, opts: Optional[Opts] = None, timeout: Optional[float] = None) -> State:
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

    @route(RouteName.LIST_NOTATIONS_IN_STATEMENTS)
    def list_notations_in_statement(self, state: State, statement: str, timeout: Optional[float] = None) -> List[NotationInfo]:
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
        params = ListNotationsInStatementParams(state, statement)
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

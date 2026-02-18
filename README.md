# Pytanque

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg?style=for-the-badge)](https://llm4rocq.github.io/pytanque)
[![Build Status](https://img.shields.io/github/actions/workflow/status/llm4rocq/pytanque/docs.yml?branch=main&style=for-the-badge)](https://github.com/llm4rocq/pytanque/actions/workflows/docs.yml)
[![Tests](https://img.shields.io/github/actions/workflow/status/llm4rocq/pytanque/tests.yml?branch=main&style=for-the-badge)](https://github.com/llm4rocq/pytanque/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg?style=for-the-badge)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg?style=for-the-badge)](https://github.com/llm4rocq/pytanque/blob/main/LICENSE)

Pytanque is a Python API for lightweight communication with the [Rocq](https://rocq-prover.org/) proof assistant via [coq-lsp](https://github.com/ejgallego/coq-lsp).

## Overview

- **Pytanque** is a lightweight Python client for Petanque
- **Petanque** is part of coq-lsp and provides a machine-to-machine protocol based on JSON-RPC to communicate with the Rocq prover.
- **pet-server/pet** are the commands that start a Petanque server which can interpret requests for the Rocq prover 

### Key Features

- **Three communication modes**: Socket mode (via `pet-server`) for multi-client usage, stdio mode (via `pet`) for single-client simplicity, or HTTP mode (via `rocq-ml-server`) for inference at scale.
- **Interactive theorem proving**: Execute tactics and commands step by step
- **Comprehensive feedback**: Access all Rocq messages (errors, warnings, search results)
- **State management**: Navigate proof states and compare them
- **AST parsing**: Get abstract syntax trees for commands and file positions
- **Position-based queries**: Get states at specific file positions 

## Installation

### Prerequisites

First, install coq-lsp with the required dependencies:

```bash
# Install dependencies
opam install lwt logs coq-lsp

# Or install one of the dev versions of coq-lsp, e.g., for Coq.8.20
opam install lwt logs coq.8.20.0
opam pin add coq-lsp https://github.com/ejgallego/coq-lsp.git#v8.20
```

### Install Pytanque

### Install from GitHub (Recommended)

```bash
pip install git+https://github.com/llm4rocq/pytanque.git
```

### Development Installation

We recommend using uv.
1. Clone this repository
2. Use the project workflow:
   ```bash
   cd pytanque
   uv sync
   ```

## Quick Start

Pytanque supports three communication modes with the Petanque backend:

### Socket Mode (via pet-server)

#### 1. Start the Petanque Server

```bash
$ pet-server  # Default port: 8765
# Or specify a custom port:
$ pet-server -p 9000
```

#### 2. Connect via Socket

```python
from pytanque import Pytanque

with Pytanque("127.0.0.1", 8765, mode=PytanqueMode.SOCKET) as client:
    # Start a proof
    state = client.start("./examples/foo.v", "addnC")
    print(f"Initial state: {state.st}, finished: {state.proof_finished}")
    
    # Execute tactics step by step
    state = client.run(state, "induction n.", verbose=True)
    state = client.run(state, "auto.", verbose=True)
    
    # Check current goals
    goals = client.goals(state)
    print(f"Current goals: {len(goals)}")
```


You can quickly try this example with:

```bash
# Socket mode example
python examples/foo.py
```

See also the notebook `examples/getting_started.ipynb` for more examples.

### Stdio Mode (via pet)

For direct communication without a server, use subprocess mode:

```python
from pytanque import Pytanque, PytanqueMode

with Pytanque(mode=PytanqueMode.STDIO) as client:
    # Same API as socket mode
    state = client.start("./examples/foo.v", "addnC")
    print(f"Initial state: {state.st}, finished: {state.proof_finished}")
    
    # Execute tactics step by step
    state = client.run(state, "induction n.", verbose=True)
    state = client.run(state, "auto.", verbose=True)
    
    # Check current goals
    goals = client.goals(state)
    print(f"Current goals: {len(goals)}")
```

### HTTP Mode (via rocq-ml-server)

For communication with a [rocq-ml-server](https://github.com/LLM4Rocq/rocq-ml-toolbox).

#### 1. Start the rocq-ml-Server

See [here](https://github.com/LLM4Rocq/rocq-ml-toolbox/tree/main/src/rocq_ml_toolbox/inference) for more details about startup arguments:

```bash
$ rocq-ml-server  # Default port: 5000
# Or specify a custom port:
$ rocq-ml-server -p 9000
```

#### 2. Connect via Http

```python
from pytanque import Pytanque

with Pytanque("127.0.0.1", 5000, mode=PytanqueMode.HTTP) as client:
    # Same API as socket mode
    state = client.start("./examples/foo.v", "addnC")
    print(f"Initial state: {state.st}, finished: {state.proof_finished}")
    
    # Execute tactics step by step
    state = client.run(state, "induction n.", verbose=True)
    state = client.run(state, "auto.", verbose=True)
    
    # Check current goals
    goals = client.goals(state)
    print(f"Current goals: {len(goals)}")
```


## API Overview

### Core Methods

- **`start(file, theorem)`**: Begin a proof session
- **`run(state, command)`**: Execute tactics or commands
- **`goals(state)`**: Get current proof goals
- **`premises(state)`**: Get available premises/lemmas

### Advanced Features

- **`get_root_state(file)`**: Get initial document state
- **`state_equal(st1, st2, kind)`**: Compare proof states
- **`state_hash(state)`**: Get state hash
- **`toc(file)`**: Get table of contents
- **`ast(state, text)`**: Parse command to AST
- **`ast_at_pos(file, line, char)`**: Get AST at file position
- **`get_state_at_pos(file, line, char)`**: Get proof state at position
- **`list_notation_in_statement(state, statement)`**: List the notations in a theorem

### Working with Feedback

All commands return states with feedback containing Rocq messages:

```python
state = client.run(state, "Search nat.")
for level, message in state.feedback:
    print(f"Level {level}: {message}")
```

## Testing

First install dev dependencies for testing:

```bash
uv sync --dev
```

You can launch all the tests with pytest. The test suite includes tests for both communication modes:

```bash
# Run all tests (socket + subprocess modes)
uv run pytest -v .

# Run only socket mode tests
uv run pytest tests/test_unit.py tests/test_integration.py -v

# Run only stdio mode tests  
uv run pytest tests/test_stdio.py -v
```

**Note:** Socket mode tests require `pet-server` to be running. Subprocess mode tests require the `pet` command to be available in PATH.

## Documentation

The complete API documentation is available at: [https://llm4rocq.github.io/pytanque](https://llm4rocq.github.io/pytanque)

### Building Documentation Locally

To build the documentation locally:

```bash
# Install documentation dependencies
uv sync --extra docs

# Build the documentation
cd docs
uv run sphinx-build -b html . _build/html

# Open the documentation
open _build/html/index.html
```

## Development

### Protocol

We use [atdpy](https://atd.readthedocs.io/en/latest/atdpy.html) to automatically generate serializers/deserializers from protocol type definitions. These types definition should match the ocaml code of petanque in coq-lsp.

To add a new method:

1. Add type definitions in `protocol.atd`
2. Run `atdpy protocol.atd` to generate `protocol.py`
3. Update `client.py` with the new method


## Troubleshooting

### Common Issues

**Socket Mode Connection Errors**
- Ensure `pet-server` is running: `pet-server -p 8765`
- Verify port availability and network connectivity
- Check firewall settings if connecting remotely

**Subprocess Mode Errors**
- Ensure `pet` command is available in PATH: `which pet`
- Verify coq-lsp installation includes the `pet` binary
- Check that the `pet` process can access your Rocq/Coq files

**File Path Issues**
- Use absolute paths or ensure working directory is correct
- Check file exists and has proper Coq/Rocq syntax
- Ensure workspace is set correctly with `client.set_workspace()`

**Installation Issues**
- Ensure coq-lsp is properly installed with both `pet` and `pet-server`
- Install `lwt` and `logs` before `coq-lsp` (required for both modes)
- Verify installation: `pet --version` and `pet-server --version`

**Performance Considerations**
- Socket mode: Better for multiple clients or long-running sessions
- Subprocess mode: Better for single-client usage or automation
- Choose the appropriate mode based on your use case

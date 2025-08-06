# Pytanque

Pytanque is a Python API for lightweight communication with the [Rocq](https://rocq-prover.org/) proof assistant via [coq-lsp](https://github.com/ejgallego/coq-lsp).

## Overview

- **Pytanque** is a lightweight Python client for Petanque
- **Petanque** is part of coq-lsp and provides a machine-to-machine protocol based on JSON-RPC to communicate with the Rocq prover.
- **pet-server** is the command that starts a Petanque server which can interpret requests for the Rocq prover 

### Key Features

- **Interactive theorem proving**: Execute tactics and commands step by step
- **Comprehensive feedback**: Access all Rocq messages (errors, warnings, search results)
- **AST parsing**: Get abstract syntax trees for commands and file positions
- **State management**: Navigate proof states and compare them
- **Position-based queries**: Get states at specific file positions

## Installation

### Prerequisites

First, install coq-lsp with the required dependencies:

```bash
opam install lwt logs coq.8.20.0
opam pin add coq-lsp https://github.com/ejgallego/coq-lsp.git#4112a0426a1ab43819879642e17c131a4f9e0281
```

### Install Pytanque

We recommend using a virtual environment. With `uv`:

```bash
uv venv
uv pip install -e .
source .venv/bin/activate
```

Or with standard Python:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quick Start

### 1. Start the Petanque Server

```bash
$ pet-server  # Default port: 8765
# Or specify a custom port:
$ pet-server -p 9000
```

### 2. Basic Usage

```python
from pytanque import Pytanque

with Pytanque("127.0.0.1", 8765) as client:
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

You can quickly try a similar example with:

```bash
python examples/foo.py
```

See also the notebook `examples/getting_started.ipynb` for more examples.

## API Overview

### Core Methods

- **`start(file, theorem)`**: Begin a proof session
- **`run(state, command)`**: Execute tactics or commands
- **`goals(state)`**: Get current proof goals
- **`premises(state)`**: Get available premises/lemmas

### Advanced Features

- **`ast(state, text)`**: Parse command to AST
- **`ast_at_pos(file, line, char, offset)`**: Get AST at file position
- **`get_state_at_pos(file, line, char, offset)`**: Get proof state at position
- **`get_root_state(file)`**: Get initial document state
- **`state_equal(st1, st2, kind)`**: Compare proof states
- **`state_hash(state)`**: Get state hash
- **`toc(file)`**: Get table of contents

### Working with Feedback

All commands return states with feedback containing Rocq messages:

```python
state = client.run(state, "Search nat.")
for level, message in state.feedback:
    print(f"Level {level}: {message}")
```

## Testing


You can launch all the tests with pytest.

```bash
pytest -v .
```

## Development

### Protocol

We use [atdpy](https://atd.readthedocs.io/en/latest/atdpy.html) to automatically generate serializers/deserializers from protocol type definitions. These types definition should match the ocaml code of petanque in coq-lsp.

To add a new method:

1. Add type definitions in `protocol.atd`
2. Run `atdpy protocol.atd` to generate `protocol.py`
3. Update `client.py` with the new method

### Project Structure

```
pytanque/
├── client.py          # Main Pytanque client class
├── protocol.py        # Auto-generated protocol definitions
├── __init__.py        # Package exports
tests/
├── conftest.py        # Shared test fixtures
├── test_unit.py       # Unit tests for individual methods
├── test_integration.py # Integration and workflow tests
examples/
├── foo.py            # Basic usage example
├── getting_started.ipynb # Jupyter notebook tutorial
└── foo.v             # Example Coq/Rocq file
```

## Troubleshooting

### Common Issues

**Server Connection Errors**
- Ensure `pet-server` is running: `pet-server -p 8765`
- Verify port availability

**File Path Issues**
- Use absolute paths or ensure working directory is correct
- Check file exists and has proper Coq/Rocq syntax

**Installation Issues**
- Ensure coq-lsp is properly installed
- Install `lwt` and `logs` before `coq-lsp` (required for `pet-server`)

# invoke-tasks

A Python library providing reusable [invoke](https://www.pyinvoke.org/) tasks for common development workflows. This library can be integrated into other Python projects to streamline build, testing, code quality, and infrastructure tasks.

## Features

- **Code Quality Tasks**: Linting, formatting, type checking, and complexity analysis
- **Infrastructure Tasks**: Cloud provider integration and infrastructure configuration
- **Installation Tools**: Utilities for setting up cloud tools and dependencies
- **Extensible Design**: Built as a library to be imported and used in other projects

## Installation

Install from the repository using pip:

```bash
pip install git+https://github.com/javad/Human-Knowledge-Graph.git#subdirectory=invoke-tasks
```

Or using [uv](https://docs.astral.sh/uv/) from the command line:

```bash
uv pip install git+https://github.com/javad/Human-Knowledge-Graph.git#subdirectory=invoke-tasks
```

Or add to your `pyproject.toml` for uv projects:

```toml
[tool.uv.sources]
invoke-tasks = { git = "https://github.com/Human-Knowledge-Graph/invoke-tasks.git" }

[project]
dependencies = [
    "invoke-tasks",
]
```

Then install with:

```bash
uv sync
```

Or clone the repository and install locally:

```bash
git clone https://github.com/javad/Human-Knowledge-Graph.git
cd Human-Knowledge-Graph/invoke-tasks
pip install -e .
```

## Usage

Import the task namespaces into your project's `tasks.py`:

```python
from invoke import Collection
from invoke_tasks import ns_code

# Create your invoke collection
ns = Collection(ns_code)
```

Then run tasks from the command line:

```bash
invoke --list  # View available tasks
invoke code.lint
invoke code.format
invoke code.type-check
```

## Requirements

- Python 3.10+
- invoke >= 2.2.1
- pyyaml >= 6.0.3

## License

See LICENSE for details.

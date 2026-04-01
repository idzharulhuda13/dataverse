"""
Sandbox for executing LLM-generated Python code safely.

Implements a 4-layer security model:
  1. Module & builtin blocklists
  2. AST-based static analysis (pre-execution)
  3. Restricted execution namespace
  4. Resource limits (timeout + output size cap)
"""

import ast
import io
import sys
import threading
import traceback
from dataclasses import dataclass, field
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.figure import Figure


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BLOCKED_MODULES = frozenset({
    # Filesystem & OS access
    "os", "subprocess", "sys", "shutil", "pathlib", "tempfile", "glob",
    # Network access
    "socket", "http", "urllib", "requests", "ftplib", "smtplib",
    "xmlrpc", "asyncio",
    # Low-level / dangerous
    "ctypes", "multiprocessing", "signal", "importlib",
    "pickle", "shelve", "marshal",
    # Code generation / introspection
    "code", "codeop", "compileall", "inspect",
    # Browser / external
    "webbrowser",
})

BLOCKED_BUILTINS = frozenset({
    "exec", "eval", "compile", "__import__",
    "open", "exit", "quit", "breakpoint",
    "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr",
    "input", "memoryview", "type",
})

# Dunder attributes that are commonly used to escape sandboxes
BLOCKED_DUNDER_ATTRS = frozenset({
    "__class__", "__bases__", "__subclasses__", "__mro__",
    "__builtins__", "__globals__", "__code__", "__func__",
    "__self__", "__dict__", "__module__", "__import__",
    "__loader__", "__spec__", "__qualname__",
})

MAX_OUTPUT_BYTES = 50 * 1024  # 50 KB
DEFAULT_TIMEOUT = 30  # seconds


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RESULT TYPE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SandboxResult:
    """Result of a sandboxed code execution."""
    output: Optional[str] = None
    dataframe: Optional[pd.DataFrame] = None
    figure: Optional[Figure] = None
    error: Optional[str] = None
    blocked: bool = False
    blocked_reason: Optional[str] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 2: AST STATIC ANALYSIS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class _SecurityVisitor(ast.NodeVisitor):
    """Walks the AST to detect forbidden patterns before execution."""

    def __init__(self) -> None:
        self.violations: list[str] = []

    # ── Import statements ────────────────────────────────────────────────

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top_module = alias.name.split(".")[0]
            if top_module in BLOCKED_MODULES:
                self.violations.append(
                    f"Importing blocked module '{alias.name}'"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            top_module = node.module.split(".")[0]
            if top_module in BLOCKED_MODULES:
                self.violations.append(
                    f"Importing from blocked module '{node.module}'"
                )
        self.generic_visit(node)

    # ── Function calls ───────────────────────────────────────────────────

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func

        # Direct call: __import__("os")
        if isinstance(func, ast.Name) and func.id == "__import__":
            self.violations.append("Direct call to __import__()")

        # Call to blocked builtins: eval(...), exec(...), open(...)
        if isinstance(func, ast.Name) and func.id in BLOCKED_BUILTINS:
            self.violations.append(f"Call to blocked builtin '{func.id}()'")

        # getattr / setattr calls (can bypass attribute restrictions)
        if isinstance(func, ast.Name) and func.id in ("getattr", "setattr", "delattr"):
            self.violations.append(
                f"Call to '{func.id}()' — can bypass attribute restrictions"
            )

        self.generic_visit(node)

    # ── Attribute access ─────────────────────────────────────────────────

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in BLOCKED_DUNDER_ATTRS:
            self.violations.append(
                f"Access to restricted dunder attribute '.{node.attr}'"
            )
        self.generic_visit(node)


def validate_code(code: str) -> Optional[str]:
    """
    Parse and statically analyze code for security violations.

    Returns:
        None if code is safe, or a human-readable error string if violations found.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax error in generated code: {e}"

    visitor = _SecurityVisitor()
    visitor.visit(tree)

    if visitor.violations:
        details = "; ".join(visitor.violations)
        return f"Security violation(s) detected: {details}"

    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 3: RESTRICTED NAMESPACE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Modules that LLM-generated code is allowed to import at runtime.
# These are safe analytics/viz libraries — no filesystem, network, or OS access.
ALLOWED_MODULES = frozenset({
    "pandas", "numpy", "matplotlib", "seaborn", "prophet",
    "math", "statistics", "collections", "itertools", "functools",
    "datetime", "re", "string", "textwrap", "decimal", "fractions",
    "operator", "copy", "json", "csv",
})


def _make_restricted_import():
    """
    Create a restricted __import__ function that only allows safe modules.

    LLM-generated code commonly includes `import seaborn as sns` or
    `import matplotlib.pyplot as plt` at the top. Python's `import` statement
    delegates to `__import__` at runtime, so we need to provide a gated version
    rather than removing it entirely.
    """
    _real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

    def _restricted_import(name, *args, **kwargs):
        top_module = name.split(".")[0]
        if top_module in BLOCKED_MODULES:
            raise ImportError(
                f"Importing '{name}' is not allowed in the sandbox. "
                f"Blocked modules: {', '.join(sorted(BLOCKED_MODULES))}"
            )
        if top_module not in ALLOWED_MODULES:
            raise ImportError(
                f"Importing '{name}' is not allowed in the sandbox. "
                f"Only analytics and visualization libraries are permitted."
            )
        return _real_import(name, *args, **kwargs)

    return _restricted_import


def _build_safe_builtins() -> dict:
    """
    Create a copy of __builtins__ with dangerous functions removed
    and __import__ replaced with a restricted version.
    """
    import builtins as _builtins_module

    safe = {k: v for k, v in vars(_builtins_module).items()
            if k not in BLOCKED_BUILTINS}

    # Replace __import__ with a gated version (not removed — import statements need it)
    safe["__import__"] = _make_restricted_import()

    return safe


def _build_exec_namespace(df: pd.DataFrame) -> dict:
    """
    Build the restricted globals dict for exec().

    Only provides the libraries needed for data analysis + visualization.
    """
    return {
        # Data
        "df": df,
        # Libraries
        "pd": pd,
        "np": np,
        "plt": plt,
        "sns": sns,
        # Restricted builtins
        "__builtins__": _build_safe_builtins(),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 4: RESOURCE-LIMITED EXECUTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class _TimedOut(Exception):
    """Raised when code execution exceeds the timeout."""
    pass


def _exec_with_timeout(code: str, exec_globals: dict, timeout: int) -> Optional[str]:
    """
    Execute code in a thread with a timeout.

    Returns:
        None on success, or an error string on failure.
    """
    result: dict = {"error": None}

    def _target():
        try:
            exec(code, exec_globals)  # noqa: S102
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}"

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        # Thread is still running — it exceeded the timeout.
        # Daemon threads will be cleaned up when the main process exits.
        return (
            f"Code execution timed out after {timeout} seconds. "
            f"The code may contain an infinite loop or be too computationally expensive."
        )

    return result["error"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PUBLIC API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def safe_execute(
    code: str,
    df: pd.DataFrame,
    timeout: int = DEFAULT_TIMEOUT,
) -> SandboxResult:
    """
    Validate and execute LLM-generated Python code in a sandboxed environment.

    Security layers:
      1. Module & builtin blocklists (constants)
      2. AST static analysis (pre-execution)
      3. Restricted execution namespace (no __import__, filtered builtins)
      4. Resource limits (timeout + output size cap)

    Args:
        code: Python source code to execute.
        df: The DataFrame to make available as `df` in the code.
        timeout: Maximum execution time in seconds (default: 30).

    Returns:
        SandboxResult with execution results or error/block information.
    """
    # ── Layer 2: AST static analysis ─────────────────────────────────────
    violation = validate_code(code)
    if violation:
        return SandboxResult(blocked=True, blocked_reason=violation)

    # ── Prepare execution environment ────────────────────────────────────
    output_buffer = io.StringIO()
    original_stdout = sys.stdout

    # Clear previous matplotlib state
    plt.close("all")

    # ── Layer 3: Build restricted namespace ──────────────────────────────
    exec_globals = _build_exec_namespace(df)

    try:
        # Redirect stdout to capture print output
        sys.stdout = output_buffer

        # ── Layer 4: Execute with timeout ────────────────────────────────
        error = _exec_with_timeout(code, exec_globals, timeout)

    finally:
        # Always restore stdout
        sys.stdout = original_stdout

    # ── Collect results ──────────────────────────────────────────────────
    if error:
        return SandboxResult(error=error)

    # Capture printed output (truncated)
    raw_output = output_buffer.getvalue().strip()
    if len(raw_output) > MAX_OUTPUT_BYTES:
        raw_output = raw_output[:MAX_OUTPUT_BYTES] + "\n... [output truncated]"
    output_str = raw_output or None

    # Retrieve final_df if created
    final_df = exec_globals.get("final_df", None)
    if final_df is not None and not isinstance(final_df, pd.DataFrame):
        return SandboxResult(error="'final_df' must be a DataFrame.")

    # Capture matplotlib figure if any plots were created
    fig = plt.gcf() if plt.get_fignums() else None

    return SandboxResult(
        output=output_str,
        dataframe=final_df,
        figure=fig,
    )

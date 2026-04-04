"""
Comprehensive tests for the code execution sandbox.

Tests verify that:
  ✅ Legitimate analytics code (pandas, matplotlib, seaborn, numpy) is allowed
  🛡️ Malicious / dangerous code is blocked before execution
  ⏱️ Resource limits (timeout, output cap) are enforced
"""

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for tests

import pandas as pd
import pytest

from models.sandbox import (
    BLOCKED_BUILTINS,
    BLOCKED_MODULES,
    SandboxResult,
    safe_execute,
    validate_code,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIXTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.fixture
def sample_df():
    """A small DataFrame for testing."""
    return pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie", "Diana"],
        "age": [25, 30, 35, 28],
        "score": [88.5, 92.3, 76.1, 95.0],
        "city": ["New York", "London", "Paris", "Tokyo"],
    })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ✅ LEGITIMATE CODE — SHOULD BE ALLOWED
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestLegitimateCode:
    """These tests verify that normal analytics code executes successfully."""

    def test_pandas_describe(self, sample_df):
        code = "print(df.describe())"
        result = safe_execute(code, sample_df)
        assert not result.blocked
        assert result.error is None
        assert result.output is not None
        assert "mean" in result.output

    def test_pandas_groupby(self, sample_df):
        code = "print(df.groupby('city')['score'].mean())"
        result = safe_execute(code, sample_df)
        assert not result.blocked
        assert result.error is None
        assert result.output is not None

    def test_seaborn_barplot(self, sample_df):
        code = """
import seaborn as sns
import matplotlib.pyplot as plt
plt.figure(figsize=(8, 5))
sns.barplot(data=df, x='name', y='score')
plt.title('Scores by Name')
plt.tight_layout()
plt.show()
"""
        result = safe_execute(code, sample_df)
        assert not result.blocked
        assert result.error is None
        assert result.figure is not None

    def test_matplotlib_bar(self, sample_df):
        code = """
import matplotlib.pyplot as plt
plt.figure(figsize=(8, 5))
plt.bar(df['name'], df['score'])
plt.title('Scores')
plt.tight_layout()
plt.show()
"""
        result = safe_execute(code, sample_df)
        assert not result.blocked
        assert result.error is None
        assert result.figure is not None

    def test_numpy_operations(self, sample_df):
        code = """
import numpy as np
mean_score = np.mean(df['score'].values)
std_score = np.std(df['score'].values)
print(f"Mean: {mean_score:.2f}, Std: {std_score:.2f}")
"""
        result = safe_execute(code, sample_df)
        assert not result.blocked
        assert result.error is None
        assert result.output is not None
        assert "Mean:" in result.output

    def test_final_df_creation(self, sample_df):
        code = """
final_df = df[df['age'] > 28].copy()
print(f"Filtered: {len(final_df)} rows")
"""
        result = safe_execute(code, sample_df)
        assert not result.blocked
        assert result.error is None
        assert result.dataframe is not None
        assert len(result.dataframe) == 2  # Bob (30) and Charlie (35)

    def test_display_df_creation(self, sample_df):
        code = """
display_df = df.pivot_table(index='city', values='score', aggfunc='mean')
print("Pivot table created")
"""
        result = safe_execute(code, sample_df)
        assert not result.blocked
        assert result.error is None
        assert result.display_df is not None
        assert isinstance(result.display_df, pd.DataFrame)
        assert "London" in result.display_df.index

    def test_print_output(self, sample_df):
        code = 'print("Hello from sandbox!")'
        result = safe_execute(code, sample_df)
        assert not result.blocked
        assert result.output == "Hello from sandbox!"

    def test_allowed_builtins(self, sample_df):
        """Ensure common safe builtins like len, range, sorted still work."""
        code = """
total = len(df)
ages = sorted(df['age'].tolist())
print(f"Total: {total}, Ages: {ages}")
"""
        result = safe_execute(code, sample_df)
        assert not result.blocked
        assert result.error is None
        assert "Total: 4" in result.output


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🛡️ MALICIOUS CODE — SHOULD BE BLOCKED
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestBlockedImports:
    """Tests that importing blocked modules is caught by AST analysis."""

    def test_import_os(self, sample_df):
        code = "import os\nos.listdir('/')"
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "os" in result.blocked_reason

    def test_import_subprocess(self, sample_df):
        code = "import subprocess\nsubprocess.run(['ls'])"
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "subprocess" in result.blocked_reason

    def test_from_os_import(self, sample_df):
        code = "from os import system\nsystem('whoami')"
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "os" in result.blocked_reason

    def test_import_shutil(self, sample_df):
        code = "import shutil\nshutil.rmtree('/tmp/test')"
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "shutil" in result.blocked_reason

    def test_import_socket(self, sample_df):
        code = "import socket\ns = socket.socket()"
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "socket" in result.blocked_reason

    def test_import_sys(self, sample_df):
        code = "import sys\nprint(sys.path)"
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "sys" in result.blocked_reason

    @pytest.mark.parametrize("module", list(BLOCKED_MODULES)[:10])
    def test_all_blocked_modules(self, sample_df, module):
        code = f"import {module}"
        result = safe_execute(code, sample_df)
        assert result.blocked, f"Module '{module}' was not blocked"


class TestBlockedBuiltins:
    """Tests that calls to dangerous builtins are blocked."""

    def test_eval(self, sample_df):
        code = 'eval("2 + 2")'
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "eval" in result.blocked_reason

    def test_exec_call(self, sample_df):
        code = 'exec("print(1)")'
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "exec" in result.blocked_reason

    def test_open_file(self, sample_df):
        code = "open('/etc/passwd').read()"
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "open" in result.blocked_reason

    def test_dunder_import(self, sample_df):
        code = "__import__('os').system('whoami')"
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "__import__" in result.blocked_reason

    def test_compile(self, sample_df):
        code = 'compile("print(1)", "<string>", "exec")'
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "compile" in result.blocked_reason


class TestBlockedDunderAccess:
    """Tests that sandbox-escape dunder attribute access is caught."""

    def test_class_escape(self, sample_df):
        code = "df.__class__.__bases__[0].__subclasses__()"
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "__class__" in result.blocked_reason

    def test_builtins_access(self, sample_df):
        code = "print.__builtins__"
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "__builtins__" in result.blocked_reason

    def test_globals_attr(self, sample_df):
        code = "print.__globals__"
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "__globals__" in result.blocked_reason

    def test_subclasses(self, sample_df):
        code = "object.__subclasses__()"
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "__subclasses__" in result.blocked_reason


class TestBlockedGetattr:
    """Tests that getattr/setattr bypass attempts are caught."""

    def test_getattr_bypass(self, sample_df):
        code = "getattr(df, '__class__')"
        result = safe_execute(code, sample_df)
        assert result.blocked
        # Should catch both getattr and __class__

    def test_setattr_bypass(self, sample_df):
        code = "setattr(df, 'evil', True)"
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "setattr" in result.blocked_reason


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⏱️ RESOURCE LIMITS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestResourceLimits:

    def test_timeout_infinite_loop(self, sample_df):
        """Infinite loops should be killed after timeout."""
        code = "while True: pass"
        result = safe_execute(code, sample_df, timeout=2)
        assert result.error is not None
        assert "timed out" in result.error

    def test_output_truncation(self, sample_df):
        """Extremely large output should be truncated."""
        code = "print('x' * 100000)"  # 100KB of output
        result = safe_execute(code, sample_df)
        assert not result.blocked
        assert result.output is not None
        assert "[output truncated]" in result.output

    def test_syntax_error(self, sample_df):
        """Syntax errors in generated code should be caught cleanly."""
        code = "def foo(:"
        result = safe_execute(code, sample_df)
        assert result.blocked
        assert "Syntax error" in result.blocked_reason


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔗 INTEGRATION: validate_code() directly
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestValidateCode:
    """Tests for the standalone validate_code() function."""

    def test_clean_code_passes(self):
        code = """
import pandas as pd
import matplotlib.pyplot as plt
df.head()
plt.show()
"""
        assert validate_code(code) is None

    def test_blocked_import_detected(self):
        result = validate_code("import os")
        assert result is not None
        assert "os" in result

    def test_multiple_violations(self):
        code = """
import os
import subprocess
eval("1+1")
"""
        result = validate_code(code)
        assert result is not None
        # Should report multiple violations
        assert "os" in result
        assert "subprocess" in result
        assert "eval" in result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔗 INTEGRATION: safe_execute() end-to-end result validation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestSafeExecuteResults:
    """Verify safe_execute returns correct SandboxResult fields for common cases."""

    def test_success_result(self, sample_df):
        result = safe_execute('print("ok")', sample_df)
        assert not result.blocked
        assert result.error is None
        assert result.output == "ok"
        assert result.figure is None

    def test_blocked_result(self, sample_df):
        result = safe_execute("import os", sample_df)
        assert result.blocked
        assert result.blocked_reason is not None
        assert "os" in result.blocked_reason

    def test_runtime_error_result(self, sample_df):
        result = safe_execute("1/0", sample_df)
        assert not result.blocked
        assert result.error is not None
        assert "ZeroDivision" in result.error

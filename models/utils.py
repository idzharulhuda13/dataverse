import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Any, Optional, Tuple
from matplotlib.figure import Figure
import io
import sys
import re

from models.sandbox import safe_execute

SUPPORTED_EXTENSIONS = (".csv", ".xls", ".xlsx", ".parquet", ".json", ".tsv")
MAX_FILE_SIZE_MB = 200
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def load_dataframe(
    file: Any, sheet_name: Any = 0
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Load a data file into a DataFrame with format auto-detection.

    Supported formats: CSV, Excel (.xls/.xlsx), Parquet, JSON, TSV.

    Parameters:
        file: Uploaded file object (must have .name and .size attributes) or file path.
        sheet_name: For Excel files, which sheet to load (name or 0-based index).
                    Defaults to 0 (first sheet).

    Returns:
        tuple: (Loaded DataFrame if valid, otherwise None; Error message or None)
    """
    try:
        # ── File size guard ──────────────────────────────────────────────
        file_size = getattr(file, "size", None)
        if file_size is not None and file_size > MAX_FILE_SIZE_BYTES:
            return None, (
                f"File is too large ({file_size / (1024*1024):.1f} MB). "
                f"Maximum allowed size is {MAX_FILE_SIZE_MB} MB."
            )

        # ── Format detection ─────────────────────────────────────────────
        name = getattr(file, "name", "").lower()

        if name.endswith(".csv"):
            df = pd.read_csv(file)
        elif name.endswith((".xls", ".xlsx")):
            df = pd.read_excel(file, sheet_name=sheet_name)
        elif name.endswith(".parquet"):
            df = pd.read_parquet(file)
        elif name.endswith(".json"):
            df = pd.read_json(file)
        elif name.endswith(".tsv"):
            df = pd.read_csv(file, sep="\t")
        else:
            ext = name.rsplit(".", 1)[-1] if "." in name else "unknown"
            return None, (
                f"Unsupported file format: .{ext}. "
                f"Supported formats: CSV, Excel, Parquet, JSON, TSV."
            )

        if df.empty:
            return None, "The uploaded file contains no data."

        return df, None

    except pd.errors.EmptyDataError:
        return None, "The file is empty or invalid."
    except pd.errors.ParserError:
        return None, "The file could not be parsed. Please check its format."
    except ImportError as e:
        # e.g. openpyxl not installed for .xlsx
        return None, f"Missing dependency for this file format: {e}"
    except Exception as e:
        return None, str(e)


def get_excel_sheet_names(file: Any) -> list[str]:
    """
    Return the list of sheet names in an Excel file.

    Parameters:
        file: Uploaded Excel file object.

    Returns:
        List of sheet name strings.
    """
    try:
        xls = pd.ExcelFile(file)
        return xls.sheet_names
    except Exception:
        return []


# Backward-compatible alias
def load_csv(file: Any) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Deprecated: use load_dataframe() instead."""
    return load_dataframe(file)

def summarize_numerical(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame that summarizes each numeric column."""
    numeric_summary = df.select_dtypes(include=["int", "float"]).describe().transpose()
    numeric_summary['missing_values'] = df.isna().sum() # type: ignore
    return numeric_summary

def summarize_categorical(df: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize categorical columns in the DataFrame.
    
    Parameters:
        df (pd.DataFrame): The DataFrame to summarize.
    
    Returns:
        pd.DataFrame: Summary of categorical columns with unique counts and top values.
    """
    categorical_summary = {}
    for col in df.select_dtypes(include='object').columns:
        unique_count = df[col].nunique()
        top_value = str(df[col].mode()[0]) if not df[col].mode().empty else None # type: ignore
        top_freq = df[col].value_counts().iloc[0] if unique_count > 0 else None
        categorical_summary[col] = {
            'unique_values': unique_count,
            'most_frequent': top_value,
            'frequency': top_freq,
            'missing_values': df[col].isna().sum()
        }
    return pd.DataFrame(categorical_summary).T

def execute_python_code(
    code: str, 
    df: pd.DataFrame
) -> Tuple[Optional[str], Optional[pd.DataFrame], Optional[Figure]]:
    """
    Executes the extracted Python code within a sandboxed environment.

    Parameters:
        code (str): The Python code to execute.
        df (DataFrame): The dataset to use in execution.

    Returns:
        tuple: (output_str, final_df, figure)
            - output_str (str or None): Printed output, if any.
            - final_df (DataFrame or None): The modified DataFrame if created.
            - figure (plt.Figure or None): The generated plot, if applicable.
    """
    result = safe_execute(code, df)

    if result.blocked:
        return f"🛡️ Code blocked: {result.blocked_reason}", None, None
    if result.error:
        return f"❌ Error executing code: {result.error}", None, None

    return result.output, result.dataframe, result.figure

def make_stop_on_token_callback_exit_code_block():
    in_code_block = False
    # Regex to find "```" possibly with some text around it, case-insensitive
    # re.DOTALL is not needed here as we are looking for the sequence within a single token_string
    # re.IGNORECASE is useful if "```" could be "```" or "```" (though unlikely for backticks)
    # The pattern looks for three backticks
    code_block_delimiter_pattern = re.compile(r"```python") 

    def callback(token_id: int, token_string: str) -> bool:
        nonlocal in_code_block

        # Use search to find the pattern anywhere in the token_string
        if code_block_delimiter_pattern.search(token_string):
            if not in_code_block:
                # Entering a code block, continue generating
                in_code_block = True
                return True
            else:
                # Exiting a code block, stop generation
                in_code_block = False
                return False  # Stop generation
        
        # If we are inside a code block, continue generation until "```" is found
        # If we are outside, continue generation until "```" is found
        return True

    return callback

def extract_non_code_text(reply: str) -> str:
    """
    Extract all code blocks and remove them from the reply, preserving non-code text.
    Also removes 'responding://' and similar patterns from the response.
    """
    code_pattern = r'```(?:python)?\n(.*?)\n```'
    response_without_code = re.sub(code_pattern, '', reply, flags=re.DOTALL | re.IGNORECASE).strip()
    response_without_code = re.sub(
        r'(```)?responding://(```)?|<\|end_of_text\|><\|begin_of_text\|>://|```python',
        '',
        response_without_code,
        flags=re.IGNORECASE
    ).strip()
    return response_without_code

def extract_python_code_blocks(reply: str) -> list[str]:
    """
    Extract all Python code blocks from a string reply.
    Returns a list of code block strings (without the triple backticks and 'python').
    """
    pattern = r'```python\n(.*?)\n```'
    matches = re.findall(pattern, reply, re.DOTALL)
    return [m.strip() for m in matches]
import re
import io
from typing import Any, Optional, Tuple

import pandas as pd

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



def extract_non_code_text(reply: str) -> str:
    """
    Strip code blocks from an LLM reply, returning only the prose text.
    Also removes 'responding://' and similar ADK artifacts.
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
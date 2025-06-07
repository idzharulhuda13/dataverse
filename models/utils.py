import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Any, Optional, Tuple
from matplotlib.figure import Figure
import io
import sys

def load_csv(file: Any) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Load a CSV file and perform basic validation.

    Parameters:
        file: Uploaded file object or file path.

    Returns:
        tuple: (Loaded DataFrame if valid, otherwise None; Error message or None)
    """
    try:
        df = pd.read_csv(file) # type: ignore

        if df.empty:
            return None, "The CSV file is empty."

        return df, None  # Return DataFrame and no error

    except pd.errors.EmptyDataError:
        return None, "The file is empty or invalid."
    except pd.errors.ParserError:
        return None, "The file could not be parsed. Check if it's a valid CSV."
    except Exception as e:
        return None, str(e)  # Handle unexpected errors

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
    Executes the extracted Python code within a controlled environment.

    Parameters:
        code (str): The Python code to execute.
        df (DataFrame): The dataset to use in execution.

    Returns:
        tuple: (output_str, final_df, figure)
            - output_str (str or None): Printed output, if any.
            - final_df (DataFrame or None): The modified DataFrame if created.
            - figure (plt.Figure or None): The generated plot, if applicable.
    """
    try:
        # Capture printed output
        output_buffer = io.StringIO()
        sys.stdout = output_buffer  # Redirect stdout to capture print statements

        # Clear previous plots
        plt.close("all")

        # Execution namespace
        exec_globals: dict[str, object] = {
            "df": df,  # Pass the original DataFrame
            "pd": pd,  # Pandas
            "plt": plt,  # Matplotlib
            "sns": sns   # Seaborn
        }

        # Execute the code
        exec(code, exec_globals)

        # Restore standard output
        sys.stdout = sys.__stdout__
        output_str = output_buffer.getvalue().strip() or None

        # Retrieve 'final_df' if created
        final_df = exec_globals.get("final_df", None)
        if final_df is not None and not isinstance(final_df, pd.DataFrame):
            return "❌ Error: 'final_df' must be a DataFrame.", None, None

        # Capture figure if any plots were created
        fig = plt.gcf() if plt.get_fignums() else None

        return output_str, final_df, fig

    except Exception as e:
        sys.stdout = sys.__stdout__  # Restore stdout in case of an error
        return f"❌ Error executing code: {str(e)}", None, None

def make_stop_on_token_callback():
    in_code = False
    def callback(token_id: int, token_string: str) -> bool:
        nonlocal in_code
        if token_string.find("```") != -1:
            if not in_code:
                in_code = True
                return True
            else:
                return False
        return True

    return callback
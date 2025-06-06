import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Any, Optional, Tuple, Union
from matplotlib.figure import Figure

def load_csv(file: Any) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Load a CSV file and perform basic validation.

    Parameters:
        file: Uploaded file object or file path.

    Returns:
        tuple: (Loaded DataFrame if valid, otherwise None; Error message or None)
    """
    try:
        df = pd.read_csv(file)

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
    numeric_summary['missing_values'] = df.isna().sum()
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
        top_value = df[col].mode()[0] if not df[col].mode().empty else None
        top_freq = df[col].value_counts().iloc[0] if unique_count > 0 else None
        categorical_summary[col] = {
            'unique_values': unique_count,
            'most_frequent': top_value,
            'frequency': top_freq,
            'missing_values': df[col].isna().sum()
        }
    return pd.DataFrame(categorical_summary).T

def execute_python_code(code: str, df: pd.DataFrame) -> Union[str, Figure]:
    """
    Executes the extracted Python code within the global context and captures any plots.

    Parameters:
        code (str): The Python code to execute.
        df (pd.DataFrame): The dataset to use in execution.

    Returns:
        str or Figure: Execution result or the generated figure.
    """
    try:
        # Create a new figure to capture plots
        plt.close("all")  # Clear previous figures
        exec_globals: dict[str, Any] = {
            "df": df,  # Pass the DataFrame
            "pd": pd,  # Pandas
            "plt": plt,  # Matplotlib
            "sns": sns  # Seaborn
        }
        exec(code, exec_globals)  # Execute the code
        
        # Capture the figure
        fig = plt.gcf()  # Get the current figure
        if fig.get_axes():  # If the figure has plots
            return fig  # Return the figure to be displayed
        else:
            return "✅ Code executed successfully (No plots detected)."
    except Exception as e:
        return f"❌ Error executing code: {str(e)}"
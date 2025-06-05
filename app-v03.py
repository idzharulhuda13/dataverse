import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re
import io
import sys

from gpt4all import GPT4All
from models.utils import load_csv, summarize_numerical, summarize_categorical, execute_python_code

# --------------------------
# Load LLM
model = GPT4All(
    "mistral-7b-instruct-v0.2.Q4_K_M.gguf", 
    model_path="models/", 
    allow_download=False
)

def execute_python_code(code, df):
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
        exec_globals = {
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

# --------------------------
# Streamlit App
st.title("CSV Data Explorer")
st.write("Upload a CSV file to explore the data.")

# File uploader
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

df = None
if uploaded_file:
    df, error = load_csv(uploaded_file)

    if error:
        st.error(error)
    if df is not None:
        st.success("File loaded successfully.")
        st.write(f"Number of rows: {df.shape[0]}")
        st.write(f"Number of columns: {df.shape[1]}")
        st.write("Columns:", df.columns.tolist())

        st.write("Here’s a preview of the data:")
        st.write(df.head())  # Display the first few rows

        # Numerical summarization
        st.subheader("Numerical Column Summary")
        numerical_summary = summarize_numerical(df)
        st.write(numerical_summary)

        # Categorical summarization
        st.subheader("Categorical Column Summary")
        categorical_summary = summarize_categorical(df)
        st.write(categorical_summary)

        # Data visualization
        st.subheader("Data Visualization")

        # Let the user select any column for histogram
        column = st.selectbox("Select a column for histogram", df.columns)
        if column:
            fig, ax = plt.subplots()
            if df[column].dtype == "object":
                df[column].value_counts().plot(kind="bar", ax=ax)
            else:
                df[column].hist(ax=ax, bins=20)
            st.pyplot(fig)

        # --------------------------------------------------------
        # Store chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Keep track of the original/modified DataFrame
        if "modified_df" not in st.session_state:
            st.session_state.modified_df = df.copy()

        # --------------------------------------------------------
        # Display existing conversation and any figures attached
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                # If a figure is attached to the message, display it
                if "figure" in message:
                    st.pyplot(message["figure"])

        # --------------------------------------------------------
        # User input
        user_query = st.chat_input("Ask me anything about your dataset (or about data analysis in general):")

        if user_query:
            # Save/display user message
            st.session_state.messages.append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)

            # Build conversation context
            conversation_text = f"""
            You are a professional data analyst and Python expert.
            Your task is to help users analyze their dataset by generating insights,
            performing statistical analysis, and creating visualizations using Python Seaborn
            without users knowing you write the code.

            Code Guidelines:
            - Only generate code when explicitly requested.
            - Keep all code in one code block.
            - Limit to one visualization per request for clarity.
            - Assume the dataset is already loaded as df and use it directly.

            The dataset contains the following structure:
            {st.session_state.modified_df.info()}
            
            Here are the first 10 rows:
            {st.session_state.modified_df.head(10)}

            Assistant must NOT write Python code unless explicitly asked to do so.
            Instead, provide recommendations for possible analyses.
            """

            # Append all previous messages to conversation_text
            for m in st.session_state.messages:
                role = m["role"].capitalize()
                content = m["content"].strip()
                conversation_text += f"{role}: {content}\n\n"

            # Generate assistant response
            response = model.generate(conversation_text, max_tokens=2048)

            # Extract the response excluding code blocks
            response_without_code = re.sub(
                r'```python\n.*?\n```', '', 
                response, flags=re.DOTALL
            ).strip()

            # Create a new assistant message
            assistant_msg = {
                "role": "assistant",
                "content": response_without_code
            }

            # Display assistant's text
            with st.chat_message("assistant"):
                st.markdown(response_without_code)

                # Extract and execute Python code if present
                code_blocks = re.findall(r'```python\n(.*?)\n```', response, re.DOTALL)
                if code_blocks:
                    for code in code_blocks:
                        st.markdown("**Generated Python Code:**")
                        st.code(code, language="python")

                        # Execute Python code
                        output_str, final_df, figure = execute_python_code(
                            code, st.session_state.modified_df
                        )

                        # Display printed output
                        if output_str:
                            st.write(output_str)

                        # Update DataFrame if modified
                        if final_df is not None:
                            st.session_state.modified_df = final_df
                            st.write("🔄 **Updated DataFrame Preview:**")
                            st.write(final_df.head())

                        # If a figure was generated, attach it to the assistant's message
                        if figure:
                            st.pyplot(figure)
                            assistant_msg["figure"] = figure

            # Store assistant message in session_state
            st.session_state.messages.append(assistant_msg)
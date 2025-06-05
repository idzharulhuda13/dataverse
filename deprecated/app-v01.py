import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re
import io

from gpt4all import GPT4All
from models.utils import load_csv, summarize_numerical, summarize_categorical, execute_python_code

# --------------------------
# Load LLM
model = GPT4All(
    "mistral-7b-instruct-v0.2.Q4_K_M.gguf", 
    model_path="models/", 
    allow_download=False
)

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

        # Let the user select any column for histogram visualization
        column = st.selectbox("Select a column for histogram", df.columns)
        if column:
            fig, ax = plt.subplots()
            if df[column].dtype == "object":
                df[column].value_counts().plot(kind="bar", ax=ax)
            else:
                df[column].hist(ax=ax, bins=20)
            st.pyplot(fig)

        # --------------------------------------------------------
        # Define system prompt (outside of any user queries)
        system_message = f"""
        Role & Expertise:
        You are an expert data analyst and Python developer specializing in exploratory data analysis (EDA) and visualization.

        Objective:
        Your task is to help users analyze their dataset by providing insights, performing statistical analysis, and creating clear, informative visualizations using Seaborn.

        Guidelines:
        1. Guide first: Instead of writing code immediately, suggest useful analyses, trends, or comparisons based on the dataset.
        2. Code generation: Only generate code when explicitly requested. When writing code:
        - Keep all code in one code block.
        - Limit to one visualization per request for clarity.
        - Assume the dataset is already loaded as df and use it directly.
        3. Clear explanations: Always explain insights in a user-friendly way.

        Dataset Context:
        The dataset has the following structure:
        {df.info()}

        Here are the first 10 rows:
        {df.head(10)}
        """

        # --------------------------------------------------------
        if "messages" not in st.session_state:
            st.session_state.messages = []

        if "plots" not in st.session_state:
            st.session_state.plots = []

        # --------------------------------------------------------
        # Display existing conversation
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Display previously generated plots
        for fig in st.session_state.plots:
            st.pyplot(fig)

        # --------------------------------------------------------
        # User input
        user_query = st.chat_input("Ask me anything about your dataset (or about data analysis in general):")

        if user_query:
            # Show user message
            st.session_state.messages.append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)

            # Build a single text prompt from all messages
            conversation_text = system_message
            for m in st.session_state.messages:
                if m["role"] == "system":
                    conversation_text += f"System: {m['content'].strip()}\n\n"
                elif m["role"] == "user":
                    conversation_text += f"User: {m['content'].strip()}\n\n"
                else:
                    conversation_text += f"Assistant: {m['content'].strip()}\n\n"

            # Generate text from GPT4All
            response = model.generate(
                conversation_text,  # entire conversation so far
                max_tokens=2048,
            )

            # Process & display assistant response
            # 1) Show the main text (excluding code blocks)
            response_without_code = re.sub(
                r'```python\n.*?\n```', '', response, flags=re.DOTALL
            ).strip()

            with st.chat_message("assistant"):
                st.markdown(response_without_code)

                # 2) Extract & execute code blocks if present
                code_blocks = re.findall(r'```python\n(.*?)\n```', response, re.DOTALL)
                if code_blocks:
                    for code in code_blocks:
                        st.markdown("**Generated Python Code:**")
                        st.code(code, language="python")
                        if df is not None:
                            result = execute_python_code(code, df)
                            if isinstance(result, str):
                                st.write(result)
                            else:
                                st.pyplot(result)
                                st.session_state.plots.append(result)

            # Store the entire raw assistant response
            st.session_state.messages.append({"role": "assistant", "content": response})
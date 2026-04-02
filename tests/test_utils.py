import pytest
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from models.utils import (
    summarize_numerical,
    summarize_categorical,
    execute_python_code,
    extract_non_code_text,
    extract_python_code_blocks,
    load_csv
)

@pytest.fixture
def sample_df():
    data = {
        'A': [1, 2, np.nan, 4, 5],
        'B': [10.5, 20.5, 30.5, 40.5, 50.5],
        'C': ['foo', 'bar', 'foo', 'baz', np.nan],
        'D': ['item1', 'item1', 'item2', 'item2', 'item1']
    }
    return pd.DataFrame(data)

def test_summarize_numerical(sample_df):
    summary = summarize_numerical(sample_df)
    assert isinstance(summary, pd.DataFrame)
    assert 'A' in summary.index
    assert 'B' in summary.index
    assert 'C' not in summary.index
    assert summary.loc['A', 'missing_values'] == 1
    assert summary.loc['B', 'missing_values'] == 0
    assert summary.loc['A', 'mean'] == 3.0

def test_summarize_categorical(sample_df):
    summary = summarize_categorical(sample_df)
    assert isinstance(summary, pd.DataFrame)
    assert 'C' in summary.index
    assert 'D' in summary.index
    assert 'A' not in summary.index
    assert summary.loc['C', 'unique_values'] == 3
    assert summary.loc['D', 'unique_values'] == 2
    assert summary.loc['D', 'most_frequent'] == 'item1'
    assert summary.loc['D', 'frequency'] == 3
    assert summary.loc['C', 'missing_values'] == 1

def test_execute_python_code(sample_df):
    code = "final_df = df.copy()\nfinal_df['E'] = final_df['A'] * 2\nprint('Hello World')"
    output, final_df, fig = execute_python_code(code, sample_df)
    
    assert "Hello World" in output
    assert final_df is not None
    assert 'E' in final_df.columns
    assert final_df['E'].iloc[0] == 2
    assert fig is None

def test_execute_python_code_blocked(sample_df):
    code = "import os\nos.listdir('.')"
    output, final_df, fig = execute_python_code(code, sample_df)
    
    assert "🛡️ Code blocked" in output
    assert final_df is None
    assert fig is None

def test_execute_python_code_error(sample_df):
    code = "df['non_existent_column'] + 1"
    output, final_df, fig = execute_python_code(code, sample_df)
    
    assert "❌ Error executing code" in output
    assert final_df is None
    assert fig is None

def test_extract_non_code_text():
    reply = "Here is some text.\n```python\nprint('hello')\n```\nMore text here.\nresponding:// something"
    text = extract_non_code_text(reply)
    assert "Here is some text." in text
    assert "More text here." in text
    assert "print('hello')" not in text
    assert "responding://" not in text

def test_extract_python_code_blocks():
    reply = "Text\n```python\ncode1\n```\nMore text\n```python\ncode2\n```"
    blocks = extract_python_code_blocks(reply)
    assert len(blocks) == 2
    assert blocks[0] == "code1"
    assert blocks[1] == "code2"

def test_load_csv_alias(tmp_path):
    csv_file = tmp_path / "test.csv"
    pd.DataFrame({'a': [1, 2]}).to_csv(csv_file, index=False)
    
    class MockFile:
        def __init__(self, path):
            self.name = str(path)
            self.size = path.stat().st_size
            self.file = open(path, 'rb')
        def read(self, size=-1): return self.file.read(size)
        def seek(self, pos): self.file.seek(pos)
    
    mock_file = MockFile(csv_file)
    df, error = load_csv(mock_file)
    assert error is None
    assert df is not None
    assert len(df) == 2
    mock_file.file.close()

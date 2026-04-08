import pytest
import pandas as pd
from models.utils import (
    extract_non_code_text,
    load_dataframe,
)


@pytest.fixture
def sample_df():
    data = {
        'A': [1, 2, 3, 4, 5],
        'B': [10.5, 20.5, 30.5, 40.5, 50.5],
        'C': ['foo', 'bar', 'foo', 'baz', 'qux'],
    }
    return pd.DataFrame(data)


def test_extract_non_code_text():
    reply = "Here is some text.\n```python\nprint('hello')\n```\nMore text here.\nresponding:// something"
    text = extract_non_code_text(reply)
    assert "Here is some text." in text
    assert "More text here." in text
    assert "print('hello')" not in text
    assert "responding://" not in text


def test_extract_non_code_text_plain():
    """Text with no code blocks should be returned unmodified."""
    reply = "Just plain text with no code."
    assert extract_non_code_text(reply) == reply


def test_load_dataframe_csv(tmp_path):
    csv_file = tmp_path / "test.csv"
    pd.DataFrame({'a': [1, 2], 'b': [3, 4]}).to_csv(csv_file, index=False)

    class MockFile:
        def __init__(self, path):
            self.name = str(path)
            self.size = path.stat().st_size
            self._file = open(path, 'rb')
        def read(self, size=-1): return self._file.read(size)
        def seek(self, pos): self._file.seek(pos)

    mock_file = MockFile(csv_file)
    result = load_dataframe(mock_file)
    mock_file._file.close()

    assert result.error is None
    assert result.df is not None
    assert list(result.df.columns) == ['a', 'b']
    assert len(result.df) == 2


def test_load_dataframe_unsupported_format(tmp_path):
    bad_file = tmp_path / "test.txt"
    bad_file.write_text("hello")

    class MockFile:
        def __init__(self, path):
            self.name = str(path)
            self.size = path.stat().st_size

    result = load_dataframe(MockFile(bad_file))
    assert result.df is None
    assert "Unsupported file format" in result.error

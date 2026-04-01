"""
Tests for models.utils.load_dataframe — multi-format file loading.

Uses lightweight in-memory file objects to avoid filesystem dependencies.
"""

import io
import json
import pytest
import pandas as pd

from models.utils import load_dataframe, get_excel_sheet_names, MAX_FILE_SIZE_BYTES


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class FakeUpload(io.BytesIO):
    """Mimics a Streamlit UploadedFile: a BytesIO with .name and .size attrs."""

    def __init__(self, name: str, data: bytes):
        super().__init__(data)
        self.name = name
        self.size = len(data)


def _make_csv_bytes(rows=3) -> bytes:
    df = pd.DataFrame({"a": range(rows), "b": [f"v{i}" for i in range(rows)]})
    return df.to_csv(index=False).encode("utf-8")


def _make_excel_bytes(sheet_names: list[str] | None = None) -> bytes:
    buf = io.BytesIO()
    if sheet_names is None:
        sheet_names = ["Sheet1"]
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name in sheet_names:
            pd.DataFrame({"x": [1, 2], "y": [3, 4]}).to_excel(
                writer, sheet_name=name, index=False
            )
    return buf.getvalue()


def _make_json_bytes() -> bytes:
    records = [{"col1": 1, "col2": "a"}, {"col1": 2, "col2": "b"}]
    return json.dumps(records).encode("utf-8")


def _make_parquet_bytes() -> bytes:
    buf = io.BytesIO()
    pd.DataFrame({"p": [10, 20], "q": [30, 40]}).to_parquet(buf, index=False)
    return buf.getvalue()


def _make_tsv_bytes() -> bytes:
    df = pd.DataFrame({"t1": [1, 2], "t2": [3, 4]})
    return df.to_csv(index=False, sep="\t").encode("utf-8")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CSV
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCSV:
    def test_valid_csv(self):
        f = FakeUpload("data.csv", _make_csv_bytes())
        df, err = load_dataframe(f)
        assert err is None
        assert df is not None
        assert list(df.columns) == ["a", "b"]
        assert len(df) == 3

    def test_empty_csv(self):
        f = FakeUpload("empty.csv", b"a,b\n")
        df, err = load_dataframe(f)
        assert df is None
        assert err is not None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EXCEL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestExcel:
    def test_valid_xlsx(self):
        f = FakeUpload("report.xlsx", _make_excel_bytes())
        df, err = load_dataframe(f)
        assert err is None
        assert df is not None
        assert list(df.columns) == ["x", "y"]

    def test_multi_sheet_first_sheet(self):
        f = FakeUpload("multi.xlsx", _make_excel_bytes(["Sales", "Costs"]))
        df, err = load_dataframe(f, sheet_name="Sales")
        assert err is None
        assert df is not None

    def test_multi_sheet_second_sheet(self):
        f = FakeUpload("multi.xlsx", _make_excel_bytes(["Sales", "Costs"]))
        df, err = load_dataframe(f, sheet_name="Costs")
        assert err is None
        assert df is not None

    def test_get_sheet_names(self):
        f = FakeUpload("multi.xlsx", _make_excel_bytes(["Alpha", "Beta", "Gamma"]))
        names = get_excel_sheet_names(f)
        assert names == ["Alpha", "Beta", "Gamma"]

    def test_corrupted_xlsx(self):
        f = FakeUpload("bad.xlsx", b"not-a-real-excel-file")
        df, err = load_dataframe(f)
        assert df is None
        assert err is not None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# JSON
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestJSON:
    def test_valid_json_records(self):
        f = FakeUpload("data.json", _make_json_bytes())
        df, err = load_dataframe(f)
        assert err is None
        assert df is not None
        assert list(df.columns) == ["col1", "col2"]
        assert len(df) == 2

    def test_invalid_json(self):
        f = FakeUpload("bad.json", b"{not valid json")
        df, err = load_dataframe(f)
        assert df is None
        assert err is not None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PARQUET
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestParquet:
    def test_valid_parquet(self):
        f = FakeUpload("data.parquet", _make_parquet_bytes())
        df, err = load_dataframe(f)
        assert err is None
        assert df is not None
        assert list(df.columns) == ["p", "q"]

    def test_corrupted_parquet(self):
        f = FakeUpload("bad.parquet", b"not-a-parquet-file")
        df, err = load_dataframe(f)
        assert df is None
        assert err is not None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TSV
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestTSV:
    def test_valid_tsv(self):
        f = FakeUpload("data.tsv", _make_tsv_bytes())
        df, err = load_dataframe(f)
        assert err is None
        assert df is not None
        assert list(df.columns) == ["t1", "t2"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UNSUPPORTED FORMAT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestUnsupported:
    def test_txt_file(self):
        f = FakeUpload("readme.txt", b"hello world")
        df, err = load_dataframe(f)
        assert df is None
        assert "Unsupported file format" in err

    def test_no_extension(self):
        f = FakeUpload("datafile", b"some data")
        df, err = load_dataframe(f)
        assert df is None
        assert err is not None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FILE SIZE LIMIT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestFileSize:
    def test_oversized_file_rejected(self):
        f = FakeUpload("big.csv", b"a,b\n1,2\n")
        f.size = MAX_FILE_SIZE_BYTES + 1  # Fake a large size
        df, err = load_dataframe(f)
        assert df is None
        assert "too large" in err

    def test_exact_limit_accepted(self):
        f = FakeUpload("ok.csv", _make_csv_bytes())
        f.size = MAX_FILE_SIZE_BYTES  # Exactly at limit
        df, err = load_dataframe(f)
        assert err is None
        assert df is not None

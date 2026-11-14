"""Reading an imported CSV or Excel file (spec 3 "Endpoints", the data notes; AKS-113).

``ithax.model.data_files`` reads the bytes of an uploaded file into its columns: names
from the first row, a type per column (``number``, ``text`` or ``empty``), the numbers of
each column in row order, the record count and a preview. Every problem with the content is
``UnreadableData`` (E189) with a message and a hint, never an exception from the parser;
the file name is checked by ``file_name_problem``.
"""

import io
import zipfile
from datetime import datetime

import numpy
import openpyxl
import pytest

from ithax.model import data_files
from ithax.model.data_files import (
    PREVIEW_RECORDS,
    UnreadableData,
    file_format,
    file_name_problem,
    read_table,
)


def csv(text: str) -> bytes:
    return text.encode("utf-8")


def xlsx(*rows: tuple[object, ...], sheets: tuple[str, ...] = ()) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Arrivals"
    for row in rows:
        sheet.append(list(row))
    for title in sheets:
        workbook.create_sheet(title).append(["other"])
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


def refused(raw: bytes, form: str = "csv") -> UnreadableData:
    with pytest.raises(UnreadableData) as caught:
        read_table(raw, form)
    problem = caught.value
    assert problem.code == "E189"
    assert problem.message and problem.hint
    assert "Error" not in problem.message and "Traceback" not in problem.message
    return problem


# --- file names ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["times.csv", "Times.CSV", "March 2026 arrivals.xlsx", "a_b-c.d.csv", "9.xlsx"]
)
def test_a_good_file_name_is_accepted(name: str) -> None:
    assert file_name_problem(name) is None


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".csv",
        ".hidden.csv",
        "times",
        "times.txt",
        "times.xls",
        "times.xlsm",
        "times.csv.",
        "times.csv ",
        " times.csv",
        "../times.csv",
        "a/b.csv",
        "a\\b.csv",
        "C:times.csv",
        "C:\\data\\times.csv",
        "/etc/times.csv",
        "t\x00.csv",
        "zeit\u00e4.csv",
        "con.csv",
        "NUL.xlsx",
        "com1.csv",
        "Lpt9.data.csv",
        "a" * 97 + ".csv",
        "index.json",
    ],
)
def test_a_name_that_could_leave_data_or_clash_on_windows_is_refused(name: str) -> None:
    problem = file_name_problem(name)
    assert problem is not None and problem


def test_a_name_of_one_hundred_characters_is_the_longest() -> None:
    assert file_name_problem("a" * 96 + ".csv") is None


def test_the_format_follows_the_extension_in_any_case() -> None:
    assert file_format("a.csv") == "csv"
    assert file_format("a.CSV") == "csv"
    assert file_format("a.Xlsx") == "xlsx"


# --- CSV -----------------------------------------------------------------------------------


def test_a_csv_gives_names_types_numbers_records_and_a_preview() -> None:
    table = read_table(csv("time,gap_min,note\n08:00:12,1.8,\n08:02:40,2.5,late\n"), "csv")
    assert table.format == "csv" and table.sheet is None
    assert [column.name for column in table.columns] == ["time", "gap_min", "note"]
    assert [column.type for column in table.columns] == ["text", "number", "text"]
    assert table.records == 2
    assert list(table.columns[1].values) == [1.8, 2.5]
    assert table.preview == (("08:00:12", 1.8, None), ("08:02:40", 2.5, "late"))


def test_a_byte_order_mark_quotes_and_crlf_are_read() -> None:
    raw = '\ufeff"gap, min",n\r\n"1.5",2\r\n3e1,-4\r\n'.encode()
    table = read_table(raw, "csv")
    assert [column.name for column in table.columns] == ["gap, min", "n"]
    assert list(table.columns[0].values) == [1.5, 30.0]
    assert list(table.columns[1].values) == [2.0, -4.0]


def test_names_are_stripped_and_cells_with_only_spaces_are_empty() -> None:
    table = read_table(csv(" gap \n 1.5 \n   \n2\n"), "csv")
    assert table.columns[0].name == "gap"
    assert list(table.columns[0].values) == [1.5, 2.0]
    # The row of spaces is all empty, so it is skipped.
    assert table.records == 2


@pytest.mark.parametrize(
    "cell", ["nan", "NaN", "inf", "-Infinity", "1e400", ".5", "+2", "01", "1,5"]
)
def test_a_cell_outside_the_number_grammar_or_beyond_a_float_is_text(cell: str) -> None:
    table = read_table(csv(f'gap\n"{cell}"\n'), "csv")
    assert table.columns[0].type == "text"
    assert table.preview == ((cell,),)


def test_a_column_of_empty_cells_is_empty_and_a_header_only_file_has_no_records() -> None:
    table = read_table(csv("a,b\n1,\n"), "csv")
    assert [column.type for column in table.columns] == ["number", "empty"]
    header_only = read_table(csv("a,b\n"), "csv")
    assert header_only.records == 0
    assert [column.type for column in header_only.columns] == ["empty", "empty"]


def test_a_short_row_has_empty_cells_at_its_end() -> None:
    table = read_table(csv("a,b,c\n1\n2,3,4\n"), "csv")
    assert table.preview == ((1.0, None, None), (2.0, 3.0, 4.0))


def test_extra_empty_cells_beyond_the_header_are_allowed() -> None:
    table = read_table(csv("a,b\n1,2,,\n"), "csv")
    assert table.preview == ((1.0, 2.0),)


def test_the_preview_holds_the_first_ten_records() -> None:
    rows = "\n".join(str(number) for number in range(25))
    table = read_table(csv(f"n\n{rows}\n"), "csv")
    assert table.records == 25
    assert len(table.preview) == PREVIEW_RECORDS == 10
    assert table.preview[-1] == (9.0,)


@pytest.mark.parametrize(
    ("raw", "words"),
    [
        (b"", "no header row"),
        (b"\n\n", "no header row"),
        ("gap\n1\n".encode("utf-16"), "UTF-8"),
        ("gap,zeit\n1,\xe4\n".encode("latin-1"), "UTF-8"),
        (b"a,,c\n1,2,3\n", "empty"),
        (b"a,a\n1,2\n", "twice"),
        (b"a, a \n1,2\n", "twice"),
        (b"1.5,2\n3,4\n", "number"),
        (b"a,b\n1,2,3\n", "more cells"),
        (b'a\n"unclosed\n', None),
        (b"a\n" + b'"' + b"x" * 200_000 + b'"\n', None),
        (xlsx(("a",), (1,)), "UTF-8"),
        (("x" * 201 + "\n1\n").encode(), "200"),
    ],
)
def test_a_csv_that_breaks_the_rules_is_e189(raw: bytes, words: str | None) -> None:
    problem = refused(raw)
    if words is not None:
        assert words in problem.message


def test_case_different_names_are_different_columns() -> None:
    # Column names are compared exactly; only file names are compared ignoring case.
    table = read_table(csv("a,A\n1,2\n"), "csv")
    assert [column.name for column in table.columns] == ["a", "A"]


def test_a_nul_character_is_text_or_refused_but_never_raises() -> None:
    try:
        table = read_table(csv("a\nx\x00y\n"), "csv")
    except UnreadableData:
        return
    assert table.columns[0].type == "text"


def test_too_many_records_or_cells_is_e189(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_files, "MAX_RECORDS", 3)
    assert read_table(csv("a\n1\n2\n3\n"), "csv").records == 3
    assert "records" in refused(csv("a\n1\n2\n3\n4\n")).message
    monkeypatch.setattr(data_files, "MAX_CELLS", 4)
    assert "cells" in refused(csv("a,b,c\n1,2,3\n4,5,6\n")).message


def test_a_file_above_the_size_limit_is_e189(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_files, "MAX_FILE_BYTES", 8)
    assert "64 MiB" in refused(csv("gap\n1.5\n2.5\n")).message


# --- Excel ---------------------------------------------------------------------------------


def test_an_xlsx_reads_its_first_worksheet() -> None:
    raw = xlsx(
        ("gap", "when", "flag", "count"),
        (1.5, datetime(2026, 1, 1, 8, 0), True, 3),
        (2, "x", None, "4"),
        (None, None, None, None),
        (3.0, None, None, None),
        sheets=("Other",),
    )
    table = read_table(raw, "xlsx")
    assert table.format == "xlsx" and table.sheet == "Arrivals"
    assert [column.name for column in table.columns] == ["gap", "when", "flag", "count"]
    assert [column.type for column in table.columns] == ["number", "text", "text", "number"]
    assert table.records == 3
    assert list(table.columns[0].values) == [1.5, 2.0, 3.0]
    assert list(table.columns[3].values) == [3.0, 4.0]
    assert table.preview[0] == (1.5, "2026-01-01T08:00:00", "TRUE", 3.0)


def test_an_xlsx_header_must_be_text() -> None:
    assert "number" in refused(xlsx((2024, "b"), (1, 2)), "xlsx").message
    assert "empty" in refused(xlsx(("a", None, "c"), (1, 2, 3)), "xlsx").message


def test_trailing_empty_header_cells_of_an_xlsx_are_not_columns() -> None:
    table = read_table(xlsx(("a", None), (1, None)), "xlsx")
    assert [column.name for column in table.columns] == ["a"]
    assert "more cells" in refused(xlsx(("a", None), (1, 2)), "xlsx").message


def edited(raw: bytes, member: str, change: dict[bytes, bytes]) -> bytes:
    source = zipfile.ZipFile(io.BytesIO(raw))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == member:
                for old, new in change.items():
                    assert old in data
                    data = data.replace(old, new, 1)
            target.writestr(info, data)
    return out.getvalue()


SHEET = "xl/worksheets/sheet1.xml"


@pytest.mark.parametrize(
    "raw",
    [
        b"not a zip file",
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(600),  # password protected: OLE
        b"",
        xlsx(("a",), (1,))[:300],
    ],
)
def test_an_xlsx_that_cannot_be_opened_is_e189(raw: bytes) -> None:
    assert "Excel" in refused(raw, "xlsx").message


def test_an_xlsx_that_declares_xml_entities_is_e189() -> None:
    raw = edited(
        xlsx(("a",), (1,)), SHEET, {b"<worksheet": b'<!DOCTYPE w [<!ENTITY e "x">]><worksheet'}
    )
    refused(raw, "xlsx")


def test_a_number_cell_of_five_thousand_digits_is_e189_not_a_crash() -> None:
    raw = edited(xlsx(("a",), (7,)), SHEET, {b"<v>7</v>": b"<v>" + b"9" * 5000 + b"</v>"})
    refused(raw, "xlsx")


@pytest.mark.parametrize("value", [b"1e999", b"9" * 400, b"-1e999"])
def test_a_number_cell_beyond_a_float_is_text(value: bytes) -> None:
    raw = edited(xlsx(("a",), (7,)), SHEET, {b"<v>7</v>": b"<v>" + value + b"</v>"})
    table = read_table(raw, "xlsx")
    assert table.columns[0].type == "text"


def test_a_workbook_unpacking_beyond_the_limit_is_e189(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = xlsx(("a",), (1,))
    monkeypatch.setattr(data_files, "MAX_UNPACKED_BYTES", 100)
    assert "unpacked" in refused(raw, "xlsx").message


def test_a_workbook_without_a_worksheet_is_e189(monkeypatch: pytest.MonkeyPatch) -> None:
    class NoSheets:
        worksheets: tuple[object, ...] = ()

        def close(self) -> None:
            pass

    monkeypatch.setattr(data_files, "_open_workbook", lambda raw: NoSheets())
    assert "worksheet" in refused(xlsx(("a",), (1,)), "xlsx").message


def test_an_empty_first_worksheet_has_no_header_row() -> None:
    assert "no header row" in refused(xlsx(), "xlsx").message


def test_numbers_are_kept_as_float64() -> None:
    table = read_table(csv("a\n1\n2\n"), "csv")
    assert isinstance(table.columns[0].values, numpy.ndarray)
    assert table.columns[0].values.dtype == numpy.float64


def test_an_unknown_format_is_a_programming_error() -> None:
    with pytest.raises(ValueError):
        read_table(b"a\n1\n", "ods")


def test_a_workbook_header_of_spaces_is_no_header_row() -> None:
    assert "no header row" in refused(xlsx(("  ", None), (1, 2)), "xlsx").message


def test_an_excel_value_of_another_kind_is_its_text() -> None:
    from decimal import Decimal

    assert data_files._excel_cell(Decimal("1.5")) == "1.5"
    assert data_files._excel_cell(" 2 ") == 2.0

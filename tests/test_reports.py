"""O7 — modello, formattazione e motore dei report."""

import pytest

from adbx.data.fields import Field
from adbx.data.report_engine import format_report_value, render_report
from adbx.data.reports import (
    ReportCalc,
    ReportDefinition,
    ReportError,
    ReportField,
    ReportGroup,
    ReportSummary,
    ReportText,
)
from adbx.data.workspace import Workspace


def make_avsales(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("AVSALES", [
        Field("CUST_ID", "C", 6),
        Field("LASTNAME", "C", 15),
        Field("INV_NUMBER", "C", 4),
        Field("INV_TYPE", "C", 7),
        Field("INV_DATE", "D", 8),
        Field("TAPE_ID", "C", 4),
        Field("TAPE_TITLE", "C", 40),
        Field("INVTOTAL", "N", 8, 2),
    ])
    rows = [
        ("1001", "Richardson", "A001", "Rental", "19910203", "1041",
         "Roxanne", "3.24"),
        ("1021", "Barber", "A111", "Sale", "19911028", "1008",
         "The Horror Of Party Beach", "32.46"),
        ("1021", "Barber", "A117", "Sale", "19911102", "1052",
         "Bugs Bunny's Wacky Adventure", "43.19"),
        ("1021", "Barber", "A118", "Rental", "19911104", "1040",
         "I Dismember Momma", "3.24"),
        ("1076", "Bernstein", "A002", "Rental", "19911019", "1036",
         "Paper Moon", "3.24"),
    ]
    names = [field.name for field in database.fields]
    for row in rows:
        database.append(dict(zip(names, row)))
    return workspace, database


def invoice_report(workspace, letter="A", *, grouped=False):
    report = ReportDefinition(workspace, "AVSALES", letter,
                              "Alpha Video Invoice Report 1", 132)
    if grouped:
        report.description = "Alpha Video Invoice Report 2"
        report.set_group_count(1)
        report.groups = [ReportGroup(1, "AVSALES.CUST_ID")]
        report.sections = ["page_header", "titles", "detail",
                           "group1_footer", "summary"]
    else:
        report.sections = ["page_header", "titles", "detail", "summary"]
    report.fields = [
        ReportField("page_header", 1, 70, "SYSTEM.DATE", length=10,
                    format="1"),
        ReportField("page_header", 2, 70, "SYSTEM.PAGENUMBER", length=4),
        ReportField("titles", 1, 1, "AVSALES.CUST_ID", length=6),
        ReportField("titles", 1, 7, "AVSALES.LASTNAME", length=15),
        ReportField("titles", 1, 24, "AVSALES.INV_NUMBER", length=4),
        ReportField("titles", 1, 30, "AVSALES.INV_TYPE", length=4),
        ReportField("titles", 1, 35, "AVSALES.INV_DATE", length=10),
        ReportField("titles", 1, 47, "AVSALES.TAPE_ID", length=4),
        ReportField("titles", 1, 52, "AVSALES.TAPE_TITLE", length=20,
                    window=20),
        ReportField("titles", 1, 73, "AVSALES.INVTOTAL", length=10),
        ReportField("detail", 1, 1, "AVSALES.CUST_ID", length=6,
                    data="Unique" if grouped else "Value"),
        ReportField("detail", 1, 7, "AVSALES.LASTNAME", length=15,
                    data="Unique" if grouped else "Value"),
        ReportField("detail", 1, 24, "AVSALES.INV_NUMBER", length=4),
        ReportField("detail", 1, 30, "AVSALES.INV_TYPE", length=4),
        ReportField("detail", 1, 35, "AVSALES.INV_DATE", length=10,
                    format="2"),
        ReportField("detail", 1, 47, "AVSALES.TAPE_ID", length=4),
        ReportField("detail", 1, 52, "AVSALES.TAPE_TITLE", length=40,
                    window=20, format="X"),
        ReportField("detail", 1, 73, "AVSALES.INVTOTAL", length=10),
    ]
    report.texts = [ReportText("page_header", 1, 1,
                               "Alpha Video Invoice Report")] if not grouped \
        else [ReportText("page_header", 1, 1,
                         "Alpha Video Invoice Report 2")]
    if grouped:
        report.texts += [ReportText("group1_footer", 2, 46,
                                    "Customer Total Sales:")]
        report.summaries = [ReportSummary("TOT1", "AVSALES.INVTOTAL",
                                          "Total", "Group 1")]
        report.fields.append(ReportField("group1_footer", 2, 66,
                                         "SUMMARY.TOT1", length=10,
                                         justification="R"))
        report.summaries.append(ReportSummary("TOTG", "AVSALES.INVTOTAL",
                                              "Total", "Grand"))
        report.fields.append(ReportField("summary", 1, 66, "SUMMARY.TOTG",
                                         length=10, justification="R"))
    else:
        report.summaries = [ReportSummary("TOTG", "AVSALES.INVTOTAL",
                                          "Total", "Grand")]
        report.fields.append(ReportField("summary", 1, 66, "SUMMARY.TOTG",
                                         length=10, justification="R"))
    return report


def test_report_save_active_get_and_delete(tmp_path):
    workspace, _database = make_avsales(tmp_path)
    report = invoice_report(workspace)
    report.save()
    restored = workspace.get_report("AVSALES", "A")
    assert restored is not None
    assert restored.label.startswith("A - Alpha Video Invoice")
    assert restored.width == 132
    assert len(restored.fields) == len(report.fields)
    assert workspace.report_names("AVSALES") == [
        "A - Alpha Video Invoice Report 1"]
    assert workspace.delete_report("AVSALES", "A")
    assert workspace.get_report("AVSALES", "A") is None


def test_report_validation(tmp_path):
    workspace, _database = make_avsales(tmp_path)
    broken = ReportDefinition(workspace, "AVSALES", "B", "")
    broken.fields = [ReportField("detail", 1, 1, "AVSALES.MISSING",
                                 length=10)]
    with pytest.raises(ReportError, match="not found"):
        broken.save()

    outside = ReportDefinition(workspace, "AVSALES", "C", "")
    outside.fields = [ReportField("detail", 1, 1, "OTHER.FIELD", length=10)]
    with pytest.raises(ReportError, match="outside"):
        outside.save()

    gap = ReportDefinition(workspace, "AVSALES", "D", "")
    gap.groups = [ReportGroup(2, "AVSALES.CUST_ID")]
    with pytest.raises(ReportError, match="without gaps"):
        gap.save()

    calc = ReportDefinition(workspace, "AVSALES", "E", "")
    calc.calcs = [ReportCalc("BAD", "1 +")]
    with pytest.raises(ReportError, match="Calculated field"):
        calc.save()

    width = ReportDefinition(workspace, "AVSALES", "F", "", width=80)
    width.fields = [ReportField("detail", 1, 75, "AVSALES.CUST_ID",
                                length=10)]
    with pytest.raises(ReportError, match="past column"):
        width.save()


def test_summary_options_and_groups(tmp_path):
    workspace, _database = make_avsales(tmp_path)
    report = invoice_report(workspace, grouped=True)
    report.validate()
    assert report.group_count == 1
    assert "group1_footer" in report.sections
    summary = report.summaries[0]
    assert summary.summary_type == "Total"
    assert summary.level == "Group 1"
    assert summary.ignore == "None"
    assert summary.mode == "Running"
    report.set_group_count(0)
    assert report.group_count == 0
    assert "group1_footer" not in report.sections


def test_formatting_codes():
    numeric = Field("AMOUNT", "N", 12, 2)
    assert format_report_value("1988.03", numeric, "X$F", None, 60, 60,
                               "N").lines[0] == (
        "One thousand nine hundred eighty eight and 03/100 Dollars")
    assert format_report_value("1988.03", numeric, "X", None, 60, 60,
                               "N").lines[0] == (
        "One thousand nine hundred eighty eight and 03/100")
    assert format_report_value("1988.03", numeric, "$*", None, 12, 12,
                               "R").lines[0] == "***$1,988.03"
    assert format_report_value("1234.5", numeric, "$", None, 12, 12,
                               "R").lines[0] == "   $1,234.50"
    assert format_report_value("0.00", numeric, "B", None, 10, 10,
                               "R").lines[0].strip() == ""
    assert format_report_value("", numeric, "-", None, 10, 10,
                               "R").suppress
    text = Field("NAME", "C", 20)
    assert format_report_value("alpha software", text, "W", None, 20, 20,
                               "N").lines[0] == "Alpha Software"
    assert format_report_value("alpha software", text, "Y", None, 20, 20,
                               "N").lines[0] == "Alpha software"
    wrapped = format_report_value("one two three four", text, "X", None,
                                  30, 7, "L")
    assert [line.strip() for line in wrapped.lines] == [
        "one two", "three", "four"]
    date_field = Field("WHEN", "D", 8)
    assert format_report_value("19931031", date_field, "4", None, 20, 20,
                               "L").lines[0].startswith("October 31")
    memo = Field("NOTES", "M", 10)
    memo_lines = format_report_value("alpha beta gamma", memo, "@", None,
                                     300, 10, "L")
    assert [line.strip() for line in memo_lines.lines] == [
        "alpha beta", "gamma"]


def test_engine_basic_report_matches_tutorial(tmp_path):
    import datetime

    workspace, _database = make_avsales(tmp_path)
    report = invoice_report(workspace)
    output = render_report(report, workspace,
                           today=datetime.date(1991, 3, 15))
    text = output.text
    assert "Alpha Video Invoice Report" in text
    assert "03/15/1991" in text
    assert "1001  Richardson" in text
    assert "A001" in text
    assert "03/02/1991" in text
    assert "The Horror Of Party" in text
    assert "Beach" in text
    assert "85.37" in text


def test_engine_grouping_unique_group_totals(tmp_path):
    import datetime

    workspace, _database = make_avsales(tmp_path)
    report = invoice_report(workspace, letter="B", grouped=True)
    output = render_report(report, workspace,
                           today=datetime.date(1991, 12, 23))
    lines = [line.rstrip() for page in output.pages
             for line in page.lines]
    text = "\n".join(lines)
    assert text.count("Customer Total Sales") == 3
    assert "78.89" in text
    assert "3.24" in text
    assert text.count("1021  Barber") == 1
    assert text.count("Barber") == 1
    assert text.count("Richardson") == 1
    assert "TOTG" not in text


def test_multipass_percentage_with_summary_and_calc(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("SALES", [
        Field("NAME", "C", 10), Field("AMOUNT", "N", 8, 2)])
    for name, amount in (("A", "10.00"), ("B", "30.00"), ("C", "60.00")):
        database.append({"NAME": name, "AMOUNT": amount})
    report = ReportDefinition(workspace, "SALES", "A", "Percent", 80)
    report.sections = ["detail", "summary"]
    report.summaries = [ReportSummary("TOTAL", "SALES.AMOUNT", "Total",
                                      "Grand", "None", "Pre-processed")]
    report.calcs = [ReportCalc("PCT", "(AMOUNT * 100) / TOTAL")]
    report.fields = [
        ReportField("detail", 1, 1, "SALES.NAME", length=10),
        ReportField("detail", 1, 15, "SALES.AMOUNT", length=8,
                    justification="R"),
        ReportField("detail", 1, 30, "CALC.PCT", length=10, decimals=2,
                    justification="R"),
        ReportField("summary", 1, 1, "SUMMARY.TOTAL", length=10,
                    justification="R"),
    ]
    report.save()
    text = render_report(report, workspace).text
    assert "10.00" in text
    assert "30.00" in text
    assert "60.00" in text
    assert "100.00" in text


def test_pagination_page_numbers_and_max_records(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("ITEMS", [
        Field("NAME", "C", 10), Field("VALUE", "N", 6, 0)])
    for index in range(1, 8):
        database.append({"NAME": f"Item {index}", "VALUE": str(index)})
    report = ReportDefinition(workspace, "ITEMS", "A", "Paged", 60)
    report.sections = ["page_header", "detail", "page_footer"]
    report.page_length = 12
    report.max_records_page = 2
    report.fields = [
        ReportField("page_header", 1, 1, "SYSTEM.PAGENUMBER", length=4),
        ReportField("detail", 1, 1, "ITEMS.NAME", length=10),
        ReportField("page_footer", 1, 1, "SYSTEM.PAGENUMBER", length=4),
    ]
    report.save()
    output = render_report(report, workspace)
    assert len(output.pages) == 4
    for page in output.pages:
        assert any(line.strip() == str(page.number) for line in page.lines)
    names = "\n".join(line for page in output.pages for line in page.lines)
    for index in range(1, 8):
        assert f"Item {index}" in names


def test_blank_lines_suppression_and_non_suppressible(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("T", [
        Field("NAME", "C", 10)])
    database.append({"NAME": "A"})
    database.append({"NAME": "B"})

    def build(suppress):
        report = ReportDefinition(workspace, "T", "A" if suppress else "B",
                                  "", 60)
        report.sections = ["detail"]
        report.section_lines = {"detail": 3}
        report.suppress_blank_lines = suppress
        report.fields = [ReportField("detail", 2, 1, "T.NAME", length=10)]
        report.texts = [ReportText("detail", 1, 1, "Titolo")]
        if not suppress:
            report.texts.append(ReportText("detail", 3, 1, "Fondo"))
        return report

    suppressed = render_report(build(True), workspace).pages[0].lines
    assert suppressed == ["Titolo", "A", "Titolo", "B"]
    # Un carattere non sopprimibile conserva la riga vuota.
    report = build(True)
    report.texts.append(ReportText("detail", 3, 1, chr(127)))
    lines = render_report(report, workspace).pages[0].lines
    assert lines[:3] == ["Titolo", "A", ""]
    kept = render_report(build(False), workspace).pages[0].lines
    assert kept == ["Titolo", "A", "Fondo", "Titolo", "B", "Fondo"]


def test_check_writing_two_pages_and_formats(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("PAYABLE", [
        Field("COMPANY", "C", 20), Field("AMOUNT", "N", 10, 2)])
    database.append({"COMPANY": "Adverts Inc", "AMOUNT": "1988.03"})
    database.append({"COMPANY": "Beta Corp", "AMOUNT": "32.00"})
    report = ReportDefinition(workspace, "PAYABLE", "A", "Checks", 80)
    report.sections = ["detail"]
    report.section_lines = {"detail": 22}
    report.suppress_blank_lines = False
    report.page_length = 22
    report.standard_page_length = False
    report.fields = [
        ReportField("detail", 1, 1, "PAYABLE.COMPANY", length=20),
        ReportField("detail", 2, 1, "PAYABLE.AMOUNT", length=12,
                    format="$*"),
        ReportField("detail", 3, 1, "PAYABLE.AMOUNT", length=60,
                    format="X$F", justification="L"),
    ]
    report.save()
    output = render_report(report, workspace)
    assert len(output.pages) == 2
    assert all(len(page.lines) == 22 for page in output.pages)
    assert "***$1,988.03" in output.pages[0].lines[1]
    assert "One thousand nine hundred eighty eight and 03/100 Dollars" in \
        output.pages[0].lines[2]
    assert "Thirty two and 00/100 Dollars" in output.pages[1].lines[2]


def test_pdf_writer(tmp_path):
    from adbx.render.report_pdf import write_report_pdf

    workspace, _database = make_avsales(tmp_path)
    output = render_report(invoice_report(workspace), workspace)
    target = write_report_pdf(output, tmp_path / "report.pdf", "Invoice")
    data = target.read_bytes()
    assert data.startswith(b"%PDF-1.4")
    assert b"Adverts" not in data
    assert b"1001" in data
    assert data.rstrip().endswith(b"%%EOF")


def test_system_fields_counters_and_page_summary(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("NUM", [
        Field("VALUE", "N", 6, 0)])
    for value in range(1, 5):
        database.append({"VALUE": str(value)})
    report = ReportDefinition(workspace, "NUM", "A", "Counters", 80)
    report.sections = ["page_header", "detail", "page_footer", "summary"]
    report.page_length = 12
    report.max_records_page = 2
    report.fields = [
        ReportField("page_header", 1, 1, "SYSTEM.PAGENUMBER", length=4),
        ReportField("detail", 1, 1, "NUM.VALUE", length=6),
        ReportField("detail", 1, 10, "SYSTEM.CNTR_GRAND", length=4),
        ReportField("detail", 1, 16, "SYSTEM.CNTR_PAGE", length=4),
        ReportField("page_footer", 1, 1, "SUMMARY.PGTOT", length=6,
                    justification="R"),
        ReportField("summary", 1, 1, "SUMMARY.GRTOT", length=6,
                    justification="R"),
    ]
    report.summaries = [
        ReportSummary("PGTOT", "NUM.VALUE", "Total", "Page"),
        ReportSummary("GRTOT", "NUM.VALUE", "Total", "Grand"),
    ]
    report.save()
    output = render_report(report, workspace)
    assert len(output.pages) == 2
    assert "3" in output.pages[0].lines[-1]
    assert "7" in output.pages[1].lines[-1]
    assert "10" in output.text
    assert any(line.strip().startswith("1") for line in output.pages[0].lines)


def test_attributes_and_section_management(tmp_path):
    workspace = Workspace(tmp_path)
    database = workspace.create_database("T", [Field("NAME", "C", 10)])
    database.append({"NAME": "X"})
    report = ReportDefinition(workspace, "T", "A", "", 60)
    report.sections = ["detail"]
    report.fields = [ReportField("detail", 1, 1, "T.NAME", length=10)]
    report.texts = [ReportText("detail", 1, 10, "!BBold!N!UU!O")]
    report.save()
    line = render_report(report, workspace).pages[0].lines[0]
    assert "Bold" in line
    assert "!b" not in line
    assert report.add_section("titles")
    assert not report.add_section("titles")
    assert report.remove_section("titles")
    report.sections = ["detail"]
    report.add_section("page_header")
    assert report.sections == ["page_header", "detail"]


def test_set_report_uses_child_detail_rows(tmp_path):
    from adbx.data import indexing
    from adbx.data.sets import Link, SetDefinition

    workspace = Workspace(tmp_path)
    header = workspace.create_database("AVHEADER", [
        Field("INV_NO", "C", 6), Field("CUST_ID", "C", 6)])
    items = workspace.create_database("AVITEMS", [
        Field("INV_NO", "C", 6), Field("QTY", "N", 4, 0),
        Field("PRICE", "N", 8, 2)])
    indexing.save_index(items, indexing.IndexDefinition("AVINVNO", "INV_NO"))
    header.append({"INV_NO": "A015", "CUST_ID": "1001"})
    items.append({"INV_NO": "A015", "QTY": "2", "PRICE": "3.10"})
    items.append({"INV_NO": "A015", "QTY": "3", "PRICE": "1.50"})
    definition = SetDefinition(workspace, "AVIDEO", "", "AVHEADER")
    definition.links = [Link("AVHEADER", "AVITEMS", "AVINVNO", "INV_NO",
                             "All")]
    definition.save()
    report = ReportDefinition(workspace, "AVIDEO", "A", "Invoice", 80)
    report.set_group_count(1)
    report.groups = [ReportGroup(1, "AVHEADER.INV_NO")]
    report.sections = ["titles", "group1_header", "detail",
                       "group1_footer", "summary"]
    report.fields = [
        ReportField("group1_header", 1, 1, "AVHEADER.INV_NO", length=6),
        ReportField("group1_header", 1, 10, "AVHEADER.CUST_ID", length=6),
        ReportField("detail", 1, 1, "AVITEMS.QTY", length=4,
                    justification="R"),
        ReportField("detail", 1, 8, "AVITEMS.PRICE", length=8,
                    justification="R"),
        ReportField("detail", 1, 20, "CALC.SUB", length=10,
                    decimals=2, justification="R"),
        ReportField("group1_footer", 1, 1, "SUMMARY.INVTOT", length=10,
                    justification="R"),
    ]
    report.calcs = [ReportCalc("SUB", "QTY * PRICE")]
    report.summaries = [ReportSummary("INVTOT", "CALC.SUB", "Total",
                                      "Group 1", "None", "Pre-processed")]
    report.save()
    output = render_report(report, workspace)
    text = output.text
    assert "A015" in text
    assert "1001" in text
    assert "2" in text and "3.10" in text and "6.20" in text
    assert "3" in text and "1.50" in text and "4.50" in text
    assert "10.70" in text

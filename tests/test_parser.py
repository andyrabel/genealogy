from genealogy.gedcom.parser import parse_gedcom
from tests.fixtures.sample_gedcom import SAMPLE_GEDCOM


def test_parses_all_top_level_records():
    doc = parse_gedcom(SAMPLE_GEDCOM)
    types = [r.record_type for r in doc.records]
    assert types == ["HEAD", "INDI", "INDI", "INDI", "INDI", "INDI", "FAM", "SOUR", "NOTE", "TRLR"]


def test_parses_name_and_structured_subfields():
    doc = parse_gedcom(SAMPLE_GEDCOM)
    john = doc.by_xref("@I1@")
    name = john.sub("NAME")
    assert name.value == "John /Smith/"
    assert name.sub("GIVN").value == "John"
    assert name.sub("SURN").value == "Smith"


def test_custom_vendor_tag_preserved():
    doc = parse_gedcom(SAMPLE_GEDCOM)
    john = doc.by_xref("@I1@")
    uid = john.sub("_UID")
    assert uid is not None
    assert uid.value == "12345678-ABCD-EFAB-0000-000000000000"


def test_cont_merges_with_newline():
    doc = parse_gedcom(SAMPLE_GEDCOM)
    note = doc.by_xref("@N1@")
    assert note.value == "This is a shared note record.\nIt has a second line via CONT."


def test_pointer_detection():
    doc = parse_gedcom(SAMPLE_GEDCOM)
    john = doc.by_xref("@I1@")
    fams = john.sub("FAMS")
    assert fams.is_pointer()
    assert fams.value == "@F1@"


def test_event_date_and_place():
    doc = parse_gedcom(SAMPLE_GEDCOM)
    john = doc.by_xref("@I1@")
    birth = john.sub("BIRT")
    assert birth.sub("DATE").value == "12 MAR 1850"
    assert birth.sub("PLAC").value == "Leeds, Yorkshire, England"

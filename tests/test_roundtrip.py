"""Round-trip fidelity: parse -> write -> re-parse must yield the same tree.

This is the core guarantee the whole GEDCOM layer exists to provide, so it
gets its own focused test independent of the database layer.
"""

from genealogy.gedcom.parser import parse_gedcom
from genealogy.gedcom.writer import write_gedcom
from tests.fixtures.sample_gedcom import SAMPLE_GEDCOM
from tests.gedcom_helpers import doc_to_tuple


def test_parse_write_reparse_is_lossless():
    original = parse_gedcom(SAMPLE_GEDCOM)
    exported_text = write_gedcom(original)
    reparsed = parse_gedcom(exported_text)

    assert doc_to_tuple(reparsed) == doc_to_tuple(original)


def test_long_value_is_wrapped_and_unwrapped_symmetrically():
    original = parse_gedcom(SAMPLE_GEDCOM)
    john = original.by_xref("@I1@")
    long_note = john.sub("NOTE")
    assert len(long_note.value) > 255  # exercises CONC wrapping on export

    exported_text = write_gedcom(original)
    assert "\n2 CONC " in exported_text  # confirms wrapping actually happened (NOTE is level 1)

    reparsed = parse_gedcom(exported_text)
    reparsed_note = reparsed.by_xref("@I1@").sub("NOTE")
    assert reparsed_note.value == long_note.value


def test_no_source_line_exceeds_max_length():
    original = parse_gedcom(SAMPLE_GEDCOM)
    exported_text = write_gedcom(original)
    for line in exported_text.splitlines():
        assert len(line) <= 255

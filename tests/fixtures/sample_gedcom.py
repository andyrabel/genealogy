"""Synthetic GEDCOM fixture for tests -- entirely fictional, no real
genealogy data. Kept as a Python string (not a .ged file) so no GEDCOM
files ever exist in the repo, per the project's data-privacy policy.
"""

SAMPLE_GEDCOM = """0 HEAD
1 SOUR GenealogyTestSuite
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
1 DATE 24 JUL 2026
0 @I1@ INDI
1 NAME John /Smith/
2 GIVN John
2 SURN Smith
1 SEX M
1 _UID 12345678-ABCD-EFAB-0000-000000000000
1 BIRT
2 DATE 12 MAR 1850
2 PLAC Leeds, Yorkshire, England
1 DEAT
2 DATE ABT 1920
2 PLAC Leeds, Yorkshire, England
1 FAMS @F1@
1 NOTE A test note with a long line that should be wrapped across multiple CONC continuation lines when exported because it exceeds the two hundred fifty five character line length limit specified by the GEDCOM 5.5.1 standard for a single line of text content padding padding.
1 SOUR @S1@
2 PAGE p. 42
2 QUAY 2
1 FAMC @F2@
0 @I2@ INDI
1 NAME Mary /Jones/
2 GIVN Mary
2 SURN Jones
1 SEX F
1 BIRT
2 DATE 1855
2 PLAC Bradford, Yorkshire, England
1 FAMS @F1@
0 @I3@ INDI
1 NAME Alice /Smith/
2 GIVN Alice
2 SURN Smith
1 SEX F
1 BIRT
2 DATE 5 JUN 1878
2 PLAC Leeds, Yorkshire, England
1 FAMC @F1@
0 @I4@ INDI
1 NAME Unknown /Ancestor/
1 SEX M
0 @I5@ INDI
1 NAME François /Dupônt/
2 GIVN François
2 SURN Dupônt
1 SEX M
1 NOTE Encoding smoke test: É é è ü ö å.
0 @I6@ INDI
1 NAME Unknown /Smith/
2 GIVN Unknown
2 SURN Smith
1 SEX M
1 FAMS @F2@
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
1 CHIL @I3@
1 MARR
2 DATE 3 SEP 1876
2 PLAC Leeds, Yorkshire, England
0 @F2@ FAM
1 HUSB @I6@
1 CHIL @I1@
0 @S1@ SOUR
1 TITL Parish Registers of Leeds, Yorkshire
1 AUTH West Yorkshire Archive Service
1 PUBL Leeds Parish Records, 1850-1900
1 _URL https://example.org/archives/leeds-parish-registers
0 @N1@ NOTE This is a shared note record.
1 CONT It has a second line via CONT.
0 TRLR
"""

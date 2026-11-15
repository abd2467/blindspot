"""RADD date conversion used by `validate radd-prep`."""
from datetime import date

from blindspot.s4_validate.validate import yydoy_to_days


def test_yydoy_to_days():
    epoch = date(2014, 12, 31)
    got = yydoy_to_days([0, 15001, 24366, 26001, 26306]).tolist()
    want = [0, 1, (date(2024, 12, 31) - epoch).days, (date(2026, 1, 1) - epoch).days,
            (date(2026, 11, 2) - epoch).days]
    assert got == want

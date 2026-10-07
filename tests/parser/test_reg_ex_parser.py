

import pytest
from tender_iq.parser.reg_ex_parser import parse_with_regex


@pytest.mark.parametrize("text", [
    "Estimated Bid Value indicated above is guidance on EMD amount.\nEligibility Criteria apply.\n2",
    "2. Estimated Bid Value indicated above is guidance only.\n2",
    "Estimated Bid Value\nNot specified\n2",
])
def test_estimated_value_does_not_use_disclaimer_or_footer(text):
    assert parse_with_regex(text)["estimated_bid_value"] is None


@pytest.mark.parametrize("text", [
    "Estimated Bid Value\n1,786,241.52",
    "/ Estimated Bid Value in INR (Inclusive of all\ntaxes)\n1786241.52",
])
def test_estimated_value_reads_numeric_field(text):
    assert parse_with_regex(text)["estimated_bid_value"] == 1786241.52

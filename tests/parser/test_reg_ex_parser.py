

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


def test_vehicle_type_does_not_use_notice_text():
    text = "Service Description includes Vehicle Type\n\nAs per the buyer requirements"
    assert parse_with_regex(text)["vehicle_type"] is None


def test_vehicle_type_reads_technical_specification():
    text = "Technical Specifications\nSpecification\nValues\nVehicle Type\nPremium Sedan\nYear of Vehicle\n2024"
    assert parse_with_regex(text)["vehicle_type"] == "Premium Sedan"


def test_vehicle_type_does_not_use_wrapped_description_next_field():
    text = "Technical Specifications\nCore\nDescription /Nomenclature of Service\nVehicle Hiring Multiclass\nVehicle Type\nRegulatory/ Statutory Compliance of Service\nYES"
    assert parse_with_regex(text)["vehicle_type"] is None

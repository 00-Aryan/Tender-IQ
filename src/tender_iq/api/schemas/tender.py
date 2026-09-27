# src/tender_iq/api/schemas/tender.py
from pydantic import BaseModel, ConfigDict, Field

# 1. Import domain models directly from your single source of truth
from tender_iq.models.tender_requirements import Dates, FleetSpecification, TenderFinancials


# 2. Upload response contract
class TenderUpload(BaseModel):
    filename: str = Field(..., description="Name of the uploaded PDF file.")
    status: str = Field(..., description="Status of the upload or processing job.")
    tender_id: str | None = Field(
        default=None,
        description="Unique identifier assigned to the tender for subsequent queries.",
    )


# 3. Projected summary contract 
class TenderSummarySpecs(BaseModel):
    model_config = ConfigDict(from_attributes=True)     #enables pydantic to read an instance of your full TenderRequrement=

    bid_id: str | None = Field(
        default=None, description="Unique Bid ID / GeM Tender Number."
    )
    dates: Dates = Field(
        default_factory=Dates, description="Key tender timeline dates."
    )
    financials: TenderFinancials = Field(
        default_factory=TenderFinancials, description="Financial breakdowns and EMD."
    )
    fleet: FleetSpecification = Field(
        default_factory=FleetSpecification, description="Vehicle and fleet requirements."
    )


# 4. Top-level envelope for the /specs endpoint
class TenderSpecs(BaseModel):
    tender_id: str = Field(..., description="Unique tender identifier.")
    status: str = Field(default="processed", description="Status of the tender specs.")
    specs: TenderSummarySpecs = Field(
        ..., description="Projected tender summary specifications."
    )
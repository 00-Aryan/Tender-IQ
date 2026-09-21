from pydantic import BaseModel, Field
from typing import Optional, List 
from datetime import date



class RequiredDocument(BaseModel):
    document_name: Optional[str] = Field(None, description="Name of the required document")
    is_mandatory: Optional[bool] = Field(None, description="True if missing results in rejection or non-responsiveness")
    format_type: Optional[str] = Field(None, description="e.g., PDF, XLS, On Letterhead, Scanned Copy")
    description: Optional[str] = Field(None, description="Detailed requirements, clauses, or specific contents needed inside the document")


class TenderFinancials(BaseModel):
    emd_amount: Optional[float] = None        # earnest money deposit
    emd_currency: Optional[str] = "INR"       # default INR
    working_capital_lakhs: Optional[float] = None
    estimated_bid_value: Optional[float] = None
    diesel_reimbursement_max: Optional[float] = None

class FleetSpecification(BaseModel):
    vehicle_type: Optional[str] = Field(None, description="e.g., Sedan, SUV, 32-Seater Bus, Tipper")
    minimum_quantity: Optional[int] = Field(None, description="Minimum number of vehicles required")
    estimated_km_per_month: Optional[int] = Field(None, description="Monthly estimated distance in KM")
    max_vehicle_age_years: Optional[int] = Field(None, description="Maximum allowed age of vehicle from registration date")
    ownership_required: Optional[bool] = Field(None, description="True if ownership is mandatory, False if leased is allowed")
    scope_of_work: Optional[str] = Field(None, description="what type of work is it where the vehicle will run under whome")

class EligibilityCriteria(BaseModel):
    work_experience_years: Optional[int] = None
    experience_calculation_method: Optional[str] = None
    minimum_experience_value_lakhs: Optional[float] = None
    gst_required: Optional[bool] = None
    gst_conditions: Optional[str] = None
    bid_type: Optional[str] = None  # single/double pack
    working_capital_minimum_lakhs: Optional[float] = None
    jv_allowed: Optional[bool] = None
    jv_minimum_cost_crores: Optional[float] = None

    
    
class Dates(BaseModel):
    submission_deadline : Optional[date] = Field(None, description="Bid submission deadline")
    opening_date : Optional[date] = Field(None, description="Bid Opening date")
    contract_period: Optional[str] = Field(None, description="Contract period as stated, e.g., '2 Year(s)'")
    duration_months: Optional[int] = Field(None, description="Contract duration normalized into months, e.g., 24")

class LegalCompliance(BaseModel):
    written_consent_regarding_arbitration: Optional[str] = Field(
        None, 
        description="Written consent or disclosure regarding arbitration clauses, particularly applicable to partnership firms, Joint Ventures, or Consortia as per Annexure IX."
    )
    integrity_pact: Optional[str] = Field(
        None, 
        description="Pre-contract integrity pact acceptances. Mandatory only if the estimated project cost exceeds Rs. 2.0 Crores."
    )
    code_of_integrity_for_public_procurement: Optional[str] = Field(
        None, 
        description="Acceptance declaration confirmation tracking for the Code of Integrity for Public Procurement (CIPP)."
    )
    restrictions_on_procurement_from_certain_countries: Optional[str] = Field(
        None, 
        description="Compliance certificate or declaration regarding land border sharing and procurement restrictions from specified countries."
    )
    undertaking_for_genuineness_of_information: Optional[str] = Field(
        None, 
        description="Undertaking regarding the absolute genuineness of information furnished and authenticity of uploaded documents as per Annexure VII & VIII."
    )

class TenderRequirements(BaseModel):
    bid_id: Optional[str] = Field(None, description="Unique Bid ID / GeM Tender Number")
    financials: TenderFinancials
    eligibility: EligibilityCriteria
    fleet: FleetSpecification
    documents: List[RequiredDocument]
    dates: Dates
    compliance: LegalCompliance
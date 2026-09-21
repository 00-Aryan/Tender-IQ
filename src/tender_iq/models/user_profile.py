from pydantic import BaseModel, Field , HttpUrl, EmailStr ,model_validator
from typing import Optional, List
from enum import Enum
from datetime import date



class User(BaseModel):
    name: str = Field(..., description="Name of the user")
    email: Optional[EmailStr] = Field(..., description="Email of the user")

    

class UserDoc(BaseModel):
    document_name: str
    is_available: bool = False

class Vehicle(BaseModel):
    vehicle_type: Optional[str] = Field(None, description="e.g., Sedan, SUV, 32-Seater Bus, Tipper")
    vehicle_number: Optional[str] = Field(None, description="Registration number of the vehicle")
    vehicle_make: Optional[str] = Field(None, description="Manufacturer name (e.g., Tata, Mahindra)")
    vehicle_model: Optional[str] = Field(None, description="Model variant")
    vehicle_year: Optional[int] = Field(None, ge=1900, le=2026, description="Manufacturing year context limits")
    vehicle_owner: Optional[str] = Field(None, description="Owner name as printed on RC")
    # vehicle_documents: List[DocumentMetadata] = Field(default=[], description="List of RC copies, insurance policies, permits") 

class WorkOrder(BaseModel):
    work_description: Optional[str] = Field(None, description="details of work done")
    employer_name: Optional[str] = Field(None, description="under which company vehicle is running")
    contract_value_inr: Optional[float] = Field(None, description="what was the value of the contract")
    completion_year: Optional[int] = Field(None, description="when will it be completed")
    duration_months: Optional[int] = Field(None, description="hiring time period of vehicle")


class UserProfile(BaseModel):
    user_details: User
    vehicle_info: List[Vehicle]
    years_in_business: int
    annual_turnover_lakhs: float
    past_work_orders: List[WorkOrder] = Field(default=[])
    documents_available: List[UserDoc] = Field(default=[])
    working_capital_lakhs: float
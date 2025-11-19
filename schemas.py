"""
Hospital Management Schemas

Each Pydantic model below represents a MongoDB collection. The collection
name is the lowercase of the class name.

Example: class User -> collection "user"
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Unique email address")
    role: str = Field(..., description="Role: doctor | patient | admin")
    phone: Optional[str] = Field(None)

class DoctorProfile(BaseModel):
    user_id: str = Field(..., description="Reference to user _id (doctor)")
    specialty: Optional[str] = None
    rate_per_point: float = Field(100.0, ge=0, description="Salary rate per point")

class PatientProfile(BaseModel):
    user_id: str = Field(..., description="Reference to user _id (patient)")
    dob: Optional[str] = None
    insurance_policy_id: Optional[str] = Field(None, description="Reference to InsurancePolicy")

class Availability(BaseModel):
    doctor_id: str = Field(..., description="User id of doctor")
    week_start: str = Field(..., description="ISO date string (Monday of week)")
    available_slots: List[str] = Field(default_factory=list, description="List of ISO datetime strings")

class Unavailability(BaseModel):
    doctor_id: str
    date: str = Field(..., description="ISO date string doctor unavailable")
    reason: Optional[str] = None

class Operation(BaseModel):
    name: str
    base_price: float = Field(..., ge=0)

class Roomtype(BaseModel):
    name: str = Field(..., description="super-deluxe | deluxe | normal")
    price_per_day: float = Field(..., ge=0)

class Insurancepolicy(BaseModel):
    name: str
    allowed_roomtypes: List[str] = Field(default_factory=list, description="List of room type names allowed")
    coverage_percent: float = Field(0, ge=0, le=100, description="% coverage on operation price")

class Appointment(BaseModel):
    patient_id: str
    doctor_id: str
    scheduled_at: str = Field(..., description="ISO datetime string")
    reason: Optional[str] = None
    operation_id: Optional[str] = None
    roomtype_name: Optional[str] = None
    status: str = Field("scheduled", description="scheduled | completed | cancelled")
    payment_method: Optional[str] = Field(None, description="online | cod")
    payment_status: str = Field("pending", description="pending | paid | failed")

class Prescription(BaseModel):
    appointment_id: str
    doctor_id: str
    patient_id: str
    notes: Optional[str] = None
    medications: List[str] = Field(default_factory=list)
    follow_up_date: Optional[str] = None

class Billing(BaseModel):
    appointment_id: str
    subtotal: float
    insurance_discount: float = 0.0
    total: float
    details: Optional[dict] = None

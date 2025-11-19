import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import (
    User, DoctorProfile, PatientProfile, Availability, Unavailability,
    Appointment, Prescription, Billing, Insurancepolicy, Operation, Roomtype
)

app = FastAPI()

# CORS: we don't use cookies, so credentials can be False. This allows wildcard origins safely.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility

def to_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")

# Auth (basic placeholder for roles)
class LoginRequest(BaseModel):
    email: str
    role: str

@app.post("/api/login")
async def login(req: LoginRequest):
    user = db["user"].find_one({"email": req.email, "role": req.role})
    if not user:
        # auto register simple flow for demo
        user_id = create_document("user", {"name": req.email.split("@")[0], "email": req.email, "role": req.role})
        user = db["user"].find_one({"_id": ObjectId(user_id)})
        if req.role == "doctor":
            create_document("doctorprofile", {"user_id": user_id, "specialty": None, "rate_per_point": 100.0})
        if req.role == "patient":
            create_document("patientprofile", {"user_id": user_id})
    user["_id"] = str(user["_id"]) if "_id" in user else None
    return {"user": user}

# Doctors
@app.get("/api/doctors")
async def list_doctors():
    users = get_documents("user", {"role": "doctor"})
    for u in users:
        u["_id"] = str(u["_id"]) 
    return users

@app.get("/api/doctor/{doctor_id}/appointments")
async def doctor_appointments(doctor_id: str):
    items = get_documents("appointment", {"doctor_id": doctor_id})
    for d in items:
        d["_id"] = str(d["_id"]) 
    return items

@app.get("/api/doctor/{doctor_id}/stats")
async def doctor_stats(doctor_id: str):
    completed = list(db["appointment"].find({"doctor_id": doctor_id, "status": "completed"}))
    count = len(completed)
    # points = number of completed appointments for now
    points = count
    profile = db["doctorprofile"].find_one({"user_id": doctor_id})
    rate = profile.get("rate_per_point", 100.0) if profile else 100.0
    salary = points * rate
    return {"treated_patients": count, "points": points, "salary": salary}

class AvailabilityRequest(BaseModel):
    week_start: str
    available_slots: List[str]

@app.post("/api/doctor/{doctor_id}/availability")
async def set_availability(doctor_id: str, body: AvailabilityRequest):
    create_document("availability", {"doctor_id": doctor_id, "week_start": body.week_start, "available_slots": body.available_slots})
    return {"status": "ok"}

class UnavailabilityRequest(BaseModel):
    date: str
    reason: Optional[str] = None

@app.post("/api/doctor/{doctor_id}/unavailability")
async def add_unavailability(doctor_id: str, body: UnavailabilityRequest):
    create_document("unavailability", {"doctor_id": doctor_id, "date": body.date, "reason": body.reason})
    return {"status": "ok"}

@app.get("/api/doctor/{doctor_id}/patients")
async def doctor_patients(doctor_id: str):
    # patients with appointments with this doctor
    pats = db["appointment"].find({"doctor_id": doctor_id})
    patient_ids = {a["patient_id"] for a in pats}
    patients = list(db["user"].find({"_id": {"$in": [ObjectId(pid) for pid in patient_ids if ObjectId.is_valid(pid)]}}))
    for p in patients:
        p["_id"] = str(p["_id"]) 
    return patients

@app.get("/api/patient/{patient_id}/history")
async def patient_history(patient_id: str):
    appts = list(db["appointment"].find({"patient_id": patient_id}))
    for a in appts:
        a["_id"] = str(a["_id"]) 
    prescriptions = list(db["prescription"].find({"patient_id": patient_id}))
    for pr in prescriptions:
        pr["_id"] = str(pr["_id"]) 
    return {"appointments": appts, "prescriptions": prescriptions}

# Patients
class AppointmentRequest(BaseModel):
    doctor_id: str
    scheduled_at: str
    reason: Optional[str] = None
    payment_method: Optional[str] = None

@app.get("/api/patients")
async def list_patients():
    users = get_documents("user", {"role": "patient"})
    for u in users:
        u["_id"] = str(u["_id"]) 
    return users

@app.post("/api/patient/{patient_id}/appointments")
async def create_appointment(patient_id: str, body: AppointmentRequest):
    appt_id = create_document("appointment", {
        "patient_id": patient_id,
        "doctor_id": body.doctor_id,
        "scheduled_at": body.scheduled_at,
        "reason": body.reason,
        "status": "scheduled",
        "payment_method": body.payment_method,
        "payment_status": "pending"
    })
    return {"appointment_id": appt_id}

@app.get("/api/patient/{patient_id}/appointments")
async def get_patient_appointments(patient_id: str):
    items = get_documents("appointment", {"patient_id": patient_id})
    for d in items:
        d["_id"] = str(d["_id"]) 
    return items

# Prescriptions
class PrescriptionRequest(BaseModel):
    appointment_id: str
    notes: Optional[str] = None
    medications: List[str] = []
    follow_up_date: Optional[str] = None

@app.post("/api/doctor/{doctor_id}/prescription")
async def add_prescription(doctor_id: str, body: PrescriptionRequest):
    appt = db["appointment"].find_one({"_id": ObjectId(body.appointment_id)})
    if not appt:
        raise HTTPException(404, "Appointment not found")
    presc_id = create_document("prescription", {
        "appointment_id": body.appointment_id,
        "doctor_id": doctor_id,
        "patient_id": appt["patient_id"],
        "notes": body.notes,
        "medications": body.medications,
        "follow_up_date": body.follow_up_date
    })
    return {"prescription_id": presc_id}

@app.get("/api/prescription/{appointment_id}")
async def get_prescription_by_appointment(appointment_id: str):
    items = list(db["prescription"].find({"appointment_id": appointment_id}))
    for i in items:
        i["_id"] = str(i["_id"]) 
    return items

# Payments & Billing
class PaymentUpdate(BaseModel):
    status: str

@app.post("/api/appointment/{appointment_id}/payment")
async def update_payment(appointment_id: str, body: PaymentUpdate):
    db["appointment"].update_one({"_id": ObjectId(appointment_id)}, {"$set": {"payment_status": body.status}})
    return {"status": "ok"}

class BillingRequest(BaseModel):
    operation_id: Optional[str] = None
    roomtype_name: Optional[str] = None

@app.post("/api/appointment/{appointment_id}/bill")
async def generate_bill(appointment_id: str, body: BillingRequest):
    appt = db["appointment"].find_one({"_id": ObjectId(appointment_id)})
    if not appt:
        raise HTTPException(404, "Appointment not found")

    subtotal = 0.0
    details = {}

    if body.operation_id:
        op = db["operation"].find_one({"_id": ObjectId(body.operation_id)})
        if not op:
            raise HTTPException(404, "Operation not found")
        subtotal += float(op.get("base_price", 0))
        details["operation"] = {"name": op.get("name"), "price": float(op.get("base_price", 0))}

    if body.roomtype_name:
        room = db["roomtype"].find_one({"name": body.roomtype_name})
        if not room:
            raise HTTPException(404, "Room type not found")
        subtotal += float(room.get("price_per_day", 0))
        details["room"] = {"name": room.get("name"), "price": float(room.get("price_per_day", 0))}

    # Insurance check via patient's policy
    patient = db["patientprofile"].find_one({"user_id": appt["patient_id"]})
    discount = 0.0
    if patient and patient.get("insurance_policy_id"):
        pol = db["insurancepolicy"].find_one({"_id": ObjectId(patient["insurance_policy_id"])})
        if pol:
            # room eligibility
            if body.roomtype_name and body.roomtype_name not in pol.get("allowed_roomtypes", []):
                details["insurance_note"] = "Selected room type not covered by insurance"
            coverage = float(pol.get("coverage_percent", 0))
            discount = subtotal * (coverage / 100.0)

    total = max(0.0, subtotal - discount)
    bill_id = create_document("billing", {
        "appointment_id": appointment_id,
        "subtotal": subtotal,
        "insurance_discount": discount,
        "total": total,
        "details": details
    })
    return {"billing_id": bill_id, "subtotal": subtotal, "discount": discount, "total": total, "details": details}

# Admin utilities
class AdminScheduleRequest(BaseModel):
    patient_id: str
    doctor_id: str
    scheduled_at: str
    reason: Optional[str] = None

@app.post("/api/admin/appointments")
async def admin_create_appointment(body: AdminScheduleRequest):
    appt_id = create_document("appointment", {
        "patient_id": body.patient_id,
        "doctor_id": body.doctor_id,
        "scheduled_at": body.scheduled_at,
        "reason": body.reason,
        "status": "scheduled",
        "payment_status": "pending"
    })
    return {"appointment_id": appt_id}

@app.get("/api/admin/availability/{doctor_id}")
async def admin_get_availability(doctor_id: str):
    avail = list(db["availability"].find({"doctor_id": doctor_id}))
    for a in avail:
        a["_id"] = str(a["_id"]) 
    return avail

@app.get("/api/admin/billing/{appointment_id}")
async def admin_get_billing(appointment_id: str):
    bills = list(db["billing"].find({"appointment_id": appointment_id}))
    for b in bills:
        b["_id"] = str(b["_id"]) 
    return bills

@app.post("/api/admin/payment/cod/{appointment_id}")
async def admin_mark_cod_paid(appointment_id: str):
    db["appointment"].update_one({"_id": ObjectId(appointment_id)}, {"$set": {"payment_method": "cod", "payment_status": "paid"}})
    return {"status": "ok"}

# Master data for operations/rooms/insurance
class OperationCreate(BaseModel):
    name: str
    base_price: float

@app.post("/api/admin/operation")
async def create_operation(body: OperationCreate):
    op_id = create_document("operation", body.model_dump())
    return {"operation_id": op_id}

class RoomCreate(BaseModel):
    name: str
    price_per_day: float

@app.post("/api/admin/roomtype")
async def create_roomtype(body: RoomCreate):
    room_id = create_document("roomtype", body.model_dump())
    return {"roomtype_id": room_id}

class InsuranceCreate(BaseModel):
    name: str
    allowed_roomtypes: List[str] = []
    coverage_percent: float = 0

@app.post("/api/admin/insurance")
async def create_insurance(body: InsuranceCreate):
    ins_id = create_document("insurancepolicy", body.model_dump())
    return {"insurance_policy_id": ins_id}

@app.get("/")
async def root():
    return {"message": "Hospital Management Backend running"}

@app.get("/test")
async def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

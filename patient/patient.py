from fastapi import HTTPException, Query
from dotenv import load_dotenv
from pymongo import MongoClient  
import os 
from datetime import datetime, timedelta, timezone
from dateutil import parser
from dateutil.relativedelta import relativedelta
from fastapi.responses import JSONResponse
from app_instance import app




load_dotenv()


MONGODB_CONNECTION_STRING = os.getenv("MONGODB_CONNECTION_STRING")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
DOCTORS_COLLECTION = os.getenv("DOCTORS_COLLECTION")

client = MongoClient(MONGODB_CONNECTION_STRING)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]
doctors_collection = db[DOCTORS_COLLECTION]


# API to get total counts
@app.get("/api/patient/total_counts")
def total_counts():
    try:
        # ---------------- TOTAL PATIENTS ----------------
        total_patients = collection.count_documents({})

        # ---------------- TOTAL APPOINTMENTS ----------------
        # Count medications inside each patient document
        total_appointments = 0
        all_patients = collection.find({}, {"medications": 1, "registered_at": 1})

        # Variables reused for other parts
        new_patients = 0
        risk_summary  = {}

        now = datetime.now(timezone.utc)
        current_year_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
        current_year_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)

        for p in all_patients:
            medications = p.get("medications", {})
            patient_id = p.get("_id")

            # ---------- TOTAL APPOINTMENTS ----------
            if isinstance(medications, dict):
                total_appointments += len(medications)

            # ---------- NEW PATIENTS ----------
            reg = p.get("registered_at")
            if reg:
                try:
                    dt = parser.parse(reg)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if current_year_start <= dt < current_year_end:
                        new_patients += 1
                except:
                    pass

            # ---------- LATEST RISK VALUE ----------
            latest_time = None
            latest_risk = None

            for key, med in medications.items():
                try:
                    med_time = parser.parse(med.get("time"))
                    if med_time.tzinfo is None:
                        med_time = med_time.replace(tzinfo=timezone.utc)

                    if (latest_time is None) or (med_time > latest_time):
                        latest_time = med_time
                        latest_risk = int(med.get("riskrate", 0))

                except:
                    continue

            if latest_risk is not None:
                risk_summary [patient_id] = latest_risk

        # ---------------- RISK CATEGORY SUMMARY ----------------
        low_risk = mid_risk = high_risk = 0

        for risk in risk_summary.values():
            if risk <= 45:
                low_risk += 1
            elif 46 <= risk <= 75:
                mid_risk += 1
            else:
                high_risk += 1

        # ---------------- FINAL RESPONSE ----------------
        return {
            "total_patients": total_patients,
            "total_appointments": total_appointments,
            "new_patients": new_patients,
            "risk_summary": {
                "low_risk": low_risk,
                "mid_risk": mid_risk,
                "high_risk": high_risk
            }
        }

    except Exception as e:
        raise HTTPException(500, f"Internal Server Error: {str(e)}")


# API to fetch list of patients
@app.get("/api/patient/patients_list")
async def patients_list():

    try:
        patients_details = collection.find({})
        patients_list = []

        si_no = 1

        for patient in patients_details:

            medications = patient.get("medications", {})

            # If no medications exist
            if medications:
                
                latest_medication = sorted(medications.keys())[-1]
                last_medication = medications[latest_medication]

                last_updated = last_medication.get("time")
                risk_score = last_medication.get("riskrate")
            else:
                last_updated = None
                risk_score = None

            patients_list.append({
                "si_no": si_no,
                "patient_id": str(patient.get("patientid", "")),
                "name": patient.get("name", ""),
                "gender": patient.get("gender", ""),
                "last_updated": last_updated,
                "risk_score": risk_score
            })

            si_no += 1

        return patients_list

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching patient details: {str(e)}"
        )
    

# API to fetch list of doctors
@app.get("/api/doctors/doctors_list")
async def doctors_list():
    try:
        doctors_details = doctors_collection.find({})
        doctors_list = []

        for doctor in doctors_details:
            doctors_list.append({
                
                
                "name": doctor.get("name", ""),
                "specialisation": doctor.get("specialisation", "")
                
            })

        return  doctors_list
        

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/api/patient/appointments_by_date")
async def appointments_by_date(date: str = Query(..., description="Format: YYYY-MM-DD")):
    try:
        # Convert date
        try:
            selected_date = datetime.strptime(date, "%Y-%m-%d")
        except:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")

        start = selected_date.isoformat()
        end = (selected_date + timedelta(days=1)).isoformat()

        #  Fetch ALL patients (only required fields)
        patients = collection.find({}, {"patientid": 1, "medications": 1})

        doctor_counts = {}  # doctor_id → {name, specialisation, count}

        #  Loop through each patient and manually process medications
        for p in patients:
            meds = p.get("medications", {})
            if not meds:
                continue

            # Convert medications object → python dictionary iteration
            for key, med_data in meds.items():
                meeting = med_data.get("meeting_details")
                if not meeting:
                    continue

                doc_id = meeting.get("doctor_id")
                meeting_time = meeting.get("meeting_datetime")

                if not doc_id or not meeting_time:
                    continue

                # Check date range
                if start <= meeting_time < end:
                    # Fetch doctor info manually (NO $lookup)
                    doctor = doctors_collection.find_one(
                        {"doctor_id": doc_id},
                        {"_id": 0, "name": 1, "specialisation": 1}
                    )

                    if not doctor:
                        continue

                    #  Group and count manually (NO $group)
                    if doc_id not in doctor_counts:
                        doctor_counts[doc_id] = {
                            "doctor_name": doctor["name"],
                            "specialisation": doctor["specialisation"],
                            "appointment_count": 1
                        }
                    else:
                        doctor_counts[doc_id]["appointment_count"] += 1

        # Convert dictionary to list
        result = list(doctor_counts.values())

        # Sort alphabetically (NO $sort)
        result.sort(key=lambda x: x["doctor_name"])

        if not result:
            return {"message": "No doctor appointments found for this date."}

        return result

    except Exception as e:
        raise HTTPException(500, f"Internal Server Error: {str(e)}")



@app.get("/api/patient/monthly_reports")
async def monthly_reports():
    try:
        today = datetime.utcnow()

        # Start of this month
        start_of_month = datetime(today.year, today.month, 1)
        # Start of next month
        if today.month == 12:
            start_of_next_month = datetime(today.year + 1, 1, 1)
        else:
            start_of_next_month = datetime(today.year, today.month + 1, 1)

        start = start_of_month.isoformat()
        end = start_of_next_month.isoformat()

        #  Fetch all patients
        patients = collection.find({}, {"patientid": 1, "medications": 1})

        # doctor_id → {name, specialisation, count}
        doctor_summary = {}

        #  Loop through each patient
        for p in patients:
            meds = p.get("medications", {})
            if not meds:
                continue

            # Convert medications object into loopable items
            for key, med in meds.items():
                meeting = med.get("meeting_details")
                if not meeting:
                    continue

                doctor_id = meeting.get("doctor_id")
                meeting_time = meeting.get("meeting_datetime")

                if not doctor_id or not meeting_time:
                    continue

                # Filter meetings falling in this month
                if not (start <= meeting_time < end):
                    continue

                #  Fetch doctor info (replaces $lookup)
                doctor = doctors_collection.find_one(
                    {"doctor_id": doctor_id},
                    {"_id": 0, "name": 1, "specialisation": 1}
                )
                if not doctor:
                    continue

                #  Count appointments (replaces $group)
                if doctor_id not in doctor_summary:
                    doctor_summary[doctor_id] = {
                        "doctor_name": doctor["name"],
                        "specialisation": doctor["specialisation"],
                        "appointment_count": 1
                    }
                else:
                    doctor_summary[doctor_id]["appointment_count"] += 1

        #  Convert dictionary → list
        results = list(doctor_summary.values())

        #  Sort by appointment count (replaces $sort)
        results.sort(key=lambda x: x["appointment_count"], reverse=True)

        return results

    except Exception as e:
        raise HTTPException(500, f"Internal Server Error: {str(e)}")

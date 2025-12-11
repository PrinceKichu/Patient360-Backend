from fastapi import HTTPException
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from datetime import datetime, timezone
from calendar import month_name as calendar_month_name
import calendar
from app_instance import app




load_dotenv()

MONGODB_CONNECTION_STRING = os.getenv("MONGODB_CONNECTION_STRING")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")


client = MongoClient(MONGODB_CONNECTION_STRING)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]


# API for patient dashboard
@app.get("/api/patient/dashboard/{patientid}")
async def get_patient_dashboard(patientid: str):
    try:
        # Convert patientid to int
        try:
            patient_id = int(patientid)
        except:
            raise HTTPException(status_code=400, detail="patientid must be a number")

        # Fetch patient basic info
        patient = collection.find_one(
            {"patientid": patient_id},
            {"_id": 0, "patientid": 1, "name": 1, "gender": 1, "medications": 1}
        )

        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        medications = patient.get("medications", {})

        if not medications:
            raise HTTPException(status_code=404, detail="No medication records found")

        # Initialize with offset-aware datetime
        latest_med = None
        latest_time = datetime.min.replace(tzinfo=timezone.utc)

        
        for med in medications.values():
            time_str = med.get("time")
            if not time_str:
                continue

            # Convert to timezone-aware UTC datetime
            try:
                dt = datetime.fromisoformat(
                    time_str.replace("Z", "+00:00")
                ).astimezone(timezone.utc)
            except:
                continue

      
            if dt > latest_time:
                latest_time = dt
                latest_med = med

        if not latest_med:
            raise HTTPException(status_code=404, detail="No valid medication timestamps")

        # Prepare final dashboard response
        dashboard_data = {
            "patientid": patient["patientid"],
            "name": patient["name"],
            "gender": patient.get("gender"),
            "bp": latest_med.get("bp"),
            "age": latest_med.get("age"),
            "heartrate": latest_med.get("heartrate"),
            "SpO2": latest_med.get("SpO2"),
            "Stress": latest_med.get("Stress"),
            "Respiratoryrate": latest_med.get("Respiratoryrate"),
            "riskrate": latest_med.get("riskrate"),
        }

        return dashboard_data

    except Exception as e:
        print("ERROR:", e)
        raise HTTPException(status_code=500, detail=str(e))




def month_name(month_number: int):
    return calendar.month_name[month_number]

# API for patient dashboard risk rates by month
@app.get("/api/patient/patient_dashboard_risk/{patientid}")
def get_dashboard_patient_risk(patientid: str):

    # Convert patientid
    try:
        patient_id = int(patientid)
    except:
        raise HTTPException(status_code=400, detail="patientid must be a number")

    # Fetch patient document
    patient = collection.find_one({"patientid": patient_id})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Initialize month buckets
    month_risks = {calendar_month_name[i]: [] for i in range(1, 13)}

    # Extract medications
    medications = patient.get("medications", {})

    for med in medications.values():
        risk = med.get("riskrate")
        time_str = med.get("time")

        if risk is not None and time_str:
            # Convert time
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            month = calendar_month_name[dt.month]

            month_risks[month].append(risk)

    # Compute averages
    avg_monthly_risk = [
        {
            "month": month,
            "average_riskrate": round(sum(risks) / len(risks), 2) if risks else None
        }
        for month, risks in month_risks.items()
    ]

    return avg_monthly_risk


# API for patient health trend
@app.get("/api/patient/patient_health_trend/{patientid}")
def get_patient_health_trend(patientid: str):
    # Convert patientid to int
    try:
        patient_id = int(patientid)
    except:
        raise HTTPException(status_code=400, detail="patientid must be a number")

    # Fetch patient record
    patient_records = collection.find_one({"patientid": patient_id})
    if not patient_records:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Initialize months
    monthly_data = {
      calendar_month_name[i]: {"heartrate": None, "SpO2": None, "Stress": None, "systolic": None, "diastolic": None}
      for i in range(1, 13)
}


    # Iterate medications
    medications = patient_records.get("medications", {})
    for med in medications.values():
        # Convert medication timestamp
        time_str = med.get("time")
        if not time_str:
            continue
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        month = calendar_month_name[dt.month]

        # Extract values
        hr = med.get("heartrate")
        sp = med.get("SpO2")
        stress = med.get("Stress")
        bp = med.get("bp")
        systolic = diastolic = None
        if bp and "/" in bp:
            try:
                systolic, diastolic = map(int, bp.split("/"))
            except:
                systolic, diastolic = None, None

        
        if monthly_data[month]["heartrate"] is None:
            monthly_data[month]["heartrate_list"] = []
            monthly_data[month]["SpO2_list"] = []
            monthly_data[month]["Stress_list"] = []
            monthly_data[month]["systolic_list"] = []
            monthly_data[month]["diastolic_list"] = []

        # Append values
        if hr is not None:
            monthly_data[month]["heartrate_list"].append(float(str(hr).replace("bpm","").strip()))
        if sp is not None:
            monthly_data[month]["SpO2_list"].append(float(str(sp).replace("%","").strip()))
        if stress is not None:
            monthly_data[month]["Stress_list"].append(float(str(stress).strip()))
        if systolic is not None:
            monthly_data[month]["systolic_list"].append(systolic)
        if diastolic is not None:
            monthly_data[month]["diastolic_list"].append(diastolic)

    # Compute averages
    for month, data in monthly_data.items():
        for key, lst_key in [("heartrate", "heartrate_list"), ("SpO2", "SpO2_list"),
                             ("Stress", "Stress_list"), ("systolic", "systolic_list"), ("diastolic", "diastolic_list")]:
            if lst_key in data and data[lst_key]:
                monthly_data[month][key] = round(sum(data[lst_key])/len(data[lst_key]), 2)
            else:
                monthly_data[month][key] = None
            # Remove temporary lists
            if lst_key in data:
                del data[lst_key]

    return monthly_data


# API for patient average actual vs healthy levels
@app.get("/api/patient/average_actual/{patientid}")
def get_patient_average_actual(patientid: str):
    try:
        patientid_int = int(patientid)
    except:
        raise HTTPException(status_code=400, detail="patientid must be a number")

    # Fetch patient document
    patient = collection.find_one({"patientid": patientid_int})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Get latest medication
    medications = patient.get("medications", {})
    if not medications:
        raise HTTPException(status_code=404, detail="No medications found for this patient")

    latest_med_key = sorted(medications.keys())[-1]
    latest_med = medications[latest_med_key]

    # Helper to convert values
    def to_float(value):
        if value is None:
            return None
        try:
            clean = str(value).replace("%", "").replace("bpm", "").strip()
            if "/" in clean:  # For BP, take systolic only
                clean = clean.split("/")[0]
            return float(clean)
        except:
            return None

    # Actual patient values from latest medication
    actual_hr = to_float(latest_med.get("heartrate"))
    actual_spo2 = to_float(latest_med.get("SpO2"))
    actual_bp = latest_med.get("bp")  # Keep as string

    # Define standard healthy levels
    healthy = {
        "heartrate": 80,   # midpoint of 60-100
        "SpO2": 97.5,      # midpoint of 95-100
        "bp": "120/80"
    }

    return {
        "actual": {
            "heartrate": actual_hr,
            "SpO2": actual_spo2,
            "bp": actual_bp
        },
        "average": {
            "heartrate": healthy["heartrate"],
            "SpO2": healthy["SpO2"],
            "bp": healthy["bp"]
        }
       
    }


#Define healthy ranges
HEALTHY_HR = (60, 100)
HEALTHY_SPO2 = 95
HEALTHY_BP = (90, 120)


# Functions to calculate risk percentages
def calc_hr_risk(hr):
    if hr is None:
        return None
    low, high = HEALTHY_HR
    if low <= hr <= high:
        return 0
    if hr < low:
        return round(((low - hr) / low) * 100, 2)
    return round(((hr - high) / high) * 100, 2)

def calc_spo2_risk(sp):
    if sp is None:
        return None
    if sp >= HEALTHY_SPO2:
        return 0
    return round(((HEALTHY_SPO2 - sp) / HEALTHY_SPO2) * 100, 2)

def calc_bp_risk(bp):
    if bp is None:
        return None
    low, high = HEALTHY_BP
    if low <= bp <= high:
        return 0
    if bp < low:
        return round(((low - bp) / low) * 100, 2)
    return round(((bp - high) / high) * 100, 2)


# API for patient risk scores weightage
@app.get("/api/patient/risk_scores_weightage/{patientid}")
async def get_risk_score_weightage(patientid: str):
    # Convert patientid to int
    try:
        patient_id = int(patientid)
    except:
        raise HTTPException(status_code=400, detail="patientid must be a number")

    # Fetch patient
    patient = collection.find_one({"patientid": patient_id})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Get medications
    medications = patient.get("medications", {})
    if not medications:
        raise HTTPException(status_code=404, detail="No medications found for this patient")

    # Find latest medication (based on time)
    latest_med = None
    latest_time = None

    for med in medications.values():
        time_str = med.get("time")
        if not time_str:
            continue
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        if latest_time is None or dt > latest_time:
            latest_time = dt
            latest_med = med

    if not latest_med:
        raise HTTPException(status_code=404, detail="No valid medication timestamps")

    # Helper to convert values
    def to_float(v):
        if v is None:
            return None
        try:
            v = str(v).replace("%", "").replace("bpm", "").strip()
            if "/" in v:
                v = v.split("/")[0]  # systolic only
            return float(v)
        except:
            return None

    hr_value = to_float(latest_med.get("heartrate"))
    spo2_value = to_float(latest_med.get("SpO2"))
    bp_value = to_float(latest_med.get("bp"))  # systolic

    return {
        "heartrate": {
            "risk_percent": calc_hr_risk(hr_value)
        },
        "SpO2": {
            "risk_percent": calc_spo2_risk(spo2_value)
        },
        "blood_pressure": {
            "risk_percent": calc_bp_risk(bp_value)
        },
     
    }


# API for patient recommendations
@app.get("/api/patient/recommendations/{patientid}")
def get_recommendations(patientid: int):
    # Fetch patient
    patient = collection.find_one({"patientid": patientid}, {"_id": 0, "medications": 1})
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    medications = patient.get("medications", {})
    if not medications:
        raise HTTPException(status_code=404, detail="No medications found for this patient")
    
    # Get latest medication (based on key order)
    latest_med_key = sorted(medications.keys())[-1]
    latest_med = medications[latest_med_key]

    return {
        "Diet_PLAN": latest_med.get("Diet_PLAN"),
        "Exercise_PLAN": latest_med.get("Exercise_PLAN"),
        "Routine_PLAN": latest_med.get("Routine_PLAN")
    }


@app.get("/api/patient/episodes/{patientid}")
def get_previous_episodes(patientid: int):

    patient = collection.find_one({"patientid": patientid}, {"_id": 0, "medications": 1})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    medications = patient.get("medications", {})
    if not medications:
        raise HTTPException(status_code=404, detail="No medications found for this patient")

    episodes = []

    # FIXED: unpack key, value
    for key, med in medications.items():
        episode = {
            "heartrate": med.get("heartrate"),
            "SpO2": med.get("SpO2"),
            "Respiratoryrate": med.get("Respiratoryrate"),
            "bp": med.get("bp"),
            "riskrate": med.get("riskrate"),
            "time": med.get("time"),
            "type": med.get("type")
        }
        episodes.append(episode)

    # Sort by time desc
    episodes.sort(key=lambda x: x["time"], reverse=True)

    # Add serial numbers
    for index, episode in enumerate(episodes, start=1):
        episode["sno"] = index

    return episodes


# API for prescription tracking
@app.get("/api/patient/{patientid}/prescription_tracking")
async def prescription_tracking(patientid: str):
    try:
        # Convert patientid to int for correct MongoDB match
        patient_id_int = int(patientid)

        # Fetch patient document from MongoDB
        patient = collection.find_one({"patientid": patient_id_int})
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        # Get all medications
        medications = patient.get("medications", {})
        if not medications:
            raise HTTPException(status_code=404, detail="No medications found for this patient")

       # Build prescription tracking structure
        prescription_tracking = {}

        for med_key, med_value in medications.items():
            diet = med_value.get("Diet_PLAN", {})
            exercise = med_value.get("Exercise_PLAN", {})
            routine = med_value.get("Routine_PLAN", {})

            med_plan = {}
            for day in range(1, 8):
                key = f"DAY{day}"
                med_plan[key] = {
                    "Diet": diet.get(key),
                    "Exercise": exercise.get(key),
                    "Routine": routine.get(key)
                }

            prescription_tracking[med_key] = med_plan

        return prescription_tracking

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


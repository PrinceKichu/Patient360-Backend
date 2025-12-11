from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime, timedelta, timezone
from functions.send_whatsapp_msg import send_greeting_message, send_template_message, send_whatsapp_message
from templates.ada_templates import get_template_name
import os
import asyncio
import smtplib
from calendar import month_name as calendar_month_name
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from utils.google_calendar import create_google_meet_event
from app_instance import app


import patient.patient
import patient.patient_dashboard





app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
load_dotenv()
 
MONGODB_CONNECTION_STRING = os.getenv("MONGODB_CONNECTION_STRING")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
HISTORY_COLLECTION = os.getenv("HISTORY_COLLECTION")
APPOINTMENTS_COLLECTION = os.getenv("APPOINTMENTS_COLLECTION")
DOCTORS_COLLECTION = os.getenv("DOCTORS_COLLECTION")
DASHBOARD_COLLECTION = os.getenv("DASHBOARD_COLLECTION")

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
 
# Initialize MongoDB client
client = MongoClient(MONGODB_CONNECTION_STRING)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]
meeting_history_collection = db[HISTORY_COLLECTION]
appointments_collection = db[APPOINTMENTS_COLLECTION]  
doctors_collection = db[DOCTORS_COLLECTION]
dashboard_collection = db[DASHBOARD_COLLECTION]





def send_meeting_email(patient_name, patient_email, meeting_datetime, meet_link):
    """Send email with meeting details to patient"""
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = patient_email
        msg['Subject'] = f"Health Consultation Meeting Scheduled - {patient_name}"
        
        # Format datetime
        meeting_dt = datetime.fromisoformat(meeting_datetime)
        formatted_datetime = meeting_dt.strftime('%B %d, %Y at %I:%M %p')
        
        # Create email body
        body = f"""Dear {patient_name},

Your health consultation meeting has been scheduled successfully!

Meeting Details:
📅 Date & Time: {formatted_datetime} (IST)
⏱️ Duration: 1 hour
🏥 Type: Health Consultation

Join the meeting using this link:
🔗 {meet_link}

Meeting ID: {meet_link.split('/')[-1]}

How to Join:
• Click the meeting link above
• Or go to meet.google.com and enter the Meeting ID
• Join 5 minutes before the scheduled time

Important Notes:
• Ensure you have a stable internet connection
• Keep your medical records ready for discussion
• Test your camera and microphone beforehand
• If you face any technical issues, contact us immediately

Preparation for the Meeting:
• Have your medical history ready
• List of current medications
• Any specific questions or concerns
• A quiet, well-lit space for the video call

If you need to reschedule or have any questions, please contact us at {EMAIL_ADDRESS}

Best regards,
Health Care Team
Patient360

---
This is an automated message. Please do not reply to this email.
If you need immediate assistance, contact our support team.
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_ADDRESS, patient_email, text)
        server.quit()
        
        print(f"✅ Meeting email sent successfully to {patient_email}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email: {str(e)}")
        return False

@app.post('/api/schedule_meeting')
async def schedule_meeting(patientid: int, meeting_datetime: str, therapy: str, therapy_mode: str):
    """Schedule a meeting and send email to patient"""
    try:
        # Fetch patient details
        patient = collection.find_one({"patientid": patientid}, {"_id": 0})
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Validate patient email
        if not patient.get('email'):
            raise HTTPException(status_code=400, detail="Patient email not found in database")
        
        # Validate mode of appointments and therapies selected
        mode = ['online', 'offline']
        if therapy_mode.lower() not in mode:
            raise HTTPException(status_code=400, detail="Invalid mode of appointment")
        therapies = ["Psychology", "Speech & Language Therapy", "Occupational Therapy", "Music Therapy", "Continuous Education", "Nutrition"]
        if therapy not in therapies:
            raise HTTPException(status_code=400, detail=f"Selected therapy unavailable for {therapy_mode} appointments")

        # Validate meeting datetime format
        try:
            meeting_dt = datetime.fromisoformat(meeting_datetime)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid datetime format. Use: YYYY-MM-DDTHH:MM:SS")
        
        # Check if meeting is in the future
        if meeting_dt <= datetime.now():
            raise HTTPException(status_code=400, detail="Meeting datetime must be in the future")
        
        start_dt = datetime.fromisoformat(meeting_datetime)
        end_dt = start_dt + timedelta(hours=1)

        meet_link = create_google_meet_event(
            summary=f"Consultation with {patient['name']}",
            description="Health Consultation via Google Meet",
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat()
        )

        # Send email with meeting details
        email_sent = send_meeting_email(
            patient['name'], 
            patient['email'], 
            meeting_datetime,
            meet_link
        )
        
        # Store meeting details in database
        meeting_details = {
            "meeting_link": meet_link,
            "meeting_datetime": meeting_datetime,
            "scheduled_at": datetime.now().isoformat(),
            "therapy": therapy,
            "therapy_mode": therapy_mode,
            "email_sent": email_sent
        }

        track_meeting = {
            "patient_id": patientid,
            "patient_email": patient['email'],
            "meeting_details": [meeting_details]
        }
        past_meetings = meeting_history_collection.find_one({"patient_id": patientid})
        if past_meetings:
            update_history = meeting_history_collection.update_one(
                {"patient_id": patientid},
                {"$push": {"meeting_details": meeting_details}}
            )
        else:
            history = meeting_history_collection.insert_one(track_meeting)           
        
        # Update patient record
        update_result = collection.update_one(
            {"patientid": patientid},
            {"$set": {"meeting_details": meeting_details}}
        )
        
        return JSONResponse(status_code=200, content={
            "message": f"Meeting scheduled successfully for {patient['name']}",
            "patient_name": patient['name'],
            "patient_email": patient['email'],
            "meeting_link": meet_link,
            "meeting_datetime": meeting_datetime,
            "email_sent": email_sent,
            "status": "success"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to schedule meeting: {str(e)}")

# @app.post('/api/schedule_meeting')
# async def schedule_meeting(patientid: int, meeting_datetime: str):
#     """Schedule a meeting and send email to patient"""
#     try:
#         # Fetch patient details
#         patient = collection.find_one({"patientid": patientid}, {"_id": 0})
#         if not patient:
#             raise HTTPException(status_code=404, detail="Patient not found")
        
#         # Validate patient email
#         if not patient.get('email'):
#             raise HTTPException(status_code=400, detail="Patient email not found in database")
        
#         # Validate meeting datetime format
#         try:
#             meeting_dt = datetime.fromisoformat(meeting_datetime)
#         except ValueError:
#             raise HTTPException(status_code=400, detail="Invalid datetime format. Use: YYYY-MM-DDTHH:MM:SS")
        
#         # Check if meeting is in the future
#         if meeting_dt <= datetime.now():
#             raise HTTPException(status_code=400, detail="Meeting datetime must be in the future")
        
#         # Use your specific Google Meet link
#         meet_link = "https://meet.google.com/kme-zwvu-nsc"
        
#         # Send email with meeting details
#         email_sent = send_meeting_email(
#             patient['name'], 
#             patient['email'], 
#             meeting_datetime,
#             meet_link
#         )
        
#         # Store meeting details in database
#         meeting_details = {
#             "meeting_link": meet_link,
#             "meeting_datetime": meeting_datetime,
#             "scheduled_at": datetime.now().isoformat(),
#             "email_sent": email_sent
#         }
        
#         # Update patient record
#         update_result = collection.update_one(
#             {"patientid": patientid},
#             {"$set": {"meeting_details": meeting_details}}
#         )
        
#         return JSONResponse(status_code=200, content={
#             "message": f"Meeting scheduled successfully for {patient['name']}",
#             "patient_name": patient['name'],
#             "patient_email": patient['email'],
#             "meeting_link": meet_link,
#             "meeting_datetime": meeting_datetime,
#             "email_sent": email_sent,
#             "status": "success"
#         })
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to schedule meeting: {str(e)}")


@app.get('/api/test_email')
async def test_email():
    """Test email configuration"""
    try:
        # Test email sending
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = EMAIL_ADDRESS  # Send to yourself
        msg['Subject'] = "Patient360 - Email Test"
        
        body = """This is a test email from Patient360 system.

If you receive this, your email configuration is working correctly!

Email settings:
- SMTP Server: Gmail
- From: {EMAIL_ADDRESS}

Test successful! ✅
"""
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, EMAIL_ADDRESS, msg.as_string())
        server.quit()
        
        return JSONResponse(status_code=200, content={
            "message": "Email test successful!",
            "from_email": EMAIL_ADDRESS,
            "smtp_server": SMTP_SERVER,
            "status": "working"
        })
        
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "message": "Email test failed",
            "error": str(e),
            "status": "failed"
        })

# Your existing endpoints
@app.get('/api/health_check')
async def health_check():
    return ("OK", 200)
 
@app.get('/api/fetch_all_records')
async def fetch_all_records():
    try:
        records = list(collection.find({}, {"_id": 0}))
        if not records:
            raise HTTPException(status_code=404, detail="No records found")
        
        for record in records:
            if 'time' in record and hasattr(record['time'], 'isoformat'):
                record['time'] = record['time'].isoformat()
            if 'meeting_details' in record and isinstance(record['meeting_details'], dict):
                if 'scheduled_at' in record['meeting_details']:
                    # Handle both string and datetime objects
                    scheduled_at = record['meeting_details']['scheduled_at']
                    if hasattr(scheduled_at, 'isoformat'):
                        record['meeting_details']['scheduled_at'] = scheduled_at.isoformat()
                
        return JSONResponse(status_code=200, content=records)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
 
@app.get('/api/fetch_patient_details')
async def fetch_patient_details(patientid: int):
    try:
        patient_record = collection.find_one({"patientid": patientid}, {"_id": 0})
        if not patient_record:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        if 'time' in patient_record and hasattr(patient_record['time'], 'isoformat'):
            patient_record['time'] = patient_record['time'].isoformat()
            
        return JSONResponse(status_code=200, content=patient_record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.post('/api/send_plan_via_whatsapp')
async def send_plan_via_whatsapp(patientid: int, type: str, background_tasks: BackgroundTasks):
    try:
        current_time = datetime.now()
        update_result = collection.update_one(
            {"patientid": patientid},
            {"$set": {"type": type, "time": current_time}}
        )

        if update_result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Patient Not Updated")

        patient = collection.find_one({"patientid": patientid}, {"_id": 0})
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        template_name = get_template_name('Greetings')
        send_greeting_message(template_name, patient["mobileno"], patient["name"])

        background_tasks.add_task(send_daily_message, patient, type, 1, delay=5)
        for day_num in range(2, 8):
            background_tasks.add_task(send_daily_message, patient, type, day_num)

        return JSONResponse(status_code=200, content={"message": "Plans for all 7 days will be sent daily!"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    
# @app.post('/api/send_patient_summary')
# async def send_patient_summary(patientid: int):
#     """
#     Send patient health summary (Name, Weight, BP, Heart Rate, Fasting Sugar) 
#     to WhatsApp using ADA template: health_summary
#     """
#     try:
#         # Fetch patient details
#         patient = collection.find_one({"patientid": patientid}, {"_id": 0})
#         if not patient:
#             raise HTTPException(status_code=404, detail="Patient not found")

#         # Extract details with safe defaults
#         name = patient.get("name", "Unknown")
#         mobile = patient.get("mobileno")
#         weight = str(patient.get("weight", "N/A"))
#         bp = patient.get("bp", "N/A")
#         heartrate = str(patient.get("heartrate", "N/A"))
#         sugar = str(patient.get("fasting_sugar", "N/A"))

#         if not mobile:
#             raise HTTPException(status_code=400, detail="Mobile number missing for patient")

#         # WhatsApp ADA template name
#         template_name = "health_summary"

#         # Parameters must match {{1}}, {{2}}, {{3}}, {{4}}, {{5}} in template
#         params = [name, weight, bp, heartrate, sugar]

#         # Construct the actual message (for API response)
#         message_text = (
#             f"Health Summary:\n\n"
#             f"Name: {name}\n"
#             f"Weight: {weight}\n"
#             f"Blood Pressure: {bp}\n"
#             f"Heart Rate: {heartrate}\n"
#             f"Fasting Sugar: {sugar}\n"
#         )

#         # Send via WhatsApp
#         response = send_template_message(template_name, mobile, *params)

#         return JSONResponse(status_code=200, content={
#             "message": f"Health summary sent to {name} on WhatsApp",
#             "patientid": patientid,
#             "whatsapp_response": response,
#             "sent_text": message_text   # 👈 added this
#         })

#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to send health summary: {str(e)}")

@app.post('/api/send_patient_summary')
async def send_patient_summary(patientid: int, type: str, background_tasks: BackgroundTasks):
    try:
        # Fetch patient record
        patient = collection.find_one({"patientid": patientid}, {"_id": 0})
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        # Extract patient fields safely
        name = patient.get("name", "Unknown")
        mobile = patient.get("mobileno")
        weight = str(patient.get("weight", "N/A"))
        bp = patient.get("bp", "N/A")
        heartrate = str(patient.get("heartrate", "N/A"))
        sugar = str(patient.get("fasting_sugar", "N/A"))

        if not mobile:
            raise HTTPException(status_code=400, detail="Mobile number missing for patient")

        # Get template name
        template_name = get_template_name('HealthSummary')

        # Order matters! Must match template placeholders {{1}}, {{2}}, {{3}}, {{4}}, {{5}}
        template_data = [name, weight, bp, heartrate, sugar]

        # Send the WhatsApp message
        response = send_whatsapp_message(template_name, mobile, template_data)

        # Build preview message for API response
        message_text = (
            f"Health Summary:\n\n"
            f"Name: {name}\n"
            f"Weight: {weight}\n"
            f"Blood Pressure: {bp}\n"
            f"Heart Rate: {heartrate}\n"
            f"Fasting Sugar: {sugar}\n"
        )

        return JSONResponse(status_code=200, content={
            "message": f"Health summary sent to {name} on WhatsApp",
            "patientid": patientid,
            "whatsapp_response": response,
            "sent_text": message_text
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
  

async def send_daily_message(patient, type, day_num, delay=86400):
    await asyncio.sleep(delay)
    current_day = f"DAY{day_num}"
    plan = patient.get(f"{type}_PLAN", {}).get(current_day, f"No {type} plan for {current_day}")
    message = f"{type.capitalize()} plan for {current_day} for {patient['name']}: {plan}"
    print(message)
    template_name = get_template_name(type)
    response = send_template_message(template_name, patient["mobileno"], patient["name"], plan)
    print(f"Successfully sent the template '{template_name}' to {patient['mobileno']}.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


def send_static_template(template_name: str, mobile_number: str):
    """
    Send a static WhatsApp template that doesn't require parameters
    This function is specifically for templates with pre-defined content
    """
    try:
        from functions.send_whatsapp_msg import send_whatsapp_message
        
        # For static templates, we don't need to pass any template data
        # The template content is already defined in ADA
        template_data = []  # Empty array for static templates
        
        response = send_whatsapp_message(template_name, mobile_number, template_data)
        return response
        
    except Exception as e:
        print(f"Error sending static template: {str(e)}")
        raise e

@app.post('/api/send_summary_template')
async def send_summary_template(mobile_number: str):
    """
    Send the static summary template to any mobile number
    This template contains pre-defined health summary content
    """
    try:
        # Validate mobile number (basic validation)
        if not mobile_number or len(mobile_number) < 10:
            raise HTTPException(status_code=400, detail="Invalid mobile number")
        
        # Clean mobile number (remove spaces, hyphens, etc.)
        cleaned_mobile = ''.join(filter(str.isdigit, mobile_number))
        
        # Get the summary template name from your ada_templates
        template_name = get_template_name('HealthSummary')  # or 'summary' depending on your template mapping
        
        # Send static template using the new function
        response = send_static_template(template_name, cleaned_mobile)
        
        return JSONResponse(status_code=200, content={
            "message": f"Summary template sent successfully to {mobile_number}",
            "mobile_number": cleaned_mobile,
            "template_name": template_name,
            "whatsapp_response": response,
            "status": "success"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send summary template: {str(e)}")


@app.get('/api/patient/meetings')
async def get_patient_meetings(patient_id: int):
    try:
        patient = collection.find_one({"patientid": patient_id}, {"_id": 0})
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        patient_appointments = meeting_history_collection.find_one({"patient_id": patient_id})
        if not patient_appointments:
            raise HTTPException(status_code=404, detail="No Appointments Scheduled")
        
        else:
            now = datetime.now()
            past_appointments = list(filter(lambda x: datetime.fromisoformat(x['meeting_datetime'])< now, patient_appointments['meeting_details']))
            upcoming_appointments = list(filter(lambda x: datetime.fromisoformat(x['meeting_datetime'])>= now, patient_appointments['meeting_details']))

        appointments= {"patient_id": patient_id,"upcoming_appointments":[upcoming_appointments], "past_appointments":[past_appointments]}
            
        return JSONResponse(status_code=200, content=appointments)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# API to Schedule Appointments without therapy and its mode
@app.post('/api/patient/schedule_appointments')
async def schedule_appointment(patientid: int, meeting_datetime: str):
    """Schedule a meeting and send email to patient"""
    try:
        # Fetch patient details
        patient = collection.find_one({"patientid": patientid}, {"_id": 0})
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Validate patient email
        if not patient.get('email'):
            raise HTTPException(status_code=400, detail="Patient email not found in database")

        # Validate meeting datetime format
        try:
            meeting_dt = datetime.fromisoformat(meeting_datetime)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid datetime format. Use: YYYY-MM-DDTHH:MM:SS")
        
        # Check if meeting is in the future
        if meeting_dt <= datetime.now():
            raise HTTPException(status_code=400, detail="Meeting datetime must be in the future")
        
        start_dt = datetime.fromisoformat(meeting_datetime)
        end_dt = start_dt + timedelta(hours=1)

        meet_link = create_google_meet_event(
            summary=f"Consultation with {patient['name']}",
            description="Health Consultation via Google Meet",
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat()
        )

        # Send email with meeting details
        email_sent = send_meeting_email(
            patient['name'], 
            patient['email'], 
            meeting_datetime,
            meet_link
        )
        
        # Store meeting details in database
        meeting_details = {
            "meeting_link": meet_link,
            "meeting_datetime": meeting_datetime,
            "scheduled_at": datetime.now().isoformat(),
            "email_sent": email_sent
        }

        track_meeting = {
            "patient_id": patientid,
            "patient_email": patient['email'],
            "meeting_details": [meeting_details]
        }
        past_meetings = appointments_collection.find_one({"patient_id": patientid})
        if past_meetings:
            update_history = appointments_collection.update_one(
                {"patient_id": patientid},
                {"$push": {"meeting_details": meeting_details}}
            )
        else:
            history = appointments_collection.insert_one(track_meeting)           
        
        return JSONResponse(status_code=200, content={
            "message": f"Meeting scheduled successfully for {patient['name']}",
            "patient_name": patient['name'],
            "patient_email": patient['email'],
            "meeting_link": meet_link,
            "meeting_datetime": meeting_datetime,
            "email_sent": email_sent,
            "status": "success"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to schedule meeting: {str(e)}")



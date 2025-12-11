from dotenv import load_dotenv # type: ignore
import requests
import os

load_dotenv()

# ADA API endpoint and key
ADA_API_URL = os.getenv("ADA_API_URL")
ADA_API_KEY = os.getenv("ADA_API_KEY") 
headers = {
        'Authorization': f'Bearer {ADA_API_KEY}',
        'Content-Type': 'application/json'
}


def send_whatsapp_message(template_name: str, number: str, template_data: list = None):
    """Send a WhatsApp message using ADA's template system."""
    if template_data is None:
        template_data = [] 
    data = {
        "platform": "WA",
        "from": "15557091773",  
        "to": number,
        "type": "template",
        "templateName": template_name,
        "templateLang": "en",
        "templateData": template_data,  # Insert dynamic data
        "templateButton": []  # Optional: Add buttons if needed
    }

    # Send the POST request to ADA API
    response = requests.post(ADA_API_URL, headers=headers, json=data)

    # Log and inspect the full response for debugging
    if response.status_code == 200:
        print(f"Successfully sent the template '{template_name}' to {number}.")
        return response.json()  # Return the response if needed
    else:
        print(f"Failed to send the template '{template_name}'. Status: {response.status_code}")
        print(f"Response Text: {response.text}")  # Log full response text for debugging
        return None

def send_greeting_message(template_name: str, number: str, name: str):
    return send_whatsapp_message(template_name, number, [name])

def send_template_message(template_name: str, number: str, name: str, plan: str):
    return send_whatsapp_message(template_name, number, [name, plan])


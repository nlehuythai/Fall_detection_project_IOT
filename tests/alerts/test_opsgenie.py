import requests

def trigger_opsgenie_alarm(dt):
    api_key = "YOUR_OPSGENIE_API_KEY"
    url = "https://api.opsgenie.com/v2/alerts" # Use api.eu.opsgenie.com if in Europe
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"GenieKey {api_key}"
    }
    
    data = {
        "message": "🚨 CRITICAL: Fall Detected!",
        "description": f"MPU and Camera synced within {dt:.2f} seconds.",
        "priority": "P1", # P1 is the highest priority and triggers the loudest sounds
        "tags": ["fall_detector", "safety"]
    }
    
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 202:
        print("✅ Opsgenie alert sent!")
    else:
        print(f"❌ Opsgenie failed: {response.text}") 

import requests

# ================= CONFIG =================
# 1. Paste your Auth Token from the Blynk Device Info tab
BLYNK_AUTH_TOKEN = "Your_Blynk_Auth_Token_Here" 

# 2. This MUST match the 'Event Code' you created in Blynk (e.g., fall_alert)
BLYNK_EVENT_CODE = "fall_alert" 
# =========================================

def trigger_test_alert():
    """
    Sends a single HTTP request to Blynk to trigger the notification/siren.
    """
    print(f"--- Initiating Blynk Test for Event: {BLYNK_EVENT_CODE} ---")
    
    # Blynk HTTP API URL
    url = f"https://blynk.cloud/external/api/logEvent?token={BLYNK_AUTH_TOKEN}&code={BLYNK_EVENT_CODE}"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print("✅ SUCCESS: Request sent to Blynk!")
            print("Check your phone for the notification or siren sound.")
        elif response.status_code == 400:
            print("❌ ERROR 400: Invalid Token or Event Code. Check your CONFIG.")
        elif response.status_code == 403:
            print("❌ ERROR 403: Invalid Auth Token.")
        else:
            print(f"⚠️ Unexpected Status: {response.status_code}")
            print(f"Response Body: {response.text}")
            
    except Exception as e:
        print(f"❌ CONNECTION ERROR: Could not reach Blynk servers.\n{e}")

if __name__ == "__main__":
    trigger_test_alert()
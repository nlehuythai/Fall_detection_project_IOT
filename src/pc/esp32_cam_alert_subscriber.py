import paho.mqtt.client as mqtt
import json
import os

# ==================== CONFIGURATION ====================
MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 1883
MQTT_TOPIC = "esp32/camera/alert"
MQTT_CLIENT_ID = "Emergency_Monitor_Station"

# ==================== CALLBACKS ====================

def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the broker"""
    if rc == 0:
        print("--- MONITORING STATION ACTIVE ---")
        print(f"Connected to: {MQTT_BROKER}")
        print(f"Subscribed to topic: {MQTT_TOPIC}")
        print("Waiting for status updates...\n")
        client.subscribe(MQTT_TOPIC, qos=2)
    else:
        print(f"Connection failed with code {rc}")

def on_message(client, userdata, msg):
    """Callback for when a message is received"""
    try:
        # Decode the JSON alert
        payload = json.loads(msg.payload.decode())
        
        # Extract details
        status = payload.get("alert", "UNKNOWN")
        severity = payload.get("severity", "INFO")
        duration = payload.get("duration_seconds", 0)
        timestamp = payload.get("timestamp", "N/A")

        # Visual Alert Formatting
        print("="*50)
        print(f"🚨 ALERT RECEIVED: {status}")
        print(f"Severity:  {severity}")
        print(f"Duration:  {duration} seconds")
        print(f"Time:      {timestamp}")
        print("="*50 + "\n")

        # Optional: Add a system beep (works on some OS)
        if severity == "CRITICAL":
            print("\a") # Trigger system bell/beep

    except Exception as e:
        print(f"Error parsing alert: {e}")

# ==================== MAIN EXECUTION ====================

def main():
    # Initialize Client
    client = mqtt.Client(client_id=MQTT_CLIENT_ID)
    
    # Assign Callbacks
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        # Connect and Start Loop
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        # loop_forever() is a blocking call, it runs the network loop 
        # and handles reconnecting automatically
        client.loop_forever()
        
    except KeyboardInterrupt:
        print("\nMonitoring station shutting down...")
        client.disconnect()

if __name__ == "__main__":
    main() 

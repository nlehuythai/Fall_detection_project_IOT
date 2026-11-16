import time
from mqtt_handler import MQTTListener

listener = MQTTListener()

print("Starting MQTT listener...")
listener.start()

try:
    for i in range(30):
        print("\n" + "=" * 45)

        print("MQTT connected:", listener.is_connected())

        latest = listener.get_latest()

        if latest:
            print("Latest event:", latest.get("event"))
            print("Camera:", latest.get("camera"))
            print("Timestamp:", latest.get("timestamp"))
            print("Confidence:", latest.get("average_confidence"))
        else:
            print("Waiting for YOLO detection...")

        time.sleep(1)

except KeyboardInterrupt:
    print("Test stopped.")

finally:
    listener.stop()
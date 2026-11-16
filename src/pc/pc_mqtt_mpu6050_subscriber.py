import json
import time
import paho.mqtt.client as mqtt

BROKER = "test.mosquitto.org"
PORT = 1883

TOPIC_MPU_DATA = "esp32/mpu6050/data"
TOPIC_MPU_FALL = "esp32/mpu6050/fall"

MQTT_CLIENT_ID = "MPU6050_PC_Receiver"

GX_THRESHOLD = 1.5
AX_THRESHOLD = 9
AZ_THRESHOLD = 9

COOLDOWN_TIME = 5
last_fall_time = 0


def is_fall_condition(data):
    gx = abs(data.get("gx", 0))
    ax = abs(data.get("ax", 0))
    az = abs(data.get("az", 0))

    return (
        gx > GX_THRESHOLD
        and (ax > AX_THRESHOLD or az > AZ_THRESHOLD)
    )


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("✓ Connected to MQTT broker")

        result, mid = client.subscribe(TOPIC_MPU_DATA)

        if result == mqtt.MQTT_ERR_SUCCESS:
            print(f"✓ Subscribed: {TOPIC_MPU_DATA}")
        else:
            print("✗ Subscribe failed:", result)

    else:
        print(f"✗ MQTT connection failed: {reason_code}")


def on_disconnect(client, userdata, disconnect_flags,
                  reason_code, properties):
    print(f"⚠ MQTT disconnected: {reason_code}")


def on_message(client, userdata, msg):
    global last_fall_time

    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("✗ Invalid JSON:", msg.payload)
        return

    print("📡 Received MPU6050 Data:", data)

    if not is_fall_condition(data):
        return

    now = time.time()

    if now - last_fall_time < COOLDOWN_TIME:
        print("⏳ Fall detected but in cooldown period")
        return

    last_fall_time = now

    print("🚨 FALL DETECTED BY MPU6050!")

    alert_msg = json.dumps({
        "event": "MPU_FALL_DETECTED",
        "timestamp": now,
        "data": data
    })

    info = client.publish(
        TOPIC_MPU_FALL,
        alert_msg,
        qos=1
    )

    if info.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"📤 Publishing alert: {TOPIC_MPU_FALL}")
    else:
        print(f"✗ Publish failed: {info.rc}")


client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id=MQTT_CLIENT_ID
)

client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

client.reconnect_delay_set(
    min_delay=1,
    max_delay=30
)

try:
    print(f"Connecting to {BROKER}:{PORT}...")

    client.connect(BROKER, PORT, keepalive=60)
    client.loop_forever()

except KeyboardInterrupt:
    print("\nStopping MQTT subscriber...")

finally:
    client.disconnect()
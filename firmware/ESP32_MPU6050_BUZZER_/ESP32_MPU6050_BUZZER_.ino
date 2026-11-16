/*
  ESP32 Fall Detection Node
  - Publishes: MPU6050 Data (Accel/Gyro)
  - Subscribes: Alerts from PC (to trigger Buzzer)
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// -------- Configuration --------
const char* ssid = "It's YanJiun";
const char* password = "pehyanjiun";
const char* mqtt_server = "test.mosquitto.org";

// Topics
const char* topic_publish = "esp32/mpu6050/data";
const char* topic_subscribe = "esp32/camera/alert";

// Hardware Pins
const int BUZZER_PIN = 13; // Connect Buzzer (+) to GPIO 13

WiFiClient espClient;
PubSubClient client(espClient);
Adafruit_MPU6050 mpu;

// -------- MQTT Callback (Receiving Alerts) --------
void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived on topic: ");
  Serial.println(topic);

  // Convert payload to string
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.println("Payload: " + message);

  // Check if the payload contains the fall alert keyword
  if (message.indexOf("FALL_DETECTED") != -1) {
    Serial.println("🚨 EMERGENCY: Fall alert received! Activating Buzzer.");
    
    // Sound the buzzer (3 rapid beeps)
    for(int i = 0; i < 3; i++) {
      digitalWrite(BUZZER_PIN, HIGH);
      delay(200);
      digitalWrite(BUZZER_PIN, LOW);
      delay(100);
    }
  }
}

void setup_wifi() {
  Serial.print("Connecting to WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✓ WiFi Connected");
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect("ESP32_MultiTask_Node")) {
      Serial.println("connected");
      // IMPORTANT: Resubscribe to the alert topic after connecting
      client.subscribe(topic_subscribe);
      Serial.println("✓ Subscribed to Alert Topic");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  
  // Initialize Buzzer
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  setup_wifi();
  client.setServer(mqtt_server, 1883);
  client.setCallback(callback); // Set the function to handle incoming alerts

  if (!mpu.begin()) {
    Serial.println("MPU6050 not found!");
    while (1);
  }

  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop(); // This must run to process incoming subscriber messages

  // --- Publish Sensor Data every 500ms ---
  static unsigned long lastMsg = 0;
  unsigned long now = millis();
  
  if (now - lastMsg > 500) {
    lastMsg = now;
    
    sensors_event_t accel, gyro, temp;
    mpu.getEvent(&accel, &gyro, &temp);

    char payload[256];
    snprintf(payload, sizeof(payload),
      "{\"ax\":%.2f,\"ay\":%.2f,\"az\":%.2f,\"gx\":%.2f,\"gy\":%.2f,\"gz\":%.2f}",
      accel.acceleration.x, accel.acceleration.y, accel.acceleration.z,
      gyro.gyro.x, gyro.gyro.y, gyro.gyro.z
    );

    client.publish(topic_publish, payload);
  }
}
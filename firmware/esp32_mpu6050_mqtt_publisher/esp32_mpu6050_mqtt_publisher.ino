
#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// -------- WiFi credentials --------
const char* ssid = "It's YanJiun";
const char* password = "pehyanjiun";

// -------- MQTT Broker --------
const char* mqtt_server = "test.mosquitto.org";
const int mqtt_port = 1883;
const char* mqtt_topic = "esp32/mpu6050/data";

WiFiClient espClient;
PubSubClient client(espClient);

Adafruit_MPU6050 mpu;

void setup_wifi() {
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
}

void reconnect() {
  while (!client.connected()) {
    client.connect("ESP32_MPU6050_Publisher");
    delay(1000);
  }
}

void setup() {
  Serial.begin(115200);
  Wire.begin();

  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);

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
  client.loop();

  sensors_event_t accel, gyro, temp;
  mpu.getEvent(&accel, &gyro, &temp);

  char payload[256];
  snprintf(payload, sizeof(payload),
    "{\"ax\":%.2f,\"ay\":%.2f,\"az\":%.2f,\"gx\":%.2f,\"gy\":%.2f,\"gz\":%.2f}",
    accel.acceleration.x,
    accel.acceleration.y,
    accel.acceleration.z,
    gyro.gyro.x,
    gyro.gyro.y,
    gyro.gyro.z
  );

  client.publish(mqtt_topic, payload);
  delay(500);
}

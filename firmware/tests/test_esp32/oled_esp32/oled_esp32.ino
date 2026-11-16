#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>  // Included to disable the radio

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define RESET_BUTTON_PIN 4  // Connect button between GPIO 4 and GND

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

unsigned long startTime = 0;
unsigned long elapsedTime = 0;

void setup() {
  // 1. CRITICAL: Disable WiFi and Bluetooth immediately
  // These radios consume 100mA+ and are the main cause of 
  // "freezing" or "resetting" on battery power.
  WiFi.mode(WIFI_OFF);
  btStop();

  // 2. Initialize the Reset Button
  pinMode(RESET_BUTTON_PIN, INPUT_PULLUP);

  // 3. Initialize OLED
  // Note: We do NOT use "while(!Serial)" here because 
  // it would stop the code if no PC is connected.
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) { 
    for(;;); // Loop forever if display is not found
  }

  display.clearDisplay();
  startTime = millis(); // Initialize start time
}

void loop() {
  // Check for Reset Button Press (Active LOW)
  if (digitalRead(RESET_BUTTON_PIN) == LOW) {
    startTime = millis();
    delay(50); // Simple debounce
  }

  // Calculate Time
  elapsedTime = millis() - startTime;
  unsigned long totalSeconds = elapsedTime / 1000;
  int seconds = totalSeconds % 60;
  int minutes = (totalSeconds / 60) % 60;
  int hours   = (totalSeconds / 3600);

  // Update Display
  display.clearDisplay();
  
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(35, 10);
  display.print("STOPWATCH");

  // Format HH:MM:SS
  display.setTextSize(2);
  display.setCursor(15, 35);
  
  if(hours < 10) display.print("0");
  display.print(hours);
  display.print(":");
  
  if(minutes < 10) display.print("0");
  display.print(minutes);
  display.print(":");
  
  if(seconds < 10) display.print("0");
  display.print(seconds);

  display.display();
  
  // A tiny delay helps stabilize power consumption
  delay(100); 
}
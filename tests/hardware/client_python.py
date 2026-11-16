import cv2
from ultralytics import YOLO

# Replace with your ESP32 IP address
# Usually, the stream is on port 81
url = "http://192.168.1.50:81/stream"

# Create a VideoCapture object
cap = cv2.VideoCapture(url)

if not cap.isOpened():
    print("Error: Could not open video stream. Check IP and Port.")
    exit()



model = YOLO("yolov8n.pt") # Load a small, fast model
model.predict(source=url, show=True) # Ultralytics handles the stream for you!

cap.release()
cv2.destroyAllWindows()
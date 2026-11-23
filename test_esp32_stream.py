import cv2
import time

URL = "http://192.168.137.15:81/stream"

cap = cv2.VideoCapture(URL, cv2.CAP_FFMPEG)

print("Opened:", cap.isOpened())

count = 0
start = time.time()

while time.time() - start < 30:
    ret, frame = cap.read()

    if ret:
        count += 1
        print(f"Frame {count}: {frame.shape}")
    else:
        print("Failed to read frame")
        break

cap.release()

print("Total frames:", count)
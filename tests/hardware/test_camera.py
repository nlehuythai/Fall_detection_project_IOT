import cv2
from ultralytics import YOLO


def load_model(model_path):
    """Load the YOLOv11 model from the specified path."""
    return YOLO(model_path)


def camera():
    """Open the webcam and return the VideoCapture object."""
    # Note: 0 is usually the default webcam, 1 is often an external camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not access the webcam.")
        exit()
    return cap

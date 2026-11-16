import os
from dotenv import load_dotenv
load_dotenv()
import cv2
from ultralytics import YOLO


def load_model(model_path):
    """Load the YOLOv11 model from the specified path."""
    return YOLO(model_path)


def camera():
    """Open the network camera feed and return the VideoCapture object."""
    # Connect to the network camera feed
    cap = cv2.VideoCapture(os.getenv("ESP32_CAM_STREAM_URL", "http://<ESP32_CAM_IP>:81/stream"))
    if not cap.isOpened():
        print("Error: Could not access the network camera feed.")
        exit()
    return cap


def object_detection(model, frame):
    """Run YOLOv11 inference on the frame and return annotated frame and detection results."""
    # Get the frame dimensions
    image_height, image_width = frame.shape[:2]

    # Run YOLOv11 inference
    results = model(frame, verbose=False)
    annotated_frame = results[0].plot()

    detections = []
    for box in results[0].boxes:
        # Get class ID, coordinates, and confidence
        class_id = results[0].names[int(box.cls[0].item())]
        x1, y1, x2, y2 = box.xyxy[0].tolist()  # Bounding box coordinates

        # Calculate box dimensions
        box_width = x2 - x1
        box_height = y2 - y1

        x_center = (x1 + box_width / 2) / image_width
        y_center = (y1 + box_height / 2) / image_height
        width = box_width / image_width
        height = box_height / image_height
        conf = round(box.conf[0].item(), 2)  # Get confidence

        detection = {
            "Object type": class_id,
            "Coordinates": [round(x1), round(y1), round(x2), round(y2)],
            "Probability": conf,
            "X Center": round(x_center, 2),
            "Y Center": round(y_center, 2),
            "Width": round(width, 2),
            "Height": round(height, 2)
        }
        detections.append(detection)

    return annotated_frame, detections


def main():
    # Define model path - Ensure this path is correct for your machine
    model_path = os.getenv("MODEL_PATH", "training/models/1_1_2026__best.pt")
    # Load the YOLOv11 model
    model = load_model(model_path)

    # Open the webcam
    cap = camera()

    # Loop through the video frames from the webcam
    while cap.isOpened():
        success, frame = cap.read()
        if success:
            # Run object detection
            annotated_frame, detections = object_detection(model, frame)

            # Print detection details
            for detection in detections:
                print("Object type:", detection["Object type"])
                print("Coordinates:", detection["Coordinates"])
                print("Probability:", detection["Probability"])
                print("X Center:", detection["X Center"])
                print("Y Center:", detection["Y Center"])
                print("Width:", detection["Width"])
                print("Height:", detection["Height"])
                print("---")

            # Display the annotated frame
            cv2.imshow("YOLOv11 Inference", annotated_frame)

            # Break the loop if 'q' is pressed
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        else:
            break

    # Release the webcam and close the display window
    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

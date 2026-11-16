import os
import cv2  # Import OpenCV library for computer vision tasks like image processing and camera access
from ultralytics import YOLO  # Import the YOLO class from the ultralytics library for object detection


def load_model(model_path):
    """Load the YOLOv11 model from the specified path."""
    # Initialize and return the YOLO model using the provided weights file path (.pt file)
    return YOLO(model_path)


def camera():
    """Open the external camera feed and return the VideoCapture object."""
    # Connect to the external camera; index 1 is typically used for external USB cameras
    # Change to 0 if this is the only camera on your system or 2 if you have multiple external devices
    cap = cv2.VideoCapture(2) 
    
    # Check if the camera was successfully opened; returns False if the device is not found or busy
    if not cap.isOpened():
        # Inform the user that the camera could not be accessed
        print("Error: Could not access the external camera.")
        # Terminate the script execution as the camera is essential for the process
        exit()
    # Return the capture object which will be used to read video frames
    return cap


def object_detection(model, frame):
    """Run YOLOv11 inference on the frame and return annotated frame and detection results."""
    # Extract the height and width from the image frame shape to use for normalization later
    image_height, image_width = frame.shape[:2]

    # Perform object detection on the current frame; verbose=False hides console logs from YOLO
    results = model(frame, verbose=False)
    
    # Extract the frame with bounding boxes and class labels automatically drawn by the model
    annotated_frame = results[0].plot()

    # Initialize a list to hold the structured detection data for each object found
    detections = []
    # Loop through each bounding box detected by the model in the current image
    for box in results[0].boxes:
        # Retrieve the human-readable class name (e.g., 'cup', 'cell phone') using the class ID
        class_name = results[0].names[int(box.cls[0].item())]
        
        # Extract the bounding box coordinates in [xmin, ymin, xmax, ymax] format
        x1, y1, x2, y2 = box.xyxy[0].tolist() 

        # Calculate the absolute width and height of the bounding box in pixels
        box_width = x2 - x1
        box_height = y2 - y1

        # Calculate the normalized center coordinates (0.0 to 1.0) relative to image size
        x_center = (x1 + box_width / 2) / image_width
        y_center = (y1 + box_height / 2) / image_height
        
        # Calculate the normalized width and height of the box (0.0 to 1.0)
        width = box_width / image_width
        height = box_height / image_height
        
        # Get the confidence score (the model's certainty) and round it to 2 decimal places
        conf = round(box.conf[0].item(), 2) 

        # Structured dictionary containing all relevant details for a single detected object
        detection = {
            "Object type": class_name,
            "Coordinates": [round(x1), round(y1), round(x2), round(y2)],
            "Probability": conf,
            "X Center": round(x_center, 2),
            "Y Center": round(y_center, 2),
            "Width": round(width, 2),
            "Height": round(height, 2)
        }
        # Append this detection to our list of results
        detections.append(detection)

    # Return both the visual frame (with boxes) and the raw data list
    return annotated_frame, detections


def main():
    # Define the absolute path to the trained YOLO model file
    model_path = os.getenv("MODEL_PATH", "training/models/1_1_2026__best.pt")
    
    # Load the YOLO model using the helper function defined earlier
    model = load_model(model_path)

    # Initialize the camera capture using the updated camera function (now using external camera)
    cap = camera()

    # Run the processing loop as long as the camera capture is open and active
    while cap.isOpened():
        # Read a single frame from the camera; success is True if a frame was grabbed
        success, frame = cap.read()
        
        if success:
            # Process the current frame to detect objects and get the annotated image
            annotated_frame, detections = object_detection(model, frame)

            # Iterate through the detections and print their properties to the console
            for detection in detections:
                print("Object type:", detection["Object type"])
                print("Coordinates:", detection["Coordinates"])
                print("Probability:", detection["Probability"])
                print("X Center:", detection["X Center"])
                print("Y Center:", detection["Y Center"])
                print("Width:", detection["Width"])
                print("Height:", detection["Height"])
                print("---")  # Print a separator for readability in the console

            # Display the video frame in a window titled "YOLOv11 Inference"
            cv2.imshow("YOLOv11 Inference", annotated_frame)

            # Wait for 1ms; if the 'q' key is pressed, break the while loop to stop the program
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        else:
            # If the frame could not be read (e.g., camera disconnected), stop the loop
            break

    # Once the loop ends, release the camera hardware so other apps can use it
    cap.release()
    # Close all OpenCV-created windows to clean up resources
    cv2.destroyAllWindows()


if __name__ == '__main__':
    # Start the program by calling the main function
    main()
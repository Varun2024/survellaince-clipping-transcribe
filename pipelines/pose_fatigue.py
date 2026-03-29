import cv2
import json
from pathlib import Path
import numpy as np

# Thresholds for fatigue detection
EAR_BLINK_THRESHOLD = 0.3
EAR_MICROSLEEP_THRESHOLD = 0.2
MICROSLEEP_DURATION_FRAMES = 5
YAWN_MAR_THRESHOLD = 0.6
YAWN_DURATION_FRAMES = 2
HEAD_NOD_THRESHOLD = 0.04
HEAD_NOD_FRAMES = 3

def detect_eyes_and_compute_ear(frame, face_cascade, eye_cascade):
    """
    Detect eyes and compute Eye Aspect Ratio (EAR) for blink/fatigue detection.
    Returns EAR value or None if no face/eyes detected.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    
    if len(faces) == 0:
        return None
    
    # Use first detected face
    (x, y, w, h) = faces[0]
    roi_gray = gray[y:y+h, x:x+w]
    roi_color = frame[y:y+h, x:x+w]
    
    eyes = eye_cascade.detectMultiScale(roi_gray)
    
    if len(eyes) < 2:
        return None
    
    # Simple EAR estimation based on eye detection area
    # Smaller eye bounding box = eyes closed
    eye_areas = [e[2] * e[3] for e in eyes[:2]]
    avg_eye_area = np.mean(eye_areas)
    
    # Normalize to a rough EAR-like metric (0-1 scale)
    # This is a simplified alternative to proper eye landmarks
    ear = min(1.0, avg_eye_area / 1000.0)
    return ear

def detect_head_position(frame, face_cascade):
    """
    Detect head position (up/down/forward/backward).
    Returns head position dict or None.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    
    if len(faces) == 0:
        return None
    
    (x, y, w, h) = faces[0]
    head_center_y = y + h / 2
    head_center_x = x + w / 2
    frame_h, frame_w = frame.shape[:2]
    
    return {
        "head_center_x": head_center_x / frame_w,  # normalized 0-1
        "head_center_y": head_center_y / frame_h,  # normalized 0-1
        "face_width": w / frame_w,
        "face_height": h / frame_h,
    }

def analyze_pose_and_fatigue(frames_dir, output_json):
    """
    Analyze video frames for fatigue indicators using OpenCV-based methods.
    Outputs per-frame metrics to a JSON file.
    """
    results = []
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )
    eye_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_eye.xml'
    )
    
    # State tracking for advanced metrics
    microsleep_counter = 0
    yawn_counter = 0
    head_nod_counter = 0
    prev_head_y = None
    
    frames = sorted(Path(frames_dir).glob('frame_*.jpg'))
    
    for frame_path in frames:
        frame = cv2.imread(str(frame_path))
        if frame is None:
            continue
        
        frame_result = {"frame": frame_path.name}
        
        # Detect eyes and compute EAR
        ear = detect_eyes_and_compute_ear(frame, face_cascade, eye_cascade)
        if ear is not None:
            frame_result["ear"] = float(ear)
            
            # Blink detection (fast EAR drop)
            frame_result["blink"] = bool(ear < EAR_BLINK_THRESHOLD)
            
            # Microsleep detection (prolonged eye closure)
            if ear < EAR_MICROSLEEP_THRESHOLD:
                microsleep_counter += 1
            else:
                microsleep_counter = 0
            frame_result["microsleep"] = bool(microsleep_counter >= MICROSLEEP_DURATION_FRAMES)
        
        # Detect head position
        head_pos = detect_head_position(frame, face_cascade)
        if head_pos is not None:
            frame_result.update(head_pos)
            
            # Head nod detection (sudden downward movement)
            if prev_head_y is not None and head_pos["head_center_y"] - prev_head_y > HEAD_NOD_THRESHOLD:
                head_nod_counter += 1
            else:
                head_nod_counter = 0
            frame_result["head_nod"] = bool(head_nod_counter >= HEAD_NOD_FRAMES)
            
            # Simple slouch detection (head below center)
            frame_result["slouch"] = bool(head_pos["head_center_y"] > 0.6)
            
            prev_head_y = head_pos["head_center_y"]
        
        results.append(frame_result)
    
    # Write results to JSON
    with open(output_json, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Pose and fatigue results written to {output_json}")
    print(f"Analyzed {len(results)} frames for fatigue indicators")

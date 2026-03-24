import cv2
import mediapipe as mp
import json
from pathlib import Path
import numpy as np

def eye_aspect_ratio(eye_landmarks):
    # Calculate the Eye Aspect Ratio (EAR) for blink/yawn detection
    # eye_landmarks: list of (x, y) tuples for eye points
    # Using 6 points: [0, 1, 2, 3, 4, 5] (MediaPipe Face Mesh indices)
    A = np.linalg.norm(np.array(eye_landmarks[1]) - np.array(eye_landmarks[5]))
    B = np.linalg.norm(np.array(eye_landmarks[2]) - np.array(eye_landmarks[4]))
    C = np.linalg.norm(np.array(eye_landmarks[0]) - np.array(eye_landmarks[3]))
    ear = (A + B) / (2.0 * C)
    return ear

def analyze_pose_and_fatigue(frames_dir, output_json):
    mp_pose = mp.solutions.pose
    mp_face_mesh = mp.solutions.face_mesh
    results = []
    with mp_pose.Pose(static_image_mode=True) as pose, \
         mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1) as face_mesh:
        for frame_path in sorted(Path(frames_dir).glob('frame_*.jpg')):
            image = cv2.imread(str(frame_path))
            if image is None:
                continue
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pose_res = pose.process(rgb)
            face_res = face_mesh.process(rgb)
            frame_result = {"frame": frame_path.name}
            # Pose landmarks
            if pose_res.pose_landmarks:
                nose = pose_res.pose_landmarks.landmark[mp_pose.PoseLandmark.NOSE]
                left_eye = pose_res.pose_landmarks.landmark[mp_pose.PoseLandmark.LEFT_EYE]
                right_eye = pose_res.pose_landmarks.landmark[mp_pose.PoseLandmark.RIGHT_EYE]
                left_shoulder = pose_res.pose_landmarks.landmark[mp_pose.PoseLandmark.LEFT_SHOULDER]
                right_shoulder = pose_res.pose_landmarks.landmark[mp_pose.PoseLandmark.RIGHT_SHOULDER]
                frame_result.update({
                    "nose": [nose.x, nose.y, nose.z],
                    "left_eye": [left_eye.x, left_eye.y, left_eye.z],
                    "right_eye": [right_eye.x, right_eye.y, right_eye.z],
                    "left_shoulder": [left_shoulder.x, left_shoulder.y, left_shoulder.z],
                    "right_shoulder": [right_shoulder.x, right_shoulder.y, right_shoulder.z],
                })
                # Head pose estimation (simple): vertical head position
                frame_result["head_down"] = nose.y > left_shoulder.y and nose.y > right_shoulder.y
            # Face mesh for advanced fatigue metrics
            if face_res.multi_face_landmarks:
                face_landmarks = face_res.multi_face_landmarks[0]
                # Example: EAR for left eye (indices 33, 160, 158, 133, 153, 144)
                indices = [33, 160, 158, 133, 153, 144]
                eye_points = [(face_landmarks.landmark[i].x, face_landmarks.landmark[i].y) for i in indices]
                ear = eye_aspect_ratio(eye_points)
                frame_result["left_eye_ear"] = ear
                # Simple blink detection
                frame_result["blink"] = ear < 0.2
                # (Optional) Add yawn detection, head pose, etc.
            results.append(frame_result)
    with open(output_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Pose and fatigue results written to {output_json}")

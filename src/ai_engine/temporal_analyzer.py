
import os
import time
from collections import deque
from pathlib import Path

import numpy as np
from dotenv import load_dotenv


# Load cấu hình từ .env
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

CONF_THRESHOLD = float(
    os.getenv("CONF_THRESHOLD", "0.5")
)


class FallTemporalAnalyzer:

    def __init__(self):
        self.history = deque(maxlen=40)
        self.detection_history = deque(maxlen=15)

        self.state = "NORMAL"

        self.transition_time = None
        self.low_posture_start = None
        self.recovery_start = None

        self.transition_peak_velocity = 0.0

    def reset_transition(self):
        self.transition_time = None
        self.low_posture_start = None
        self.transition_peak_velocity = 0.0

    def update(self, detection_class, detection_confidence, features):
        current_time = time.time()

        is_fallen = (
            detection_class == "Fallen"
            and detection_confidence >= CONF_THRESHOLD
        )

        self.detection_history.append(is_fallen)

        fallen_ratio = (
            sum(self.detection_history) / len(self.detection_history)
            if self.detection_history else 0.0
        )

        if features is None:
            return {
                "state": self.state,
                "fallen_ratio": fallen_ratio,
                "average_velocity": 0.0,
                "low_duration": 0.0,
                "reason": "Pose unavailable"
            }

        torso_angle = features["torso_angle"]
        hip_y = features["hip_y"]
        hip_velocity = features["hip_velocity"]

        self.history.append({
            "time": current_time,
            "angle": torso_angle,
            "hip_y": hip_y,
            "velocity": hip_velocity
        })

        # Chuyển động trong 1 giây gần nhất
        recent_samples = [
            item for item in self.history
            if current_time - item["time"] <= 1.0
        ]

        average_velocity = (
            float(np.mean([
                item["velocity"] for item in recent_samples
            ]))
            if recent_samples else 0.0
        )

        peak_downward_velocity = max(
            [item["velocity"] for item in recent_samples] + [0.0]
        )

        # Xác định tư thế thấp
        low_posture = torso_angle >= 50

        if low_posture:
            if self.low_posture_start is None:
                self.low_posture_start = current_time

            low_duration = current_time - self.low_posture_start

        else:
            self.low_posture_start = None
            low_duration = 0.0

        # Tìm tư thế đứng gần nhất trong 3 giây
        upright_samples = [
            item for item in self.history
            if current_time - item["time"] <= 3.0
            and item["angle"] <= 35
        ]

        transition_detected = False

        if low_posture and upright_samples:
            previous_upright = upright_samples[-1]

            angle_change = (
                torso_angle - previous_upright["angle"]
            )

            hip_drop = hip_y - previous_upright["hip_y"]

            transition_detected = (
                angle_change >= 20
                and hip_drop >= 20
                and peak_downward_velocity >= 220
            )

        # NORMAL
        if self.state == "NORMAL":

            if transition_detected:
                self.state = "FALL_TRANSITION"
                self.transition_time = current_time

                self.transition_peak_velocity = (
                    peak_downward_velocity
                )

        # FALL_TRANSITION
        elif self.state == "FALL_TRANSITION":

            if not low_posture:
                self.state = "NORMAL"
                self.reset_transition()

            else:
                self.transition_peak_velocity = max(
                    self.transition_peak_velocity,
                    peak_downward_velocity
                )

                if low_duration >= 1.0:
                    self.state = "POSTURE_VERIFICATION"

        # POSTURE_VERIFICATION
        elif self.state == "POSTURE_VERIFICATION":

            if not low_posture:
                self.state = "NORMAL"
                self.reset_transition()

            elif self.transition_time is not None:

                transition_duration = (
                    current_time - self.transition_time
                )

                enough_detection_evidence = (
                    fallen_ratio >= 0.8
                )

                enough_motion_evidence = (
                    self.transition_peak_velocity >= 220
                )

                if (
                    transition_duration >= 2.0
                    and low_duration >= 2.0
                    and enough_detection_evidence
                    and enough_motion_evidence
                ):
                    self.state = "FALL_CONFIRMED"

        # FALL_CONFIRMED
        elif self.state == "FALL_CONFIRMED":

            if not low_posture and not is_fallen:

                if self.recovery_start is None:
                    self.recovery_start = current_time

                elif current_time - self.recovery_start >= 3.0:
                    self.state = "RECOVERED"
                    self.recovery_start = None
                    self.reset_transition()

            else:
                self.recovery_start = None

        # RECOVERED
        elif self.state == "RECOVERED":

            self.state = "NORMAL"
            self.history.clear()
            self.detection_history.clear()
            self.reset_transition()

        return {
            "state": self.state,
            "fallen_ratio": fallen_ratio,
            "average_velocity": average_velocity,
            "low_duration": low_duration,
            "reason": "Analyzing"
        }

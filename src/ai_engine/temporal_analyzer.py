import os
import time
from collections import deque
from pathlib import Path
import math
import numpy as np
from dotenv import load_dotenv


# =========================================================
# CONFIGURATION
# =========================================================

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.5"))

# Tư thế
UPRIGHT_ANGLE_THRESHOLD = 35
UPRIGHT_CONFIRM_SECONDS = 1.5

# Giảm từ 50 xuống 45 để nhận diện tư thế nằm
# trong trường hợp góc thân người chỉ đạt khoảng 40-50 độ.
LOW_POSTURE_ANGLE_THRESHOLD = 45

# Thời gian cho phép mất Pose
POSE_LOST_TIMEOUT = 2.0

# Ngưỡng chuyển động
FALL_VELOCITY_THRESHOLD = 150
FALL_ANGLE_CHANGE_THRESHOLD = 20
FALL_HIP_DROP_THRESHOLD = 20

# Lưu vận tốc cực đại trong khoảng thời gian này.
# Không còn phụ thuộc vận tốc phải đạt đỉnh đúng lúc
# low_posture vừa được kích hoạt.
MOTION_HISTORY_SECONDS = 2.0

# State machine
FALL_TRANSITION_TIMEOUT = 2.0
LOW_POSTURE_CONFIRM_SECONDS = 2.0
FALLEN_RATIO_THRESHOLD = 0.8

RECOVERY_CONFIRM_SECONDS = 3.0


class FallTemporalAnalyzer:

    def __init__(self):

        # Lịch sử Pose
        self.history = deque(maxlen=90)
        self.detection_history = deque(maxlen=15)
        self.pose_history = deque(maxlen=5)

        # Lịch sử vận tốc đi xuống
        self.motion_history = deque(maxlen=90)

        # Trạng thái
        self.state = "NORMAL"

        # Thời gian
        self.transition_time = None
        self.low_posture_start = None
        self.upright_start = None
        self.recovery_start = None

        # Vận tốc cực đại trong quá trình chuyển tiếp
        self.transition_peak_velocity = 0.0

        # Pose
        self.last_pose_time = None

    # =====================================================
    # RESET
    # =====================================================

    def reset_transition(self):

        self.transition_time = None
        self.low_posture_start = None
        self.upright_start = None
        self.recovery_start = None

        self.transition_peak_velocity = 0.0

    def reset_histories(self):

        self.history.clear()
        self.detection_history.clear()
        self.pose_history.clear()
        self.motion_history.clear()

    # =====================================================
    # POSE SMOOTHING
    # =====================================================

    def smooth_pose(self, features):

        self.pose_history.append({
            "angle": features["torso_angle"],
            "hip_y": features["hip_y"],
            "hip_x": features["hip_x"]
        })

        angles = [
            item["angle"]
            for item in self.pose_history
        ]

        hip_ys = [
            item["hip_y"]
            for item in self.pose_history
        ]

        hip_xs = [
            item["hip_x"]
            for item in self.pose_history
        ]

        return {
            "torso_angle": float(np.median(angles)),
            "hip_y": float(np.median(hip_ys)),
            "hip_x": float(np.median(hip_xs))
        }

    # =====================================================
    # MOTION HISTORY
    # =====================================================

    def update_motion_history(
        self,
        current_time,
        hip_velocity
    ):

        hip_speed = max(0.0, float(hip_velocity))

        self.motion_history.append({
            "time": current_time,
            "velocity": hip_speed
        })

        # Xóa dữ liệu quá cũ
        while self.motion_history:

            age = (
                current_time
                - self.motion_history[0]["time"]
            )

            if age <= MOTION_HISTORY_SECONDS:
                break

            self.motion_history.popleft()

        peak_velocity = max(
            [
                item["velocity"]
                for item in self.motion_history
            ] + [0.0]
        )

        return peak_velocity
    # =====================================================
    # MAIN TEMPORAL ANALYSIS
    # =====================================================

    def update(
        self,
        detection_class,
        detection_confidence,
        features
    ):

        current_time = time.time()

        # -------------------------------------------------
        # 1. YOLO DETECTION
        # -------------------------------------------------

        is_fallen = (
            detection_class == "Fallen"
            and detection_confidence >= CONF_THRESHOLD
        )

        self.detection_history.append(is_fallen)

        fallen_ratio = (
            sum(self.detection_history)
            / len(self.detection_history)
            if self.detection_history
            else 0.0
        )

        # -------------------------------------------------
        # 2. POSE UNAVAILABLE
        # -------------------------------------------------

        if features is None:

            if self.last_pose_time is None:
                self.last_pose_time = current_time

            pose_lost_duration = (
                current_time - self.last_pose_time
            )

            if pose_lost_duration >= POSE_LOST_TIMEOUT:

                if self.state in (
                    "FALL_TRANSITION",
                    "POSTURE_VERIFICATION"
                ):

                    print(
                        "[TEMPORAL] Pose lost timeout. "
                        "Resetting fall verification."
                    )

                    self.state = "NORMAL"

                self.reset_transition()
                self.reset_histories()

            return {
                "state": self.state,
                "fallen_ratio": fallen_ratio,
                "average_velocity": 0.0,
                "peak_downward_velocity": 0.0,
                "low_duration": 0.0,
                "angle_change": 0.0,
                "hip_drop": 0.0,
                "transition_detected": False,
                "reason": "Pose unavailable"
            }

        # -------------------------------------------------
        # 3. UPDATE POSE TIME
        # -------------------------------------------------

        self.last_pose_time = current_time

        hip_velocity = float(features["hip_velocity"])

        # -------------------------------------------------
        # 4. SMOOTH POSE
        # -------------------------------------------------

        smoothed_features = self.smooth_pose(features)

        torso_angle = smoothed_features["torso_angle"]
        hip_y = smoothed_features["hip_y"]

        # -------------------------------------------------
        # 5. UPDATE MOTION HISTORY
        # -------------------------------------------------

        peak_downward_velocity = self.update_motion_history(
            current_time,
            hip_velocity
        )

        # -------------------------------------------------
        # 6. UPDATE POSE HISTORY
        # -------------------------------------------------

        self.history.append({
            "time": current_time,
            "angle": torso_angle,
            "hip_x": smoothed_features["hip_x"],
            "hip_y": hip_y,
            "velocity": hip_velocity
        })

        recent_samples = [
            item
            for item in self.history
            if current_time - item["time"] <= 1.0
        ]

        average_velocity = (
            float(np.mean([
                item["velocity"]
                for item in recent_samples
            ]))
            if recent_samples
            else 0.0
        )

        # -------------------------------------------------
        # 7. POSTURE ANALYSIS
        # -------------------------------------------------

        low_posture = (
            torso_angle >= LOW_POSTURE_ANGLE_THRESHOLD
        )

        if low_posture:

            if self.low_posture_start is None:
                self.low_posture_start = current_time

            low_duration = (
                current_time - self.low_posture_start
            )

        else:

            self.low_posture_start = None
            low_duration = 0.0

        # -------------------------------------------------
        # 8. UPRIGHT CONFIRMATION
        # -------------------------------------------------

        upright_posture = (
            torso_angle <= UPRIGHT_ANGLE_THRESHOLD
        )

        if upright_posture:

            if self.upright_start is None:
                self.upright_start = current_time

            upright_duration = (
                current_time - self.upright_start
            )

        else:

            self.upright_start = None
            upright_duration = 0.0

        confirmed_upright = (
            upright_duration >= UPRIGHT_CONFIRM_SECONDS
        )

        # -------------------------------------------------
        # 9. FIND PREVIOUS UPRIGHT POSE
        # -------------------------------------------------

        upright_samples = [
            item
            for item in self.history
            if (
                current_time - item["time"] <= 3.0
                and item["angle"] <= UPRIGHT_ANGLE_THRESHOLD
            )
        ]
        upright_confirmed = (
            len(upright_samples) >= 5
            and (
                upright_samples[-1]["time"]
                - upright_samples[0]["time"]
            ) >= UPRIGHT_CONFIRM_SECONDS
        )

        angle_change = 0.0
        hip_drop = 0.0
        hip_displacement = 0.0
        transition_detected = False

        if low_posture and upright_samples:

            previous_upright = upright_samples[-1]

            angle_change = (
                torso_angle - previous_upright["angle"]
            )

            hip_drop = (
                hip_y - previous_upright["hip_y"]
            )

            delta_hip_x = (
                smoothed_features["hip_x"]
                - previous_upright["hip_x"]
            )

            delta_hip_y = (
                hip_y - previous_upright["hip_y"]
            )

            hip_displacement = math.sqrt(
                delta_hip_x ** 2 + delta_hip_y ** 2
            )
            # Vận tốc được lấy từ motion_history 2 giây,
            # không chỉ từ một cửa sổ 1 giây.
            transition_detected = (
                angle_change >= FALL_ANGLE_CHANGE_THRESHOLD
                and hip_displacement >= FALL_HIP_DROP_THRESHOLD
                and peak_downward_velocity >= FALL_VELOCITY_THRESHOLD
            )

        # -------------------------------------------------
        # 10. DEBUG
        # -------------------------------------------------

        # print(
        #     f"[TEMPORAL DEBUG] "
        #     f"Raw angle={features['torso_angle']:.1f} | "
        #     f"Smooth angle={torso_angle:.1f} | "
        #     f"Current velocity={hip_velocity:.1f} | "
        #     f"Peak motion={peak_downward_velocity:.1f} | "
        #     f"Angle change={angle_change:.1f} | "
        #     f"Hip drop={hip_drop:.1f} | "
        #     f"Low={low_posture} | "
        #     f"Low duration={low_duration:.2f}s | "
        #     f"Transition={transition_detected} | "
        #     f"State={self.state} | "
        #     f"Fallen ratio={fallen_ratio:.2f}"
        # )

        # =================================================
        # 11. STATE MACHINE
        # =================================================

        # -------------------------------------------------
        # NORMAL
        # -------------------------------------------------

        if self.state == "NORMAL":

            if transition_detected:

                self.state = "FALL_TRANSITION"

                self.transition_time = current_time

                self.transition_peak_velocity = (
                    peak_downward_velocity
                )

                print(
                    "[TEMPORAL] Fall transition detected"
                )

        # -------------------------------------------------
        # FALL_TRANSITION
        # -------------------------------------------------

        elif self.state == "FALL_TRANSITION":

            if confirmed_upright:

                print(
                    "[TEMPORAL] Upright confirmed. "
                    "Canceling fall transition."
                )

                self.state = "NORMAL"
                self.reset_transition()

            else:

                self.transition_peak_velocity = max(
                    self.transition_peak_velocity,
                    peak_downward_velocity
                )

                if (
                    low_posture
                    and low_duration >= 1.0
                ):

                    self.state = "POSTURE_VERIFICATION"

                    print(
                        "[TEMPORAL] Posture verification started"
                    )

        # -------------------------------------------------
        # POSTURE_VERIFICATION
        # -------------------------------------------------

        elif self.state == "POSTURE_VERIFICATION":

            if confirmed_upright:

                print(
                    "[TEMPORAL] Person returned upright. "
                    "Canceling fall verification."
                )

                self.state = "NORMAL"
                self.reset_transition()

            elif self.transition_time is not None:

                transition_duration = (
                    current_time - self.transition_time
                )

                # Tiếp tục cập nhật vận tốc cực đại
                self.transition_peak_velocity = max(
                    self.transition_peak_velocity,
                    peak_downward_velocity
                )

                enough_detection_evidence = (
                    fallen_ratio >= FALLEN_RATIO_THRESHOLD
                )

                enough_motion_evidence = (
                    self.transition_peak_velocity
                    >= FALL_VELOCITY_THRESHOLD
                )

                enough_posture_duration = (
                    low_duration >= LOW_POSTURE_CONFIRM_SECONDS
                )

                enough_transition_duration = (
                    transition_duration >= FALL_TRANSITION_TIMEOUT
                )

                print(
                    f"[VERIFY DEBUG] "
                    f"Transition={transition_duration:.2f}s | "
                    f"Low={low_duration:.2f}s | "
                    f"Detection={fallen_ratio:.2f} | "
                    f"Motion={self.transition_peak_velocity:.1f} | "
                    f"Ready="
                    f"{enough_detection_evidence and enough_motion_evidence and enough_posture_duration and enough_transition_duration}"
                )

                if (
                    enough_transition_duration
                    and enough_posture_duration
                    and enough_detection_evidence
                    and enough_motion_evidence
                ):

                    self.state = "FALL_CONFIRMED"

                    print(
                        "[TEMPORAL] FALL CONFIRMED"
                    )

                # -------------------------------------------------
        # FALL_CONFIRMED
        # -------------------------------------------------

        elif self.state == "FALL_CONFIRMED":

            print(
                f"[RECOVERY DEBUG] "
                f"Angle={torso_angle:.1f} | "
                f"Low={low_posture} | "
                f"YOLO Fallen={is_fallen} | "
                f"Recovery start={self.recovery_start}"
            )

            if upright_confirmed and not is_fallen:

                if self.recovery_start is None:

                    self.recovery_start = current_time

                    print(
                        "[RECOVERY] Timer started"
                    )

                else:

                    recovery_duration = (
                        current_time - self.recovery_start
                    )

                    print(
                        f"[RECOVERY] "
                        f"Duration={recovery_duration:.2f}s"
                    )

                    if recovery_duration >= RECOVERY_CONFIRM_SECONDS:

                        self.state = "RECOVERED"

                        print(
                            "[TEMPORAL] RECOVERED"
                        )

            else:

                self.recovery_start = None

                print(
                    "[RECOVERY] Timer reset"
                )

        # -------------------------------------------------
        # RECOVERED
        # -------------------------------------------------

        elif self.state == "RECOVERED":

            self.state = "NORMAL"

            self.reset_histories()
            self.reset_transition()

            self.last_pose_time = current_time

            print(
                "[TEMPORAL] State reset to NORMAL"
            )

        # -------------------------------------------------
        # 12. RETURN ANALYSIS
        # -------------------------------------------------

        return {
            "state": self.state,
            "fallen_ratio": fallen_ratio,
            "average_velocity": average_velocity,
            "peak_downward_velocity": peak_downward_velocity,
            "low_duration": low_duration,
            "angle_change": angle_change,
            "hip_drop": hip_drop,
            "hip_displacement": hip_displacement,
            "transition_detected": transition_detected,
            "reason": "Analyzing"
        }
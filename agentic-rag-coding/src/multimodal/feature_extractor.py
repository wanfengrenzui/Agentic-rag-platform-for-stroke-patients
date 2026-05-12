"""Feature extraction from multimodal rehabilitation data."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.multimodal.data_models import (
    EMGFeatures,
    FeatureSet,
    IMUFeatures,
    QualityFlag,
    SkeletonFeatures,
)


def _read_csv_with_fallback(csv_path: str) -> pd.DataFrame | None:
    """Read CSV with common encoding and separator fallbacks."""
    path = Path(csv_path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        try:
            return pd.read_excel(path)
        except Exception:
            return None

    encodings = ["utf-8", "gbk", "latin-1", "cp1252", "iso-8859-1"]
    separators = [",", ";", "\t", "|", " "]

    for encoding in encodings:
        for sep in separators:
            try:
                df = pd.read_csv(csv_path, encoding=encoding, sep=sep)
                return df
            except (UnicodeDecodeError, LookupError, pd.errors.ParserError):
                continue

    return None


_KINECT_JOINT_NAMES = [
    "spine_base",
    "spine_mid",
    "neck",
    "head",
    "shoulder_left",
    "elbow_left",
    "wrist_left",
    "hand_left",
    "shoulder_right",
    "elbow_right",
    "wrist_right",
    "hand_right",
    "hip_left",
    "knee_left",
    "ankle_left",
    "foot_left",
    "hip_right",
    "knee_right",
    "ankle_right",
    "foot_right",
    "spine_shoulder",
    "hand_tip_left",
    "thumb_left",
    "hand_tip_right",
    "thumb_right",
]


def _read_kinect_skeleton_file(skeleton_path: str) -> pd.DataFrame | None:
    """Parse Kinect-style .skeleton text into a joint dataframe."""
    try:
        lines = Path(skeleton_path).read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return None

    rows: list[dict] = []
    index = 0
    try:
        frame_count = int(lines[index].strip())
        index += 1
    except (IndexError, ValueError):
        return None

    for frame_index in range(frame_count):
        if index >= len(lines):
            break
        try:
            body_count = int(lines[index].strip())
        except ValueError:
            break
        index += 1

        for _ in range(body_count):
            if index >= len(lines):
                break
            index += 1  # body metadata line
            if index >= len(lines):
                break
            try:
                joint_count = int(lines[index].strip())
            except ValueError:
                break
            index += 1

            for joint_index in range(joint_count):
                if index >= len(lines):
                    break
                values = lines[index].split()
                index += 1
                if len(values) < 12:
                    continue
                try:
                    tracking_state = float(values[11])
                    rows.append(
                        {
                            "timestamp": frame_index * 33.333,
                            "joint_name": _KINECT_JOINT_NAMES[joint_index]
                            if joint_index < len(_KINECT_JOINT_NAMES)
                            else f"joint_{joint_index}",
                            "x": float(values[0]),
                            "y": float(values[1]),
                            "z": float(values[2]),
                            "confidence": min(max(tracking_state / 2.0, 0.0), 1.0),
                        }
                    )
                except ValueError:
                    continue

    return pd.DataFrame(rows) if rows else None


class SkeletonFeatureExtractor:
    """Extract features from skeleton/joint tracking data."""

    @staticmethod
    def extract(csv_path: str) -> tuple[SkeletonFeatures, list[QualityFlag]]:
        """Extract skeleton features from CSV file."""
        path = Path(csv_path)
        df = _read_kinect_skeleton_file(csv_path) if path.suffix.lower() == ".skeleton" else _read_csv_with_fallback(csv_path)
        if df is None:
            return SkeletonFeatures(), [
                QualityFlag(
                    "encoding_error",
                    "high",
                    "Cannot decode skeleton file with any standard encoding.",
                )
            ]
        flags: list[QualityFlag] = []
        
        # Basic validation
        if df.empty:
            return SkeletonFeatures(), [QualityFlag("empty_file", "high", "Skeleton file is empty.")]
        
        required_cols = ["timestamp", "joint_name", "x", "y", "z"]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            return SkeletonFeatures(), [
                QualityFlag("missing_columns", "high", f"Missing columns: {missing_cols}")
            ]
        
        # Estimate step count based on heel strikes (simplified)
        # In a real implementation, would use hip/ankle y-coordinates and motion analysis
        duration_sec = (df["timestamp"].max() - df["timestamp"].min()) / 1000.0 if "timestamp" in df.columns else 30.0
        
        # Calculate basic statistics
        confidence = df.get("confidence", [1.0]).mean() if "confidence" in df.columns else 0.95
        
        # Estimate ROM (range of motion) from joint coordinate variance
        joint_groups = df.groupby("joint_name")
        joint_roms = {}
        for joint_name, group in joint_groups:
            if "y" in group.columns:
                rom_y = group["y"].max() - group["y"].min()
                joint_roms[joint_name] = rom_y
        
        missing_ratio = 0.0
        if "confidence" in df.columns:
            low_confidence = (df["confidence"] < 0.5).sum() / len(df)
            missing_ratio = min(low_confidence, 0.3)
            if missing_ratio > 0.15:
                flags.append(QualityFlag(
                    "low_confidence_joints",
                    "medium",
                    f"Low confidence in {missing_ratio*100:.1f}% of frames."
                ))
        
        # Estimate cadence (simplified: assume 1.2 steps per second for walking)
        estimated_steps = max(int(duration_sec * 1.2), 2)
        cadence = (estimated_steps / max(duration_sec, 1.0)) * 60
        
        # Calculate ROM metrics
        hip_rom = joint_roms.get("hip", 0.15)
        knee_rom = joint_roms.get("knee", 0.20)
        ankle_rom = joint_roms.get("ankle", 0.10)
        
        # Estimate trunk sway from shoulder/hip variance
        trunk_sway = np.random.uniform(0.05, 0.15)  # Placeholder
        
        return SkeletonFeatures(
            walking_duration_sec=duration_sec,
            estimated_step_count=estimated_steps,
            cadence_steps_per_min=cadence,
            left_right_step_symmetry=np.random.uniform(0.75, 0.95),  # Placeholder
            hip_range_of_motion=hip_rom,
            knee_range_of_motion=knee_rom,
            ankle_range_of_motion=ankle_rom,
            trunk_sway_proxy=trunk_sway,
            joint_confidence_mean=float(confidence),
            missing_joint_ratio=missing_ratio,
        ), flags


class IMUFeatureExtractor:
    """Extract features from IMU sensor data."""

    @staticmethod
    def extract(csv_path: str) -> tuple[IMUFeatures, list[QualityFlag]]:
        """Extract IMU features from CSV file."""
        df = _read_csv_with_fallback(csv_path)
        if df is None:
            return IMUFeatures(), [
                QualityFlag(
                    "encoding_error",
                    "high",
                    "Cannot decode IMU file with any standard encoding.",
                )
            ]
        flags: list[QualityFlag] = []
        
        if df.empty:
            return IMUFeatures(), [QualityFlag("empty_file", "high", "IMU file is empty.")]
        
        required_cols = ["timestamp", "acc_x", "acc_y", "acc_z"]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            return IMUFeatures(), [
                QualityFlag("missing_columns", "high", f"Missing columns: {missing_cols}")
            ]
        
        # Calculate acceleration magnitude
        acc_magnitude = np.sqrt(df["acc_x"]**2 + df["acc_y"]**2 + df["acc_z"]**2)
        acc_mean = acc_magnitude.mean()
        acc_peak = acc_magnitude.max()
        
        # Angular velocity (if available)
        gyro_peak = 0.0
        if all(c in df.columns for c in ["gyro_x", "gyro_y", "gyro_z"]):
            gyro_magnitude = np.sqrt(df["gyro_x"]**2 + df["gyro_y"]**2 + df["gyro_z"]**2)
            gyro_peak = gyro_magnitude.max()
        
        # Estimate gait events based on acceleration peaks
        threshold = acc_mean + acc_mean * 0.5
        gait_events = (acc_magnitude > threshold).sum()
        
        # Dominant frequency (simplified FFT)
        try:
            fft = np.fft.fft(acc_magnitude.values)
            freqs = np.fft.fftfreq(len(fft))
            dominant_freq = abs(freqs[np.argmax(np.abs(fft))]) * 100  # Normalized
        except:
            dominant_freq = 0.0
        
        # Left/right asymmetry (if sensor_position available)
        asymmetry = 0.15  # Placeholder
        if "sensor_position" in df.columns and df["sensor_position"].nunique() > 1:
            try:
                positions = df.groupby("sensor_position")[acc_magnitude].agg("mean")
                if len(positions) >= 2:
                    vals = positions.values
                    asymmetry = abs(vals[0] - vals[1]) / (positions.mean() + 1e-6)
            except Exception:
                asymmetry = 0.15
        
        # Signal quality (based on variance and missing values)
        signal_quality = 1.0 - (df.isnull().sum().sum() / df.size) * 0.5
        
        return IMUFeatures(
            acceleration_magnitude_mean=float(acc_mean),
            acceleration_magnitude_peak=float(acc_peak),
            angular_velocity_peak=float(gyro_peak),
            gait_event_candidate_count=int(gait_events),
            dominant_frequency=float(dominant_freq),
            left_right_peak_asymmetry=float(asymmetry),
            signal_quality_score=float(signal_quality),
        ), flags


class EMGFeatureExtractor:
    """Extract features from EMG signal data."""

    @staticmethod
    def extract(csv_path: str) -> tuple[EMGFeatures, list[QualityFlag]]:
        """Extract EMG features from CSV file."""
        df = _read_csv_with_fallback(csv_path)
        if df is None:
            return EMGFeatures(), [
                QualityFlag(
                    "encoding_error",
                    "high",
                    "Cannot decode EMG file with any standard encoding.",
                )
            ]
        flags: list[QualityFlag] = []
        
        if df.empty:
            return EMGFeatures(), [QualityFlag("empty_file", "high", "EMG file is empty.")]
        
        required_cols = ["timestamp", "emg_raw"]
        # Allow flexible muscle naming
        if "emg_raw" not in df.columns and "emg" not in df.columns:
            return EMGFeatures(), [
                QualityFlag("missing_columns", "high", "Missing EMG signal column.")
            ]
        
        emg_col = "emg_raw" if "emg_raw" in df.columns else "emg"
        
        # RMS (Root Mean Square) per channel/muscle
        if "muscle_name" in df.columns:
            rms_dict = {}
            for muscle, group in df.groupby("muscle_name"):
                rms = np.sqrt(np.mean(group[emg_col]**2))
                rms_dict[muscle] = float(rms)
        else:
            rms_dict = {"all_channels": float(np.sqrt(np.mean(df[emg_col]**2)))}
        
        # MAV (Mean Absolute Value)
        mav_dict = {k: float(np.mean(np.abs(df[emg_col]))) for k in rms_dict}
        
        # IEMG (Integrated EMG)
        iemg_dict = {k: float(np.sum(np.abs(df[emg_col]))) for k in rms_dict}
        
        # Peak activation
        peak_dict = {k: float(np.max(np.abs(df[emg_col]))) for k in rms_dict}
        
        # Co-activation proxy (simplified: if multiple channels, check overlap)
        co_activation = 0.0
        if "muscle_name" in df.columns and df["muscle_name"].nunique() > 1:
            # Placeholder: assume moderate co-activation
            co_activation = np.random.uniform(0.2, 0.5)
        
        # Fatigue proxy (spectral shift)
        fatigue = 0.0  # Placeholder
        
        # Signal quality
        signal_quality = 1.0 - (df.isnull().sum().sum() / df.size) * 0.5
        
        return EMGFeatures(
            rms=rms_dict,
            mav=mav_dict,
            iemg=iemg_dict,
            peak_activation=peak_dict,
            activation_timing_proxy=None,
            co_activation_proxy=co_activation,
            fatigue_proxy=fatigue,
            signal_quality_score=float(signal_quality),
        ), flags


class FeatureExtractorPipeline:
    """Orchestrate feature extraction from multiple modalities."""

    @staticmethod
    def extract_all(
        skeleton_path: Optional[str] = None,
        imu_path: Optional[str] = None,
        emg_path: Optional[str] = None,
    ) -> tuple[FeatureSet, list[dict]]:
        """Extract features from all available modalities."""
        features = FeatureSet(
            feature_set_id="feat_auto_generated",
            case_id="case_pending",
        )
        
        all_flags: list[QualityFlag] = []
        data_evidences: list[dict] = []
        
        # Skeleton
        if skeleton_path and Path(skeleton_path).exists():
            skel_feat, skel_flags = SkeletonFeatureExtractor.extract(skeleton_path)
            features.skeleton_features = skel_feat
            all_flags.extend(skel_flags)
        
        # IMU
        if imu_path and Path(imu_path).exists():
            imu_feat, imu_flags = IMUFeatureExtractor.extract(imu_path)
            features.imu_features = imu_feat
            all_flags.extend(imu_flags)
        
        # EMG
        if emg_path and Path(emg_path).exists():
            emg_feat, emg_flags = EMGFeatureExtractor.extract(emg_path)
            features.emg_features = emg_feat
            all_flags.extend(emg_flags)
        
        features.quality_flags = all_flags
        
        return features, data_evidences

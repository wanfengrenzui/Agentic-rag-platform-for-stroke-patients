"""Feature extraction from multimodal rehabilitation data."""

from __future__ import annotations

from datetime import datetime
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

_FALLBACK_ENCODINGS: tuple[str, ...] = (
    "utf-8",
    "gbk",
    "latin-1",
    "cp1252",
    "iso-8859-1",
)


def _read_csv_with_fallback(csv_path: str) -> tuple[Optional[pd.DataFrame], Optional[str], Optional[str]]:
    """Read CSV with encoding fallback support. Returns (dataframe, used_encoding, error_message)"""
    last_error: Optional[str] = None
    path = Path(csv_path)

    for encoding in _FALLBACK_ENCODINGS:
        try:
            df = pd.read_csv(path, encoding=encoding)
            return df, encoding, None
        except UnicodeDecodeError as exc:
            last_error = str(exc)
        except pd.errors.ParserError as exc:
            last_error = str(exc)
        except FileNotFoundError:
            return None, None, f"File not found: {csv_path}"
        except Exception as exc:
            last_error = str(exc)

    return None, None, last_error or "Unknown CSV read error."


class SkeletonFeatureExtractor:
    """Extract features from skeleton/joint tracking data."""

    @staticmethod
    def extract(csv_path: str) -> tuple[SkeletonFeatures, list[QualityFlag]]:
        """Extract skeleton features from CSV file."""
        flags: list[QualityFlag] = []
        empty_features = SkeletonFeatures()

        if not Path(csv_path).exists():
            flags.append(QualityFlag("file_not_found", "high", f"Skeleton file not found: {csv_path}"))
            return empty_features, flags

        df, used_encoding, read_error = _read_csv_with_fallback(csv_path)
        if df is None:
            flags.append(
                QualityFlag(
                    "encoding_or_parse_error",
                    "high",
                    f"Cannot read skeleton CSV. Detail: {read_error}",
                )
            )
            return empty_features, flags

        if df.empty:
            flags.append(QualityFlag("empty_file", "high", "Skeleton CSV is empty."))
            return empty_features, flags

        # Normalize columns to lowercase
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Find timestamp, joint, and coordinate columns
        timestamp_col = None
        for col in ["timestamp", "time", "ts"]:
            if col in df.columns:
                timestamp_col = col
                break

        joint_col = None
        for col in ["joint_name", "joint", "name"]:
            if col in df.columns:
                joint_col = col
                break

        if not joint_col:
            flags.append(QualityFlag("missing_column", "high", "Missing joint name column."))
            return empty_features, flags

        # Get coordinate columns
        x_col = next((c for c in ["x", "pos_x", "joint_x"] if c in df.columns), None)
        y_col = next((c for c in ["y", "pos_y", "joint_y"] if c in df.columns), None)
        z_col = next((c for c in ["z", "pos_z", "joint_z"] if c in df.columns), None)
        conf_col = next((c for c in ["confidence", "conf", "score"] if c in df.columns), None)

        if not (x_col and y_col and z_col):
            flags.append(QualityFlag("missing_column", "high", "Missing coordinate columns."))
            return empty_features, flags

        # Estimate duration
        duration_sec = None
        if timestamp_col:
            ts = pd.to_numeric(df[timestamp_col], errors="coerce").dropna()
            if ts.shape[0] >= 2:
                ts_sorted = ts.sort_values().to_numpy()
                duration_raw = float(ts_sorted[-1] - ts_sorted[0])
                # Heuristic: if median step is large, divide by 1000 (milliseconds)
                if duration_raw > 100:
                    duration_sec = duration_raw / 1000.0
                else:
                    duration_sec = duration_raw

        # Extract ROM per joint
        joint_roms: dict[str, float] = {}
        for joint_name, group in df.groupby(joint_col, dropna=True):
            joint_name_str = str(joint_name).lower().strip()
            ranges: list[float] = []
            for col in [x_col, y_col, z_col]:
                values = pd.to_numeric(group[col], errors="coerce").dropna()
                if not values.empty:
                    ranges.append(float(values.max() - values.min()))
            if ranges:
                joint_roms[joint_name_str] = float(np.mean(ranges))

        # Group ROMs by joint type
        hip_values = [v for k, v in joint_roms.items() if "hip" in k]
        knee_values = [v for k, v in joint_roms.items() if "knee" in k]
        ankle_values = [v for k, v in joint_roms.items() if "ankle" in k]

        hip_rom = float(np.mean(hip_values)) if hip_values else None
        knee_rom = float(np.mean(knee_values)) if knee_values else None
        ankle_rom = float(np.mean(ankle_values)) if ankle_values else None

        # Estimate symmetry
        left_knee = [v for k, v in joint_roms.items() if "left" in k and "knee" in k]
        right_knee = [v for k, v in joint_roms.items() if "right" in k and "knee" in k]
        symmetry: Optional[float] = None
        if left_knee and right_knee:
            l_val = float(np.mean(left_knee))
            r_val = float(np.mean(right_knee))
            denom = max(abs(l_val), abs(r_val), 1e-6)
            symmetry = float(1.0 - abs(l_val - r_val) / denom)

        # Estimate step count and cadence
        step_count: Optional[int] = None
        cadence: Optional[float] = None
        if duration_sec and duration_sec > 0:
            step_count = max(1, int(round(duration_sec * 1.6)))
            cadence = float(step_count / duration_sec * 60.0)

        # Confidence
        confidence_mean: Optional[float] = None
        missing_joint_ratio: Optional[float] = None
        if conf_col:
            conf_vals = pd.to_numeric(df[conf_col], errors="coerce")
            valid = conf_vals.dropna()
            if not valid.empty:
                confidence_mean = float(valid.mean())
                missing_joint_ratio = float((valid < 0.5).mean())

        features = SkeletonFeatures(
            walking_duration_sec=duration_sec,
            estimated_step_count=step_count,
            cadence_steps_per_min=cadence,
            left_right_step_symmetry=symmetry,
            hip_range_of_motion=hip_rom,
            knee_range_of_motion=knee_rom,
            ankle_range_of_motion=ankle_rom,
            trunk_sway_proxy=None,
            joint_confidence_mean=confidence_mean,
            missing_joint_ratio=missing_joint_ratio,
        )
        return features, flags


class IMUFeatureExtractor:
    """Extract features from IMU sensor data."""

    @staticmethod
    def extract(csv_path: str) -> tuple[IMUFeatures, list[QualityFlag]]:
        """Extract IMU features from CSV file."""
        flags: list[QualityFlag] = []
        empty_features = IMUFeatures()

        if not Path(csv_path).exists():
            flags.append(QualityFlag("file_not_found", "high", f"IMU file not found: {csv_path}"))
            return empty_features, flags

        df, used_encoding, read_error = _read_csv_with_fallback(csv_path)
        if df is None:
            flags.append(
                QualityFlag(
                    "encoding_or_parse_error",
                    "high",
                    f"Cannot read IMU CSV. Detail: {read_error}",
                )
            )
            return empty_features, flags

        if df.empty:
            flags.append(QualityFlag("empty_file", "high", "IMU CSV is empty."))
            return empty_features, flags

        # Normalize columns
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Find acceleration columns
        acc_x = next((c for c in ["acc_x", "ax", "accel_x"] if c in df.columns), None)
        acc_y = next((c for c in ["acc_y", "ay", "accel_y"] if c in df.columns), None)
        acc_z = next((c for c in ["acc_z", "az", "accel_z"] if c in df.columns), None)

        if not (acc_x and acc_y and acc_z):
            flags.append(QualityFlag("missing_column", "high", "Missing acceleration columns."))
            return empty_features, flags

        # Extract acceleration
        ax = pd.to_numeric(df[acc_x], errors="coerce").fillna(0.0)
        ay = pd.to_numeric(df[acc_y], errors="coerce").fillna(0.0)
        az = pd.to_numeric(df[acc_z], errors="coerce").fillna(0.0)

        acc_mag = np.sqrt(ax.to_numpy() ** 2 + ay.to_numpy() ** 2 + az.to_numpy() ** 2)
        acc_mean = float(np.mean(acc_mag))
        acc_peak = float(np.max(acc_mag))

        # Gyroscope (optional)
        angular_peak: Optional[float] = None
        gx_col = next((c for c in ["gyro_x", "gx"] if c in df.columns), None)
        gy_col = next((c for c in ["gyro_y", "gy"] if c in df.columns), None)
        gz_col = next((c for c in ["gyro_z", "gz"] if c in df.columns), None)
        if gx_col and gy_col and gz_col:
            gx = pd.to_numeric(df[gx_col], errors="coerce").fillna(0.0).to_numpy()
            gy = pd.to_numeric(df[gy_col], errors="coerce").fillna(0.0).to_numpy()
            gz = pd.to_numeric(df[gz_col], errors="coerce").fillna(0.0).to_numpy()
            gyro_mag = np.sqrt(gx**2 + gy**2 + gz**2)
            angular_peak = float(np.max(gyro_mag))

        # Gait events (peak count)
        threshold = acc_mean + 0.5 * acc_mean
        gait_events = int(np.sum(acc_mag > threshold))

        # Asymmetry
        asymmetry: Optional[float] = None
        sensor_pos = next((c for c in ["sensor_position", "position"] if c in df.columns), None)
        if sensor_pos:
            pos_series = df[sensor_pos].astype(str).str.lower()
            left_mask = pos_series.str.contains("left", na=False).to_numpy()
            right_mask = pos_series.str.contains("right", na=False).to_numpy()
            if np.any(left_mask) and np.any(right_mask):
                left_peak = float(np.max(acc_mag[left_mask]))
                right_peak = float(np.max(acc_mag[right_mask]))
                denom = max(left_peak, right_peak, 1e-6)
                asymmetry = float(abs(left_peak - right_peak) / denom)

        # Signal quality
        missing = float(pd.isna(df[[acc_x, acc_y, acc_z]]).sum().sum()) / float(df[[acc_x, acc_y, acc_z]].shape[0] * 3)
        signal_quality = float(max(0.0, 1.0 - missing))

        features = IMUFeatures(
            acceleration_magnitude_mean=acc_mean,
            acceleration_magnitude_peak=acc_peak,
            angular_velocity_peak=angular_peak,
            gait_event_candidate_count=gait_events,
            dominant_frequency=None,
            left_right_peak_asymmetry=asymmetry,
            signal_quality_score=signal_quality,
        )
        return features, flags


class EMGFeatureExtractor:
    """Extract features from EMG signal data."""

    @staticmethod
    def extract(csv_path: str) -> tuple[EMGFeatures, list[QualityFlag]]:
        """Extract EMG features from CSV file."""
        flags: list[QualityFlag] = []
        empty_features = EMGFeatures()

        if not Path(csv_path).exists():
            flags.append(QualityFlag("file_not_found", "high", f"EMG file not found: {csv_path}"))
            return empty_features, flags

        df, used_encoding, read_error = _read_csv_with_fallback(csv_path)
        if df is None:
            flags.append(
                QualityFlag(
                    "encoding_or_parse_error",
                    "high",
                    f"Cannot read EMG CSV. Detail: {read_error}",
                )
            )
            return empty_features, flags

        if df.empty:
            flags.append(QualityFlag("empty_file", "high", "EMG CSV is empty."))
            return empty_features, flags

        # Normalize columns
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Find signal column
        signal_col = next((c for c in ["emg_raw", "emg", "signal", "value"] if c in df.columns), None)
        if not signal_col:
            flags.append(QualityFlag("missing_column", "high", "Missing EMG signal column."))
            return empty_features, flags

        # Find muscle column
        muscle_col = next((c for c in ["muscle_name", "muscle", "channel"] if c in df.columns), None)

        signal = pd.to_numeric(df[signal_col], errors="coerce")
        if signal.dropna().empty:
            flags.append(QualityFlag("invalid_signal", "high", "No valid EMG signal values."))
            return empty_features, flags

        # If no muscle column, treat all as one channel
        if not muscle_col:
            abs_signal = np.abs(signal.dropna().to_numpy())
            rms = {"all_channels": float(np.sqrt(np.mean(abs_signal ** 2)))}
            mav = {"all_channels": float(np.mean(abs_signal))}
            iemg = {"all_channels": float(np.sum(abs_signal))}
            peak_activation = {"all_channels": float(np.max(abs_signal))}
        else:
            rms = {}
            mav = {}
            iemg = {}
            peak_activation = {}
            for muscle, group in df.groupby(muscle_col, dropna=False):
                muscle_key = str(muscle).strip()
                values = pd.to_numeric(group[signal_col], errors="coerce").dropna().to_numpy()
                if values.size == 0:
                    continue
                abs_values = np.abs(values)
                rms[muscle_key] = float(np.sqrt(np.mean(values ** 2)))
                mav[muscle_key] = float(np.mean(abs_values))
                iemg[muscle_key] = float(np.sum(abs_values))
                peak_activation[muscle_key] = float(np.max(abs_values))

        # Signal quality
        missing = float(signal.isna().sum()) / len(signal)
        signal_quality = float(max(0.0, 1.0 - missing))

        features = EMGFeatures(
            rms=rms,
            mav=mav,
            iemg=iemg,
            peak_activation=peak_activation,
            activation_timing_proxy=None,
            co_activation_proxy=None,
            fatigue_proxy=None,
            signal_quality_score=signal_quality,
        )
        return features, flags


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

        # Skeleton
        if skeleton_path:
            try:
                sk_features, sk_flags = SkeletonFeatureExtractor.extract(skeleton_path)
                features.skeleton_features = sk_features
                all_flags.extend(sk_flags)
            except Exception as exc:
                all_flags.append(QualityFlag("skeleton_error", "high", f"Skeleton extraction failed: {exc}"))

        # IMU
        if imu_path:
            try:
                imu_features, imu_flags = IMUFeatureExtractor.extract(imu_path)
                features.imu_features = imu_features
                all_flags.extend(imu_flags)
            except Exception as exc:
                all_flags.append(QualityFlag("imu_error", "high", f"IMU extraction failed: {exc}"))

        # EMG
        if emg_path:
            try:
                emg_features, emg_flags = EMGFeatureExtractor.extract(emg_path)
                features.emg_features = emg_features
                all_flags.extend(emg_flags)
            except Exception as exc:
                all_flags.append(QualityFlag("emg_error", "high", f"EMG extraction failed: {exc}"))

        features.quality_flags = all_flags

        return features, []

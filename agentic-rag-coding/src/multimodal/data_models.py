"""Data models for multimodal rehabilitation case and analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ConditionType(str, Enum):
    """Patient condition type."""
    POST_STROKE = "post_stroke"
    PARKINSON = "parkinson"
    CEREBRAL_PALSY = "cerebral_palsy"
    OTHER = "other"


class AffectedSide(str, Enum):
    """Affected body side."""
    LEFT = "left"
    RIGHT = "right"
    BILATERAL = "bilateral"
    UNKNOWN = "unknown"


class DataType(str, Enum):
    """Data modality type."""
    SKELETON = "skeleton"
    IMU = "imu"
    EMG = "emg"
    METADATA = "metadata"


@dataclass
class PatientCase:
    """Patient/subject case information."""
    case_id: str
    subject_code: str
    age: int
    sex: str  # male, female, other
    condition: ConditionType = ConditionType.POST_STROKE
    affected_side: AffectedSide = AffectedSide.UNKNOWN
    time_since_onset_months: Optional[int] = None
    assessment_date: str = field(default_factory=lambda: datetime.now().isoformat()[:10])
    notes: str = ""


@dataclass
class UploadedDataFile:
    """Uploaded data file metadata."""
    file_id: str
    case_id: str
    data_type: DataType
    filename: str
    storage_path: str
    schema_status: str = "unvalidated"  # unvalidated, passed, passed_with_warning, failed
    sampling_rate_hz: Optional[float] = None
    duration_sec: Optional[float] = None
    row_count: Optional[int] = None


@dataclass
class DataEvidence:
    """Evidence from patient/subject data."""
    data_evidence_id: str
    case_id: str
    source_file_id: str
    modality: str  # skeleton, imu, emg
    feature_name: str
    value: float
    unit: str
    time_range: Optional[tuple[float, float]] = None
    interpretation: str = ""


@dataclass
class LiteratureEvidence:
    """Evidence from literature."""
    evidence_id: str
    paper_title: str
    authors: Optional[list[str]] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section: str = ""
    text: str = ""
    score_final: float = 0.0


@dataclass
class ReportClaim:
    """Professional claim in the report."""
    claim_id: str
    claim_text: str
    claim_type: str  # gait_asymmetry, muscle_activation, etc.
    data_evidence_ids: list[str] = field(default_factory=list)
    literature_evidence_ids: list[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high
    confidence: float = 0.7


@dataclass
class SkeletonFeatures:
    """Extracted skeleton features."""
    walking_duration_sec: Optional[float] = None
    estimated_step_count: Optional[int] = None
    cadence_steps_per_min: Optional[float] = None
    left_right_step_symmetry: Optional[float] = None
    hip_range_of_motion: Optional[float] = None
    knee_range_of_motion: Optional[float] = None
    ankle_range_of_motion: Optional[float] = None
    trunk_sway_proxy: Optional[float] = None
    joint_confidence_mean: Optional[float] = None
    missing_joint_ratio: Optional[float] = None


@dataclass
class IMUFeatures:
    """Extracted IMU features."""
    acceleration_magnitude_mean: Optional[float] = None
    acceleration_magnitude_peak: Optional[float] = None
    angular_velocity_peak: Optional[float] = None
    gait_event_candidate_count: Optional[int] = None
    dominant_frequency: Optional[float] = None
    left_right_peak_asymmetry: Optional[float] = None
    signal_quality_score: Optional[float] = None


@dataclass
class EMGFeatures:
    """Extracted EMG features."""
    rms: Optional[dict[str, float]] = None  # muscle -> RMS value
    mav: Optional[dict[str, float]] = None  # muscle -> MAV
    iemg: Optional[dict[str, float]] = None  # muscle -> IEMG
    peak_activation: Optional[dict[str, float]] = None
    activation_timing_proxy: Optional[float] = None
    co_activation_proxy: Optional[float] = None
    fatigue_proxy: Optional[float] = None
    signal_quality_score: Optional[float] = None


@dataclass
class QualityFlag:
    """Data quality issue or warning."""
    flag_type: str
    severity: str  # low, medium, high
    message: str


@dataclass
class FeatureSet:
    """Complete feature set for a case."""
    feature_set_id: str
    case_id: str
    skeleton_features: Optional[SkeletonFeatures] = None
    imu_features: Optional[IMUFeatures] = None
    emg_features: Optional[EMGFeatures] = None
    quality_flags: list[QualityFlag] = field(default_factory=list)
    extracted_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RehabilitationReport:
    """Generated professional rehabilitation analysis report."""
    report_id: str
    case_id: str
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Report sections
    basic_info: dict[str, Any] = field(default_factory=dict)
    data_quality_summary: str = ""
    gait_spatiotemporal_analysis: str = ""
    skeleton_joint_analysis: str = ""
    imu_signal_analysis: str = ""
    emg_muscle_analysis: str = ""
    literature_evidence_mapping: str = ""
    preliminary_rehabilitation_significance: str = ""
    risk_and_limitation: str = ""
    follow_up_recommendations: str = ""
    
    # Evidence collections
    data_evidence_list: list[DataEvidence] = field(default_factory=list)
    literature_evidence_list: list[LiteratureEvidence] = field(default_factory=list)
    claims: list[ReportClaim] = field(default_factory=list)
    
    # Metadata
    confidence_level: float = 0.7
    overall_quality_score: float = 0.7
    
    @property
    def disclaimer(self) -> str:
        """Standard disclaimer for the report."""
        return (
            "本报告由 Agentic RAG 系统基于上传数据与本地文献证据自动生成，"
            "仅用于科研、教学或康复评估辅助，不构成医学诊断或治疗建议。"
            "请由具备资质的临床专业人员结合完整病史、体格检查和标准量表进行最终判断。"
        )

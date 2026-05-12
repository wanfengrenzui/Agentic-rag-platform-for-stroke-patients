"""Professional rehabilitation report generation from multimodal data."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from src.contracts.rag_contract_models import RetrieverFilters, RetrieverInputContract
from src.multimodal.data_models import (
    DataEvidence,
    FeatureSet,
    LiteratureEvidence,
    PatientCase,
    RehabilitationReport,
    ReportClaim,
)


class RehabReportGenerator:
    """Generate professional rehabilitation analysis reports."""

    def __init__(self, deepseek_client=None, rag_store=None):
        """Initialize report generator with optional LLM and RAG backends."""
        self.deepseek_client = deepseek_client
        self.rag_store = rag_store

    def generate_report(
        self,
        case: PatientCase,
        features: FeatureSet,
    ) -> RehabilitationReport:
        """Generate complete rehabilitation report from case and features."""

        report = RehabilitationReport(
            report_id=f"report_{case.case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            case_id=case.case_id,
        )

        # 1. Basic info
        report.basic_info = {
            "subject_code": case.subject_code,
            "age": case.age or "未知",
            "sex": case.sex or "未知",
            "condition": case.condition.value if case.condition else "未知",
            "affected_side": case.affected_side.value if case.affected_side else "未知",
            "time_since_onset_months": case.time_since_onset_months or "未知",
            "assessment_date": case.assessment_date or "未知",
            "notes": case.notes or "无",
        }

        # 2. Data quality summary
        report.data_quality_summary = self._gen_data_quality_summary(features)

        # 3. Skeleton analysis
        if features.skeleton_features:
            report.skeleton_joint_analysis = self._gen_skeleton_analysis(case, features)
            data_evs = self._extract_skeleton_evidence(case, features)
            report.data_evidence_list.extend(data_evs)

        # 4. IMU analysis
        if features.imu_features:
            report.imu_signal_analysis = self._gen_imu_analysis(case, features)
            data_evs = self._extract_imu_evidence(case, features)
            report.data_evidence_list.extend(data_evs)

        # 5. EMG analysis
        if features.emg_features and features.emg_features.rms:
            report.emg_muscle_analysis = self._gen_emg_analysis(case, features)
            data_evs = self._extract_emg_evidence(case, features)
            report.data_evidence_list.extend(data_evs)

        # 6. Retrieve literature evidence
        report.literature_evidence_list = self._retrieve_literature_evidence(case, features)

        # 7. Map evidence and generate claims
        report.claims = self._generate_claims(report.data_evidence_list, report.literature_evidence_list)

        # 8. Gait spatiotemporal
        if features.skeleton_features:
            report.gait_spatiotemporal_analysis = self._gen_gait_spatiotemporal(case, features)

        # 9. Overall significance
        report.preliminary_rehabilitation_significance = self._gen_rehab_significance(case, features)

        # 10. Risk and limitation
        report.risk_and_limitation = self._gen_risk_limitation(features)

        # 11. Follow-up recommendations
        report.follow_up_recommendations = self._gen_recommendations(case, features)

        # Set confidence and quality
        report.confidence_level = self._calc_confidence(features) or 0.0
        report.overall_quality_score = self._calc_quality_score(features) or 0.0

        self._enhance_report_with_llm(report, features)

        return report

    def _gen_data_quality_summary(self, features: FeatureSet) -> str:
        """Generate data quality summary section."""
        summary_parts = ["### 数据质量说明\n"]
        
        if features.quality_flags:
            summary_parts.append("**数据质量发现：**\n")
            for flag in features.quality_flags:
                summary_parts.append(f"- [{flag.severity.upper()}] {flag.message}\n")
        else:
            summary_parts.append("所有数据模态通过基础格式校验。\n")
        
        quality_score = 0.85
        if features.skeleton_features and features.skeleton_features.joint_confidence_mean:
            quality_score = features.skeleton_features.joint_confidence_mean
        elif features.imu_features and features.imu_features.signal_quality_score:
            quality_score = features.imu_features.signal_quality_score
        
        summary_parts.append(f"\n整体数据质量评分：**{quality_score * 100:.1f}%** (含置信度)\n")
        
        return "".join(summary_parts)

    def _gen_skeleton_analysis(self, case: PatientCase, features: FeatureSet) -> str:
        """Generate skeleton/joint analysis section."""
        sf = features.skeleton_features
        if not sf:
            return ""
        
        parts = ["### 骨骼关键点与关节活动度分析\n\n"]
        
        if sf.walking_duration_sec is not None and sf.cadence_steps_per_min is not None:
            parts.append(f"**步态时间参数：** 步行持续时间 {sf.walking_duration_sec:.1f} 秒，"
                        f"估计步数 {sf.estimated_step_count or '未知'} 步，步频 {sf.cadence_steps_per_min:.1f} 步/分钟。\n\n")
        else:
            parts.append("**步态时间参数：** 数据不足，无法计算步态时间参数。\n\n")

        if sf.left_right_step_symmetry is not None:
            parts.append(f"**左右对称性：** 左右步态对称指数为 {sf.left_right_step_symmetry:.2f}，")
            if sf.left_right_step_symmetry < 0.85:
                parts.append("提示存在明显的左右步态不对称，这与中风后常见的步态模式改变相符。")
            else:
                parts.append("对称性相对良好。")
        else:
            parts.append("**左右对称性：** 数据不足，无法计算对称性。")
        parts.append("\n\n")

        parts.append(f"**关节活动度(ROM)：**\n")
        parts.append(f"- 髋关节: {sf.hip_range_of_motion or '未知'} (相对单位)\n")
        parts.append(f"- 膝关节: {sf.knee_range_of_motion or '未知'} (相对单位)\n")
        parts.append(f"- 踝关节: {sf.ankle_range_of_motion or '未知'} (相对单位)\n\n")

        if sf.trunk_sway_proxy is not None:
            parts.append(f"**躯干晃动代理指标：** {sf.trunk_sway_proxy:.3f}\n\n")
        else:
            parts.append("**躯干晃动代理指标：** 数据不足，无法计算。\n\n")

        if sf.missing_joint_ratio is not None and sf.missing_joint_ratio > 0.1:
            parts.append(f"⚠️ **缺失数据警告：** {sf.missing_joint_ratio*100:.1f}% 的关键点置信度较低，可能影响分析准确性。\n")

        return "".join(parts)

    def _gen_imu_analysis(self, case: PatientCase, features: FeatureSet) -> str:
        """Generate IMU signal analysis section."""
        imuf = features.imu_features
        if not imuf:
            return ""
        
        parts = ["### IMU 传感器信号分析\n\n"]
        
        parts.append(f"**加速度特征：**\n")
        if imuf.acceleration_magnitude_mean is not None:
            parts.append(f"- 平均加速度幅值: {imuf.acceleration_magnitude_mean:.2f} m/s²\n")
        else:
            parts.append("- 平均加速度幅值: 数据不足\n")

        if imuf.acceleration_magnitude_peak is not None:
            parts.append(f"- 峰值加速度: {imuf.acceleration_magnitude_peak:.2f} m/s²\n\n")
        else:
            parts.append("- 峰值加速度: 数据不足\n\n")

        parts.append(f"**角速度特征：**\n")
        if imuf.angular_velocity_peak is not None:
            parts.append(f"- 峰值角速度: {imuf.angular_velocity_peak:.2f} °/s\n\n")
        else:
            parts.append("- 峰值角速度: 数据不足\n\n")

        if imuf.gait_event_candidate_count is not None:
            parts.append(f"**步态事件检测：** 识别约 {imuf.gait_event_candidate_count} 个潜在步态事件\n\n")
        else:
            parts.append("**步态事件检测：** 数据不足\n\n")

        if imuf.left_right_peak_asymmetry is not None:
            parts.append(f"**左右不对称指数：** {imuf.left_right_peak_asymmetry:.2f}\n")
            if imuf.left_right_peak_asymmetry > 0.2:
                parts.append("提示下肢运动学存在左右不对称，这可能反映中风后患侧运动能力的限制。\n")
        else:
            parts.append("**左右不对称指数：** 数据不足\n")
        parts.append("\n")

        if imuf.dominant_frequency is not None:
            parts.append(f"**主导频率：** {imuf.dominant_frequency:.2f} Hz (归一化)\n")
        else:
            parts.append("**主导频率：** 数据不足\n")

        if imuf.signal_quality_score is not None:
            parts.append(f"**信号质量评分：** {imuf.signal_quality_score:.2f}/1.0\n")
        else:
            parts.append("**信号质量评分：** 数据不足\n")

        return "".join(parts)

    def _gen_emg_analysis(self, case: PatientCase, features: FeatureSet) -> str:
        """Generate EMG muscle activation analysis section."""
        emgf = features.emg_features
        if not emgf or not emgf.rms:
            return ""
        
        parts = ["### 肌电图(EMG)信号分析\n\n"]

        parts.append("**肌肉激活程度 (RMS)：**\n")
        if emgf.rms:
            for muscle, value in emgf.rms.items():
                if value is not None:
                    parts.append(f"- {muscle}: {value:.4f} V\n")
                else:
                    parts.append(f"- {muscle}: 数据不足\n")
        else:
            parts.append("- 数据不足\n")
        parts.append("\n")

        if emgf.co_activation_proxy is not None:
            parts.append(f"**协同激活指标：** {emgf.co_activation_proxy:.2f}\n")
            if emgf.co_activation_proxy > 0.3:
                parts.append("提示存在显著的肌肉协同激活，这在中风后运动恢复早期较为常见。\n")
        else:
            parts.append("**协同激活指标：** 数据不足\n")

        return "".join(parts)

    def _gen_gait_spatiotemporal(self, case: PatientCase, features: FeatureSet) -> str:
        """Generate spatial-temporal gait parameters section."""
        sf = features.skeleton_features
        imuf = features.imu_features
        
        parts = ["### 步态时空参数分析\n\n"]
        
        parts.append("**时间参数：**\n")
        if sf:
            if sf.cadence_steps_per_min is not None:
                parts.append(f"- 步频: {sf.cadence_steps_per_min:.1f} 步/分钟\n")
            else:
                parts.append("- 步频: 数据不足\n")
            if sf.estimated_step_count is not None:
                parts.append(f"- 总步数: {sf.estimated_step_count} 步\n")
            else:
                parts.append("- 总步数: 数据不足\n")
        parts.append("\n")
        
        parts.append("**空间参数：**\n")
        if sf:
            if sf.hip_range_of_motion is not None:
                parts.append(f"- 髋关节活动度: {sf.hip_range_of_motion:.3f}\n")
            else:
                parts.append("- 髋关节活动度: 数据不足\n")
            if sf.knee_range_of_motion is not None:
                parts.append(f"- 膝关节活动度: {sf.knee_range_of_motion:.3f}\n")
            else:
                parts.append("- 膝关节活动度: 数据不足\n")
        if imuf:
            if imuf.left_right_peak_asymmetry is not None:
                parts.append(f"- 加速度不对称: {imuf.left_right_peak_asymmetry:.2f}\n")
            else:
                parts.append("- 加速度不对称: 数据不足\n")
        parts.append("\n")
        
        parts.append("**步态对称性评估：**\n")
        if sf and sf.left_right_step_symmetry is not None and sf.left_right_step_symmetry < 0.9:
            parts.append(f"患者表现出 {(1-sf.left_right_step_symmetry)*100:.0f}% 的左右步态不对称，")
            parts.append("这与中风后常见的代偿性步态改变一致。建议进一步评估患侧下肢运动控制能力。\n")
        elif sf and sf.left_right_step_symmetry is not None:
            parts.append("步态对称性相对良好。\n")
        else:
            parts.append("步态对称性数据不足，暂无足够信息评估。\n")
        
        return "".join(parts)

    def _gen_rehab_significance(self, case: PatientCase, features: FeatureSet) -> str:
        """Generate preliminary rehabilitation significance section."""
        parts = ["### 初步康复意义\n\n"]
        
        parts.append(f"该受试者患病时间 {case.time_since_onset_months} 个月，")
        
        sf = features.skeleton_features
        if sf and sf.cadence_steps_per_min is not None and sf.cadence_steps_per_min > 80:
            parts.append("步频相对保持，步态稳定性较好。\n\n")
            parts.append("**初步评估：** 该患者步行能力保持相对完整，可能处于慢性恢复阶段或稳定期。\n")
        else:
            parts.append("步频偏低，步态可能存在能量消耗增加。\n\n")
            parts.append("**初步评估：** 患者步行可能存在代偿策略，建议重点关注患侧下肢的运动控制与肌力恢复。\n")
        
        parts.append("\n建议由康复医学专业人员结合临床检查、肌力测试和功能量表进行综合评估。\n")
        
        return "".join(parts)

    def _gen_risk_limitation(self, features: FeatureSet) -> str:
        """Generate risk and limitation section."""
        parts = ["### 风险与局限\n\n"]
        
        parts.append("**本分析的局限：**\n")
        parts.append("1. 本报告基于离线数据自动生成，仅用于辅助分析，不构成医学诊断。\n")
        parts.append("2. 特征提取采用简化算法，可能不适用于所有临床场景。\n")
        parts.append("3. 缺乏临床体格检查、肌力测试和标准量表评分的支持。\n")
        parts.append("4. 单次评估无法反映长期康复趋势，建议定期随访。\n\n")
        
        if features.quality_flags:
            parts.append("**数据质量风险：**\n")
            for flag in features.quality_flags:
                if flag.severity in ["medium", "high"]:
                    parts.append(f"- {flag.message}\n")
        
        return "".join(parts)

    def _gen_recommendations(self, case: PatientCase, features: FeatureSet) -> str:
        """Generate follow-up recommendations section."""
        parts = ["### 后续建议\n\n"]
        
        parts.append("**建议的后续步骤：**\n")
        parts.append("1. 由康复医学或神经科医生进行全面临床评估。\n")
        parts.append("2. 使用标准功能量表（如 Fugl-Meyer Assessment、NIHSS 等）量化步态和运动功能。\n")
        parts.append("3. 根据临床需要补充其他评估（如虚拟现实任务、力板平衡测试等）。\n")
        parts.append("4. 制定个体化康复训练计划，关注患侧下肢的力量和控制训练。\n")
        parts.append("5. 定期复评（建议每 4-8 周一次），追踪功能恢复趋势。\n\n")
        
        parts.append("**数据采集优化建议：**\n")
        if features.quality_flags:
            parts.append("- 改进传感器放置和校准，确保数据采样率稳定。\n")
        parts.append("- 在标准化步行条件下重复采集，以提高重测信度。\n")
        
        return "".join(parts)

    def _extract_skeleton_evidence(self, case: PatientCase, features: FeatureSet) -> list[DataEvidence]:
        """Extract data evidence from skeleton features."""
        evidence = []
        sf = features.skeleton_features
        
        if sf and sf.left_right_step_symmetry:
            evidence.append(DataEvidence(
                data_evidence_id=f"data_{case.case_id}_skeleton_symmetry_001",
                case_id=case.case_id,
                source_file_id="skeleton_001",
                modality="skeleton",
                feature_name="left_right_step_symmetry",
                value=sf.left_right_step_symmetry,
                unit="ratio",
                interpretation=f"左右步态对称指数为 {sf.left_right_step_symmetry:.2f}，" +
                               ("存在明显不对称。" if sf.left_right_step_symmetry < 0.85 else "对称性相对良好。")
            ))
        
        if sf and sf.cadence_steps_per_min:
            evidence.append(DataEvidence(
                data_evidence_id=f"data_{case.case_id}_skeleton_cadence_001",
                case_id=case.case_id,
                source_file_id="skeleton_001",
                modality="skeleton",
                feature_name="cadence_steps_per_min",
                value=sf.cadence_steps_per_min,
                unit="步/分钟",
                interpretation=f"患者步频为 {sf.cadence_steps_per_min:.1f} 步/分钟。"
            ))
        
        return evidence

    def _extract_imu_evidence(self, case: PatientCase, features: FeatureSet) -> list[DataEvidence]:
        """Extract data evidence from IMU features."""
        evidence = []
        imuf = features.imu_features
        
        if imuf and imuf.left_right_peak_asymmetry:
            evidence.append(DataEvidence(
                data_evidence_id=f"data_{case.case_id}_imu_asymmetry_001",
                case_id=case.case_id,
                source_file_id="imu_001",
                modality="imu",
                feature_name="left_right_peak_asymmetry",
                value=imuf.left_right_peak_asymmetry,
                unit="ratio",
                interpretation=f"左右 IMU 峰值不对称指数为 {imuf.left_right_peak_asymmetry:.2f}，" +
                               ("提示下肢动力学存在明显不对称。" if imuf.left_right_peak_asymmetry > 0.2 else "相对均衡。")
            ))
        
        return evidence

    def _extract_emg_evidence(self, case: PatientCase, features: FeatureSet) -> list[DataEvidence]:
        """Extract data evidence from EMG features."""
        evidence = []
        emgf = features.emg_features
        
        if emgf and emgf.co_activation_proxy:
            evidence.append(DataEvidence(
                data_evidence_id=f"data_{case.case_id}_emg_coactivation_001",
                case_id=case.case_id,
                source_file_id="emg_001",
                modality="emg",
                feature_name="co_activation_proxy",
                value=emgf.co_activation_proxy,
                unit="ratio",
                interpretation=f"肌肉协同激活指标为 {emgf.co_activation_proxy:.2f}。"
            ))
        
        return evidence

    def _retrieve_literature_evidence(self, case: PatientCase, features: FeatureSet) -> list[LiteratureEvidence]:
        """Retrieve relevant literature evidence from RAG store."""
        if not self.rag_store:
            return []
        
        # Generate retrieval queries based on case and features
        queries = []
        if case.condition.value == "post_stroke":
            queries.extend([
                "中风步态分析 IMU 传感器",
                "中风患者康复 步态对称性",
                "IMU 加速度计 步态事件检测",
                "中风下肢运动控制 EMG",
            ])
        
        payload = RetrieverInputContract(
            request_id=f"report_lit_{case.case_id}",
            queries=queries or ["rehabilitation gait analysis IMU EMG stroke"],
            filters=RetrieverFilters(),
            top_k=6,
        )
        try:
            retrieval = self.rag_store.run(payload)
        except Exception:
            return []

        evidence = []
        for item in retrieval.evidence_list:
            evidence.append(
                LiteratureEvidence(
                    evidence_id=item.evidence_id,
                    paper_title=item.title,
                    authors=item.authors,
                    page_start=item.page_start,
                    page_end=item.page_end,
                    section=item.section.value if hasattr(item.section, "value") else str(item.section),
                    text=item.text[:700],
                    score_final=item.score_final,
                )
            )
        return evidence

    def _generate_claims(self, data_evs: list[DataEvidence], lit_evs: list[LiteratureEvidence]) -> list[ReportClaim]:
        """Generate professional claims linking data and literature evidence."""
        claims = []
        
        for de in data_evs:
            # Find relevant literature evidence
            lit_ids = [le.evidence_id for le in lit_evs[:2]]  # Link first 2 papers
            
            claim = ReportClaim(
                claim_id=f"claim_{de.data_evidence_id}",
                claim_text=de.interpretation,
                claim_type="gait_observation" if "symmetry" in de.feature_name else "measurement",
                data_evidence_ids=[de.data_evidence_id],
                literature_evidence_ids=lit_ids,
                risk_level="medium",
                confidence=0.75,
            )
            claims.append(claim)
        
        return claims

    def _enhance_report_with_llm(self, report: RehabilitationReport, features: FeatureSet) -> None:
        """Use LLM as an interpretation layer while preserving computed evidence."""
        if not self.deepseek_client or not getattr(self.deepseek_client, "configured", False):
            return

        payload = {
            "basic_info": report.basic_info,
            "computed_features": _json_safe(
                {
                    "skeleton": features.skeleton_features.__dict__ if features.skeleton_features else None,
                    "imu": features.imu_features.__dict__ if features.imu_features else None,
                    "emg": features.emg_features.__dict__ if features.emg_features else None,
                    "quality_flags": [flag.__dict__ for flag in features.quality_flags],
                }
            ),
            "data_evidence": _json_safe([item.__dict__ for item in report.data_evidence_list]),
            "literature_evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "paper_title": item.paper_title,
                    "section": item.section,
                    "page_start": item.page_start,
                    "text": item.text,
                    "score_final": item.score_final,
                }
                for item in report.literature_evidence_list
            ],
        }
        system = (
            "你是康复医学与运动数据分析报告解释层。只输出 JSON，不要 Markdown 代码块。"
            "你必须基于给定 computed_features、data_evidence 和 literature_evidence 写作，不能编造诊断。"
            "语气应专业、审慎、可读，结论必须体现“辅助分析，不替代医生诊断”。"
        )
        user = {
            "task": "rewrite_multimodal_rehab_report_sections",
            "input": payload,
            "schema": {
                "gait_spatiotemporal_analysis": "markdown string",
                "skeleton_joint_analysis": "markdown string",
                "imu_signal_analysis": "markdown string",
                "emg_muscle_analysis": "markdown string",
                "preliminary_rehabilitation_significance": "markdown string",
                "risk_and_limitation": "markdown string",
                "follow_up_recommendations": "markdown string",
            },
        }
        try:
            data = self.deepseek_client.chat_json(system, json.dumps(user, ensure_ascii=False), temperature=0.2)
        except Exception:
            return

        for key in [
            "gait_spatiotemporal_analysis",
            "skeleton_joint_analysis",
            "imu_signal_analysis",
            "emg_muscle_analysis",
            "preliminary_rehabilitation_significance",
            "risk_and_limitation",
            "follow_up_recommendations",
        ]:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                setattr(report, key, value.strip() + "\n")

    def _calc_confidence(self, features: FeatureSet) -> float:
        """Calculate overall confidence level."""
        conf = 0.8
        
        if features.quality_flags:
            conf -= len(features.quality_flags) * 0.05
        
        if features.skeleton_features and hasattr(features.skeleton_features, 'joint_confidence_mean') and features.skeleton_features.joint_confidence_mean:
            conf *= features.skeleton_features.joint_confidence_mean
        elif features.imu_features and hasattr(features.imu_features, 'signal_quality_score') and features.imu_features.signal_quality_score:
            conf *= features.imu_features.signal_quality_score
        
        return max(0.4, min(1.0, conf))

    def _calc_quality_score(self, features: FeatureSet) -> float:
        """Calculate overall quality score."""
        scores = []
        
        if features.skeleton_features:
            scores.append(features.skeleton_features.joint_confidence_mean or 0.7)
        
        if features.imu_features:
            scores.append(features.imu_features.signal_quality_score or 0.7)
        
        if features.emg_features:
            scores.append(features.emg_features.signal_quality_score or 0.7)
        
        return sum(scores) / len(scores) if scores else 0.7


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value

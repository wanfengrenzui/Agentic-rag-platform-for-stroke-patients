"""Export rehabilitation report to various formats."""

from __future__ import annotations

import json
from datetime import datetime

from src.multimodal.data_models import RehabilitationReport


class ReportExporter:
    """Export rehabilitation reports to different formats."""

    @staticmethod
    def to_markdown(report: RehabilitationReport) -> str:
        """Export report to Markdown format."""
        md_parts = []
        
        # Title and metadata
        md_parts.append("# 多模态康复运动数据分析报告\n\n")
        md_parts.append(f"**报告编号：** {report.report_id}\n")
        md_parts.append(f"**生成时间：** {report.generated_at}\n")
        md_parts.append(f"**分析对象：** {report.basic_info.get('subject_code', 'N/A')}\n")
        md_parts.append(f"**年龄/性别：** {report.basic_info.get('age', 'N/A')} 岁 / {report.basic_info.get('sex', 'N/A')}\n")
        md_parts.append(f"**诊断：** {report.basic_info.get('condition', 'N/A')}\n")
        md_parts.append(f"**患侧：** {report.basic_info.get('affected_side', 'N/A')}\n")
        md_parts.append(f"**病程：** {report.basic_info.get('time_since_onset_months', 'N/A')} 个月\n\n")
        
        md_parts.append("---\n\n")
        
        # Disclaimer
        md_parts.append("## ⚠️ 免责声明\n\n")
        md_parts.append(f"{report.disclaimer}\n\n")
        
        md_parts.append("---\n\n")
        
        # Data quality
        if report.data_quality_summary:
            md_parts.append(report.data_quality_summary)
            md_parts.append("\n")
        
        # Gait spatiotemporal
        if report.gait_spatiotemporal_analysis:
            md_parts.append(report.gait_spatiotemporal_analysis)
            md_parts.append("\n")
        
        # Skeleton analysis
        if report.skeleton_joint_analysis:
            md_parts.append(report.skeleton_joint_analysis)
            md_parts.append("\n")
        
        # IMU analysis
        if report.imu_signal_analysis:
            md_parts.append(report.imu_signal_analysis)
            md_parts.append("\n")
        
        # EMG analysis
        if report.emg_muscle_analysis:
            md_parts.append(report.emg_muscle_analysis)
            md_parts.append("\n")
        
        # Evidence section
        if report.data_evidence_list or report.literature_evidence_list:
            md_parts.append("## 证据卡片\n\n")
            
            if report.data_evidence_list:
                md_parts.append("### 数据证据\n\n")
                for ev in report.data_evidence_list:
                    md_parts.append(f"**{ev.feature_name}**\n\n")
                    md_parts.append(f"- **值：** {ev.value} {ev.unit}\n")
                    md_parts.append(f"- **模态：** {ev.modality}\n")
                    md_parts.append(f"- **解释：** {ev.interpretation}\n\n")
            
            if report.literature_evidence_list:
                md_parts.append("### 文献证据\n\n")
                for ev in report.literature_evidence_list:
                    md_parts.append(f"**{ev.paper_title}**\n\n")
                    if ev.authors:
                        md_parts.append(f"- **作者：** {', '.join(ev.authors)}\n")
                    md_parts.append(f"- **页码：** {ev.page_start}\n")
                    md_parts.append(f"- **章节：** {ev.section}\n")
                    md_parts.append(f"- **内容摘录：** {ev.text}\n")
                    md_parts.append(f"- **相关性评分：** {ev.score_final:.2f}\n\n")
        
        # Claims section
        if report.claims:
            md_parts.append("## 专业分析与结论\n\n")
            for i, claim in enumerate(report.claims, 1):
                md_parts.append(f"### 发现 {i}\n\n")
                md_parts.append(f"**结论：** {claim.claim_text}\n\n")
                md_parts.append(f"- **分类：** {claim.claim_type}\n")
                md_parts.append(f"- **风险水平：** {claim.risk_level}\n")
                md_parts.append(f"- **置信度：** {claim.confidence:.2f}\n")
                if claim.data_evidence_ids:
                    md_parts.append(f"- **数据证据：** {', '.join(claim.data_evidence_ids)}\n")
                if claim.literature_evidence_ids:
                    md_parts.append(f"- **文献支持：** {', '.join(claim.literature_evidence_ids)}\n")
                md_parts.append("\n")
        
        # Rehabilitation significance
        if report.preliminary_rehabilitation_significance:
            md_parts.append("## 初步康复意义\n\n")
            md_parts.append(report.preliminary_rehabilitation_significance)
            md_parts.append("\n")
        
        # Risk and limitation
        if report.risk_and_limitation:
            md_parts.append("## 风险与局限\n\n")
            md_parts.append(report.risk_and_limitation)
            md_parts.append("\n")
        
        # Recommendations
        if report.follow_up_recommendations:
            md_parts.append("## 后续建议\n\n")
            md_parts.append(report.follow_up_recommendations)
            md_parts.append("\n")
        
        # Quality metrics
        md_parts.append("---\n\n")
        md_parts.append("## 报告质量信息\n\n")
        md_parts.append(f"- **置信度：** {report.confidence_level:.2%}\n")
        md_parts.append(f"- **整体质量评分：** {report.overall_quality_score:.2f}/1.0\n")
        md_parts.append(f"- **数据证据数量：** {len(report.data_evidence_list)}\n")
        md_parts.append(f"- **文献证据数量：** {len(report.literature_evidence_list)}\n")
        md_parts.append(f"- **专业分析数量：** {len(report.claims)}\n")
        
        return "".join(md_parts)

    @staticmethod
    def to_json(report: RehabilitationReport) -> str:
        """Export report to JSON format."""
        report_dict = {
            "report_id": report.report_id,
            "case_id": report.case_id,
            "generated_at": report.generated_at,
            "basic_info": report.basic_info,
            "data_quality_summary": report.data_quality_summary,
            "gait_spatiotemporal_analysis": report.gait_spatiotemporal_analysis,
            "skeleton_joint_analysis": report.skeleton_joint_analysis,
            "imu_signal_analysis": report.imu_signal_analysis,
            "emg_muscle_analysis": report.emg_muscle_analysis,
            "preliminary_rehabilitation_significance": report.preliminary_rehabilitation_significance,
            "risk_and_limitation": report.risk_and_limitation,
            "follow_up_recommendations": report.follow_up_recommendations,
            "data_evidence_list": [
                {
                    "data_evidence_id": e.data_evidence_id,
                    "feature_name": e.feature_name,
                    "value": e.value,
                    "unit": e.unit,
                    "interpretation": e.interpretation,
                }
                for e in report.data_evidence_list
            ],
            "literature_evidence_list": [
                {
                    "evidence_id": e.evidence_id,
                    "paper_title": e.paper_title,
                    "page_start": e.page_start,
                    "section": e.section,
                    "score_final": e.score_final,
                }
                for e in report.literature_evidence_list
            ],
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "claim_text": c.claim_text,
                    "claim_type": c.claim_type,
                    "data_evidence_ids": c.data_evidence_ids,
                    "literature_evidence_ids": c.literature_evidence_ids,
                    "risk_level": c.risk_level,
                    "confidence": c.confidence,
                }
                for c in report.claims
            ],
            "confidence_level": report.confidence_level,
            "overall_quality_score": report.overall_quality_score,
            "disclaimer": report.disclaimer,
        }
        return json.dumps(report_dict, ensure_ascii=False, indent=2)

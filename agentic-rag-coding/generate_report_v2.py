#!/usr/bin/env python3
"""Generate sample rehabilitation report demonstrating V2 functionality."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.multimodal.data_models import AffectedSide, ConditionType, PatientCase
from src.multimodal.feature_extractor import FeatureExtractorPipeline
from src.multimodal.report_generator import RehabReportGenerator
from src.multimodal.report_exporter import ReportExporter


def main():
    """Main function to generate report."""
    print("=" * 70)
    print("多模态康复运动数据分析报告生成系统 V2")
    print("=" * 70)
    print()
    
    # Create patient case
    print("[1/4] 创建患者案例...")
    case = PatientCase(
        case_id="case_20260511_001",
        subject_code="S001",
        age=57,
        sex="male",
        condition=ConditionType.POST_STROKE,
        affected_side=AffectedSide.RIGHT,
        time_since_onset_months=96,
        assessment_date="2026-05-11",
        notes="慢性右偏瘫，独立步行但步态不对称。",
    )
    print(f"  ✓ 患者编号: {case.subject_code}")
    print(f"  ✓ 年龄/性别: {case.age}岁/{case.sex}")
    print(f"  ✓ 诊断: {case.condition.value} (患侧:{case.affected_side.value})")
    print()
    
    # Extract features
    print("[2/4] 提取多模态特征...")
    sample_dir = Path(__file__).parent / "sample_data"
    
    features, _ = FeatureExtractorPipeline.extract_all(
        skeleton_path=str(sample_dir / "skeleton_sample.csv") if (sample_dir / "skeleton_sample.csv").exists() else None,
        imu_path=str(sample_dir / "imu_sample.csv") if (sample_dir / "imu_sample.csv").exists() else None,
        emg_path=str(sample_dir / "emg_sample.csv") if (sample_dir / "emg_sample.csv").exists() else None,
    )
    features.case_id = case.case_id
    
    print(f"  ✓ 骨骼特征: {'已提取' if features.skeleton_features else '未提取'}")
    if features.skeleton_features:
        print(f"    - 步频: {features.skeleton_features.cadence_steps_per_min:.1f} 步/分钟")
        print(f"    - 步数: {features.skeleton_features.estimated_step_count}")
    
    print(f"  ✓ IMU特征: {'已提取' if features.imu_features else '未提取'}")
    if features.imu_features:
        print(f"    - 加速度峰值: {features.imu_features.acceleration_magnitude_peak:.2f} m/s²")
    
    print(f"  ✓ EMG特征: {'已提取' if features.emg_features else '未提取'}")
    print()
    
    # Generate report
    print("[3/4] 生成专业分析报告...")
    generator = RehabReportGenerator()
    report = generator.generate_report(case, features)
    print(f"  ✓ 报告ID: {report.report_id}")
    print(f"  ✓ 数据证据: {len(report.data_evidence_list)}")
    print(f"  ✓ 文献证据: {len(report.literature_evidence_list)}")
    print(f"  ✓ 分析结论: {len(report.claims)}")
    print()
    
    # Export report
    print("[4/4] 导出报告...")
    exporter = ReportExporter()
    md_content = exporter.to_markdown(report)
    json_content = exporter.to_json(report)
    
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    md_file = output_dir / f"{report.report_id}.md"
    json_file = output_dir / f"{report.report_id}.json"
    
    md_file.write_text(md_content, encoding="utf-8")
    json_file.write_text(json_content, encoding="utf-8")
    
    print(f"  ✓ Markdown: {md_file.name}")
    print(f"  ✓ JSON: {json_file.name}")
    print()
    
    # Print sample
    print("=" * 70)
    print("报告摘要（前1500字）:")
    print("=" * 70)
    print(md_content[:1500])
    print("\n...")
    print(f"\n[完整报告已保存到 {output_dir}]")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

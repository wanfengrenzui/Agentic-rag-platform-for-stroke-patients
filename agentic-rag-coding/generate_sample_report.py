"""Generate sample rehabilitation report demonstrating V2 functionality."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.multimodal.data_models import (
    AffectedSide,
    ConditionType,
    PatientCase,
)
from src.multimodal.feature_extractor import FeatureExtractorPipeline
from src.multimodal.report_generator import RehabReportGenerator
from src.multimodal.report_exporter import ReportExporter


def generate_sample_report():
    """Generate a sample rehabilitation report."""
    
    print("=" * 60)
    print("多模态康复运动数据分析报告生成系统 - 示例演示")
    print("=" * 60)
    print()
    
    # 1. Create patient case
    print("1️⃣  创建患者案例...")
    case = PatientCase(
        case_id="case_20260511_stroke_001",
        subject_code="S001",
        age=57,
        sex="male",
        condition=ConditionType.POST_STROKE,
        affected_side=AffectedSide.RIGHT,
        time_since_onset_months=96,
        assessment_date="2026-05-11",
        notes="慢性右偏瘫患者，独立步行但步态不对称。患者接受过6个月的系统康复训练。",
    )
    print(f"   ✓ 患者编号：{case.subject_code}")
    print(f"   ✓ 年龄：{case.age}岁，性别：{case.sex}")
    print(f"   ✓ 诊断：{case.condition.value}（患侧：{case.affected_side.value}）")
    print(f"   ✓ 病程：{case.time_since_onset_months}个月")
    print()
    
    # 2. Extract features from sample data
    print("2️⃣  提取多模态特征...")
    sample_data_dir = Path(__file__).parent.parent / "sample_data"
    
    features, _ = FeatureExtractorPipeline.extract_all(
        skeleton_path=str(sample_data_dir / "skeleton_sample.csv"),
        imu_path=str(sample_data_dir / "imu_sample.csv"),
        emg_path=str(sample_data_dir / "emg_sample.csv"),
    )
    
    print(f"   ✓ 骨骼关键点特征已提取")
    if features.skeleton_features:
        print(f"      - 步频：{features.skeleton_features.cadence_steps_per_min:.1f} 步/分钟")
        print(f"      - 左右对称性：{features.skeleton_features.left_right_step_symmetry:.2f}")
        print(f"      - 步行持续时间：{features.skeleton_features.walking_duration_sec:.1f} 秒")
    
    print(f"   ✓ IMU 传感器特征已提取")
    if features.imu_features:
        print(f"      - 加速度峰值：{features.imu_features.acceleration_magnitude_peak:.2f} m/s²")
        print(f"      - 左右不对称：{features.imu_features.left_right_peak_asymmetry:.2f}")
        print(f"      - 信号质量：{features.imu_features.signal_quality_score:.2f}/1.0")
    
    print(f"   ✓ EMG 肌电信号特征已提取")
    if features.emg_features:
        print(f"      - RMS 激活：{len(features.emg_features.rms)} 个肌肉")
        print(f"      - 协同激活指标：{features.emg_features.co_activation_proxy:.2f}")
    
    if features.quality_flags:
        print(f"   ⚠️  数据质量警告：{len(features.quality_flags)}个")
        for flag in features.quality_flags:
            print(f"      - [{flag.severity}] {flag.message}")
    
    features.case_id = case.case_id
    print()
    
    # 3. Generate report
    print("3️⃣  生成专业分析报告...")
    generator = RehabReportGenerator()
    report = generator.generate_report(case, features)
    print(f"   ✓ 报告编号：{report.report_id}")
    print(f"   ✓ 包含数据证据：{len(report.data_evidence_list)} 个")
    print(f"   ✓ 包含文献证据：{len(report.literature_evidence_list)} 个")
    print(f"   ✓ 专业分析结论：{len(report.claims)} 个")
    print(f"   ✓ 置信度：{report.confidence_level:.1%}")
    print()
    
    # 4. Export report
    print("4️⃣  导出报告...")
    exporter = ReportExporter()
    markdown_content = exporter.to_markdown(report)
    json_content = exporter.to_json(report)
    
    # Save to files
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    md_path = output_dir / f"{report.report_id}.md"
    json_path = output_dir / f"{report.report_id}.json"
    
    md_path.write_text(markdown_content, encoding="utf-8")
    json_path.write_text(json_content, encoding="utf-8")
    
    print(f"   ✓ Markdown 报告：{md_path.relative_to(Path.cwd())}")
    print(f"   ✓ JSON 数据报告：{json_path.relative_to(Path.cwd())}")
    print()
    
    # 5. Print summary
    print("=" * 60)
    print("报告生成完成！")
    print("=" * 60)
    print()
    print("📄 报告摘要：")
    print("-" * 60)
    print(markdown_content[:2000])  # Print first 2000 chars
    print("...")
    print("-" * 60)
    print()
    print(f"完整报告已保存到 {output_dir}")


if __name__ == "__main__":
    try:
        generate_sample_report()
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        import traceback
        traceback.print_exc()

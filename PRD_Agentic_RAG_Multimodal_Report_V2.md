# PRD: Agentic RAG Multimodal Rehabilitation Report V2

## 1. 文档信息

- 项目名称：Agentic RAG Platform for Stroke Patients
- 版本：V2.0 Draft
- 日期：2026-05-11
- V1 基线：Agentic RAG Web MVP 已完成
- V2 定位：离线多模态运动数据上传 + 特征分析 + 文献增强专业报告生成

## 2. V2 产品目标

V2 要把产品从“基于论文的 RAG 问答系统”升级为“基于用户运动数据与文献证据的专业分析报告平台”。

用户上传一个患者或实验对象的运动数据后，系统能够：

1. 读取骨骼节点、IMU、EMG 等离线数据文件。
2. 提取基础步态、姿态、惯性、肌电特征。
3. 检索本地论文库中的相关证据。
4. 生成结构化中文分析报告。
5. 将关键结论同时绑定用户数据证据与文献证据。
6. 展示图表、指标表、证据卡片，并支持报告导出。

V2 不做“医学诊断”，只做“数据驱动的康复分析辅助报告”。所有高风险表述必须使用审慎措辞，例如“提示”“可能”“建议由专业人员进一步评估”。

## 3. 目标用户与场景

### 3.1 目标用户

- 康复医学研究者
- HCI / 医工交叉研究者
- 步态分析方向学生
- 康复治疗师或科研助理
- 需要整理多模态运动数据报告的项目团队

### 3.2 核心场景

用户拥有一次离线采集数据：

- RGB 相机提取后的骨骼节点数据
- IMU 传感器数据
- EMG 肌电数据
- 基本患者信息或实验对象信息

用户希望系统生成一份专业报告，用于：

- 研究记录
- 康复评估辅助
- 论文方法对比
- 项目展示
- 医工/HCI 课程或面试作品集

## 4. V2 MVP 范围

### 4.1 输入

V2 先支持离线文件上传，不做实时摄像头采集。

支持数据类型：

| 数据类型 | V2 支持格式 | 是否必需 |
|---|---|---|
| 患者/对象基本信息 | 表单 / JSON | 必需 |
| 骨骼节点数据 | CSV / JSON | 必需 |
| IMU 数据 | CSV | 必需 |
| EMG 数据 | CSV | 可选 |
| 备注与分析目标 | 文本 | 可选 |

### 4.2 输出

V2 输出一份专业中文报告：

1. 基本信息
2. 数据质量说明
3. 步态时空参数分析
4. 骨骼节点/关节运动分析
5. IMU 信号分析
6. EMG 肌肉激活分析
7. 与文献证据的对照
8. 初步康复意义
9. 风险与限制
10. 后续建议

报告应同时提供：

- 指标表
- 可视化图表
- 数据证据卡片
- 文献证据卡片
- 置信度说明
- Markdown 导出

PDF / Word 导出可作为 V2.1。

## 5. V2 非目标

以下能力不进入 V2 MVP：

- 实时 RGB 摄像头采集
- 实时姿态估计
- 自动医学诊断
- 医生工作流审批
- 多患者长期随访数据库
- 深度学习疾病分类模型
- 医疗合规级审查系统
- HIS / EMR 医院系统集成

## 6. 核心用户流程

```text
Create Patient Case
-> Upload Skeleton / IMU / EMG Files
-> Validate Data
-> Extract Features
-> Retrieve Literature Evidence
-> Generate Report
-> Critic Review
-> Show Report + Charts + Evidence
-> Export Markdown
```

## 7. 数据模型

### 7.1 PatientCase

```json
{
  "case_id": "case_20260511_001",
  "subject_code": "S001",
  "age": 57,
  "sex": "male",
  "condition": "post_stroke",
  "affected_side": "right",
  "time_since_onset_months": 96,
  "assessment_date": "2026-05-11",
  "notes": "Chronic right hemiplegia, independent walking with asymmetry."
}
```

字段约束：

- `case_id`: 系统生成
- `subject_code`: 用户输入，不能包含直接身份信息
- `condition`: V2 默认 `post_stroke`
- `affected_side`: `left | right | bilateral | unknown`

### 7.2 UploadedDataFile

```json
{
  "file_id": "file_001",
  "case_id": "case_20260511_001",
  "data_type": "imu",
  "filename": "imu_walk_trial_01.csv",
  "storage_path": "cases/case_20260511_001/imu_walk_trial_01.csv",
  "schema_status": "validated",
  "sampling_rate_hz": 100,
  "duration_sec": 30.0
}
```

`data_type` 枚举：

- `skeleton`
- `imu`
- `emg`
- `metadata`

### 7.3 SkeletonData Schema

V2 支持宽表或 JSON。

推荐 CSV 字段：

```text
timestamp,
joint_name,
x,
y,
z,
confidence
```

最小必需关节：

- pelvis / hip center
- left_hip
- right_hip
- left_knee
- right_knee
- left_ankle
- right_ankle

### 7.4 IMUData Schema

推荐 CSV 字段：

```text
timestamp,
sensor_id,
sensor_position,
acc_x,
acc_y,
acc_z,
gyro_x,
gyro_y,
gyro_z
```

`sensor_position` 建议值：

- waist
- pelvis
- left_thigh
- right_thigh
- left_shank
- right_shank
- left_ankle
- right_ankle
- foot
- unknown

### 7.5 EMGData Schema

推荐 CSV 字段：

```text
timestamp,
channel_id,
muscle_name,
emg_raw
```

可选字段：

```text
emg_filtered,
emg_envelope,
side
```

## 8. 特征提取

### 8.1 Skeleton Features

V2 MVP 提取：

- walking_duration_sec
- estimated_step_count
- cadence_steps_per_min
- left_right_step_symmetry
- hip_range_of_motion
- knee_range_of_motion
- ankle_range_of_motion
- trunk_sway_proxy
- joint_confidence_mean
- missing_joint_ratio

### 8.2 IMU Features

V2 MVP 提取：

- acceleration_magnitude_mean
- acceleration_magnitude_peak
- angular_velocity_peak
- gait_event_candidate_count
- dominant_frequency
- left_right_peak_asymmetry
- signal_quality_score

### 8.3 EMG Features

V2 MVP 提取：

- rms
- mav
- iemg
- peak_activation
- activation_timing_proxy
- co_activation_proxy
- fatigue_proxy
- signal_quality_score

### 8.4 FeatureSet

```json
{
  "feature_set_id": "feat_case_001_v1",
  "case_id": "case_20260511_001",
  "skeleton_features": {},
  "imu_features": {},
  "emg_features": {},
  "quality_flags": [
    {
      "type": "missing_joint_ratio_high",
      "severity": "medium",
      "message": "Right ankle confidence is low in 18% of frames."
    }
  ]
}
```

## 9. Evidence 设计

V2 引入两类 evidence：

### 9.1 DataEvidence

```json
{
  "data_evidence_id": "data_case001_imu_right_ankle_peak_001",
  "case_id": "case_20260511_001",
  "source_file_id": "file_imu_001",
  "modality": "imu",
  "feature_name": "right_ankle_angular_velocity_peak",
  "value": 185.2,
  "unit": "deg/s",
  "time_range": [12.5, 13.1],
  "interpretation": "Right ankle angular velocity peak is lower than the left side."
}
```

### 9.2 LiteratureEvidence

沿用 V1 `Evidence` 对象：

```json
{
  "evidence_id": "ev_s41598_025_94167_y_p03_c02",
  "paper_title": "IMU-Based quantitative assessment of stroke from gait",
  "page_start": 3,
  "section": "methods",
  "text": "..."
}
```

### 9.3 ReportClaim

```json
{
  "claim_id": "claim_001",
  "claim_text": "该对象的右侧踝部 IMU 峰值低于左侧，提示左右步态动力学存在不对称。",
  "claim_type": "gait_asymmetry",
  "data_evidence_ids": ["data_case001_imu_right_ankle_peak_001"],
  "literature_evidence_ids": ["ev_s41598_025_94167_y_p03_c02"],
  "risk_level": "medium"
}
```

规则：

- 每条专业分析 claim 至少绑定一个 `data_evidence_id`。
- 如果 claim 涉及医学解释，应尽量绑定 `literature_evidence_id`。
- 不允许输出诊断结论，只允许输出数据提示与分析建议。

## 10. V2 Agent 流程

```text
Patient Case + Data Files
-> Data Validator
-> Feature Extractor
-> Report Planner Agent
-> Literature Retriever
-> Report Synthesizer Agent
-> Report Critic Agent
-> Final Report
```

### 10.1 Data Validator

职责：

- 检查文件格式
- 检查必需字段
- 检查时间戳连续性
- 检查缺失值比例
- 检查采样率或时间跨度

输出：

```json
{
  "validation_status": "passed_with_warning",
  "warnings": [],
  "blocking_errors": []
}
```

### 10.2 Feature Extractor

职责：

- 将原始数据转成统一特征
- 生成 `DataEvidence`
- 生成基础图表数据

### 10.3 Report Planner Agent

职责：

- 根据用户问题、数据模态、质量情况，规划报告章节
- 决定需要检索哪些文献证据

### 10.4 Literature Retriever

职责：

- 复用 V1 FAISS + hybrid retrieval
- 针对 feature 和 report section 生成检索 query

### 10.5 Report Synthesizer Agent

职责：

- 生成专业报告
- 把用户数据证据与文献证据合并
- 保持医疗安全措辞

### 10.6 Report Critic Agent

职责：

- 检查 claim 是否绑定证据
- 检查是否出现诊断性或过度医疗建议
- 检查是否混淆数据证据与文献证据
- 检查报告结构是否完整

## 11. V2 API 草案

### 11.1 Case

```text
POST /api/cases
GET /api/cases
GET /api/cases/{case_id}
DELETE /api/cases/{case_id}
```

### 11.2 Upload Data

```text
POST /api/cases/{case_id}/files
GET /api/cases/{case_id}/files
```

### 11.3 Validate

```text
POST /api/cases/{case_id}/validate
```

### 11.4 Analyze

```text
POST /api/cases/{case_id}/analyze
```

### 11.5 Report

```text
POST /api/cases/{case_id}/reports
GET /api/cases/{case_id}/reports/{report_id}
GET /api/cases/{case_id}/reports/{report_id}/export.md
```

## 12. V2 前端信息架构

建议新增 “Cases” 工作区。

页面结构：

```text
左侧：Case 列表 / 文献库状态
中间：数据上传、校验状态、图表
右侧：报告生成与证据卡片
```

### 12.1 Case Detail 页面

模块：

- 基本信息表单
- 数据文件上传区
- 数据校验状态
- 特征指标卡片
- 图表区
- 生成报告按钮
- 报告展示区
- 导出按钮

### 12.2 图表 V2 MVP

- IMU 加速度/角速度时间序列
- EMG 包络或 RMS 柱状图
- 左右侧指标对比柱状图
- 骨骼关键点轨迹简图

## 13. 安全与合规措辞

V2 必须避免：

- “诊断为”
- “可以确定”
- “必须治疗”
- “替代医生判断”

推荐表述：

- “数据提示”
- “可能存在”
- “与文献中描述的模式相似”
- “建议由康复医学专业人员结合临床检查进一步评估”
- “该报告仅作为科研和康复评估辅助，不构成医疗诊断”

报告必须包含免责声明：

```text
本报告由 Agentic RAG 系统基于上传数据与本地文献证据自动生成，仅用于科研、教学或康复评估辅助，不构成医学诊断或治疗建议。请由具备资质的临床专业人员结合完整病史、体格检查和标准量表进行最终判断。
```

## 14. 验收标准

### 14.1 功能验收

- 可创建 patient case
- 可上传 skeleton CSV/JSON
- 可上传 IMU CSV
- 可选上传 EMG CSV
- 可完成 schema validation
- 可提取至少 10 个基础特征
- 可生成至少 1 份结构化中文报告
- 报告包含数据证据与文献证据
- 报告可导出 Markdown

### 14.2 质量验收

- 报告中的专业 claim 100% 绑定 `data_evidence_id`
- 涉及文献依据的 claim 绑定 `literature_evidence_id`
- 不出现诊断性结论
- 图表在浏览器 100% 缩放下可读
- V1 文献问答功能不回退

### 14.3 技术验收

```powershell
py -m compileall .
py -m pytest -q
npm.cmd run build
```

新增测试：

- skeleton schema validation
- IMU schema validation
- EMG schema validation
- feature extraction correctness
- report claim evidence binding
- unsafe medical wording detection

## 15. V2 实施优先级

### Phase 1: Case + Upload

- PatientCase 模型
- case 文件目录
- skeleton/IMU/EMG 上传接口
- 前端 case 页面

### Phase 2: Validation + Feature Extraction

- schema validator
- skeleton feature extractor
- IMU feature extractor
- EMG basic extractor
- feature cards

### Phase 3: Report Generation

- Report Planner Agent
- Literature Retriever 复用
- Report Synthesizer
- Report Critic
- report 页面

### Phase 4: Export + Polish

- Markdown 导出
- 图表优化
- 证据卡片优化
- 示例数据与 demo 流程

## 16. 开放问题

进入实现前需要确认：

1. V2 示例数据格式是否由我们自定义，还是按某个现有设备导出格式适配？
2. 骨骼节点来源是 MediaPipe、OpenPose、Azure Kinect，还是其他 RGB 姿态估计工具？
3. IMU 传感器预计放置位置有哪些？
4. EMG 通道对应哪些肌肉？
5. 报告主要面向科研展示，还是康复临床辅助？
6. V2 是否需要保存多个 case，还是只做单 case demo？


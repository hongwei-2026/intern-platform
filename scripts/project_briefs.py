# -*- coding: utf-8 -*-
"""OSPP-style structured task briefs for seed projects."""

from __future__ import annotations

import json


def brief(**kwargs) -> str:
    base = {
        "lang": "中文",
        "mentor_name": "演示导师",
        "mentor_email": "mentor@demo.hust.edu.cn",
        "license": "Apache-2.0",
        "cycle": "约 2–3 个月",
        "arch": "x86_64 / aarch64",
        "heat": 8,
    }
    base.update(kwargs)
    return json.dumps(base, ensure_ascii=False)


SPMV_BRIEF = brief(
    domains=["Kernel", "HPC", "Sparse"],
    languages=["C", "Python"],
    sections=[
        {
            "title": "背景介绍",
            "body": (
                "稀疏矩阵向量乘（SpMV）是科学计算与图计算中的基础算子。"
                "本任务用于华科开放原子开源俱乐部实习平台演示：打通申请、三级审核与结项流水，"
                "同时让学生完成可核验的开源贡献。"
            ),
        },
        {
            "title": "现有工作",
            "items": [
                "已有基础 SpMV 演示仓库与接口约定",
                "平台侧已支持申请状态机与企业级审核流水",
                "可对接 Gitea / GitHub 提交 PR/MR",
            ],
        },
        {
            "title": "现有不足",
            "items": [
                "缺少可复现的性能对比脚本与基线数据",
                "文档对新人不够友好，环境搭建步骤分散",
                "结项验收口径尚未完全结构化",
            ],
        },
        {
            "title": "希望改进的部分",
            "items": [
                "补齐可运行示例与最小评测脚本",
                "完善 README / FAQ / 贡献指南",
                "明确里程碑与验收 checklist",
            ],
        },
        {
            "title": "最终项目实现的愿景",
            "body": "形成「可一键复现 → 可对比性能 → 可提交 PR」的轻量 SpMV 开源贡献路径。",
        },
    ],
    outputs=[
        "提交可合并的 PR/MR，包含代码与必要测试",
        "输出结项报告（目标、工作、结果、反思）",
        "补充或更新项目文档中的关键使用说明",
    ],
    tech_requirements=[
        "熟悉 C 或 Python 其一，能阅读并修改数值计算相关代码",
        "了解基本的 Git / PR 协作流程",
        "申请时建议附上相关 patch 或讨论链接（社区扩展字段）",
    ],
)

MIRROR_BRIEF = brief(
    domains=["DevOps", "Mirror", "Networking"],
    languages=["Bash", "Python"],
    arch="x86_64",
    sections=[
        {
            "title": "背景介绍",
            "body": (
                "校园镜像站需要稳定的同步策略与可观测性。"
                "本任务演示「差异化申请字段」：除通用申请书外，还需填写镜像同步方案等社区专属信息。"
            ),
        },
        {
            "title": "现有工作",
            "items": [
                "镜像站基础同步链路可运行",
                "社区已配置 mirror_sync_plan 等申请字段",
            ],
        },
        {
            "title": "希望改进的部分",
            "items": [
                "优化同步调度与失败重试策略",
                "补充监控指标与告警建议",
                "沉淀运维文档与排障手册",
            ],
        },
        {
            "title": "最终项目实现的愿景",
            "body": "形成可复制的镜像同步策略模板，降低新同学接手成本。",
        },
    ],
    outputs=[
        "提交同步策略脚本 / 配置与说明文档",
        "结项报告需包含方案对比与验证记录",
    ],
    tech_requirements=[
        "熟悉 Linux / Bash，了解 HTTP 镜像与带宽约束",
        "能编写简单的 Python 运维脚本",
        "申请需填写 mirror_sync_plan 等扩展字段",
    ],
)

DOCS_BRIEF = brief(
    domains=["Documentation", "Community"],
    languages=["Markdown", "Git"],
    cycle="约 1–2 个月",
    sections=[
        {
            "title": "背景介绍",
            "body": "俱乐部新人常因文档分散而卡住。本任务聚焦贡献指南改版，降低入门门槛。",
        },
        {
            "title": "希望改进的部分",
            "items": [
                "统一 README / FAQ / 贡献流程图",
                "补齐常见问题与仓库规范",
            ],
        },
        {
            "title": "最终项目实现的愿景",
            "body": "新同学可按文档独立完成：加入 → 选社区 → 申请任务 → 提交 PR。",
        },
    ],
    outputs=["可维护的文档结构与导航", "至少一次合并到主分支的文档 PR"],
    tech_requirements=["熟练 Markdown 与 Git", "具备信息架构与表达能力"],
)

DEVTOOLS_BRIEF = brief(
    domains=["DeveloperTools", "CI", "DX"],
    languages=["Python", "Shell", "Docker"],
    sections=[
        {
            "title": "背景介绍",
            "body": "本地启动实习平台步骤偏多，本任务封装环境检查与一键拉起脚本。",
        },
        {
            "title": "希望改进的部分",
            "items": [
                "跨平台脚本与失败提示",
                "输出清晰使用文档",
            ],
        },
        {
            "title": "最终项目实现的愿景",
            "body": "新同学可在最短路径拉起前后端并完成一次申请演示。",
        },
    ],
    outputs=["一键启动脚本与文档", "基础环境自检清单"],
    tech_requirements=["熟悉 Python / Shell", "了解 Docker 基础更佳"],
)

AI_BRIEF = brief(
    domains=["AI", "LLM", "Inference"],
    languages=["Python", "PyTorch"],
    sections=[
        {
            "title": "背景介绍",
            "body": "整理开源模型推理示例工程，帮助同学快速跑通本地演示与最小评测。",
        },
        {
            "title": "现有不足",
            "items": ["示例分散", "依赖说明不完整", "缺少最小评测脚本"],
        },
        {
            "title": "最终项目实现的愿景",
            "body": "形成「安装 → 推理演示 → 简单评测」的可复现路径。",
        },
    ],
    outputs=["可运行示例与依赖说明", "最小评测脚本与结项报告"],
    tech_requirements=["具备 Python / ML 基础", "能独立排查依赖与运行环境问题"],
)

BRIEFS_BY_TITLE = {
    "稀疏矩阵向量乘（SpMV）算子优化": (
        "基于开源数值计算方向，完成 SpMV 稀疏矩阵向量乘的性能优化与文档沉淀",
        SPMV_BRIEF,
    ),
    "SpMV 开源实习演示项目": (
        "基于开源数值计算方向，完成 SpMV 稀疏矩阵向量乘的性能优化与文档沉淀",
        SPMV_BRIEF,
    ),
    "开源软件源同步策略优化": (
        "优化镜像站同步策略、失败重试与监控告警，沉淀运维文档",
        MIRROR_BRIEF,
    ),
    "镜像同步策略优化": (
        "优化镜像站同步策略、失败重试与监控告警，沉淀运维文档",
        MIRROR_BRIEF,
    ),
    "openGauss 新手贡献指南整理": (
        "梳理仓库贡献规范、本地编译与文档索引",
        DOCS_BRIEF,
    ),
    "俱乐部贡献指南改版": (
        "梳理仓库贡献规范、本地编译与文档索引",
        DOCS_BRIEF,
    ),
    "开源模型推理示例工程": (
        "基于昇思框架打通本地推理演示与说明文档",
        AI_BRIEF,
    ),
    "RT-Thread 组件文档与示例补全": (
        "完善组件使用说明并补充最小可运行示例",
        DEVTOOLS_BRIEF,
    ),
    "实习平台本地一键启动脚本": (
        "完善组件使用说明并补充最小可运行示例",
        DEVTOOLS_BRIEF,
    ),
}

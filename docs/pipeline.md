# 流水线契约

三个技能之间只通过文件交接，不共享进程与全局状态。这样每个阶段都能单独运行、单独替换。

## 交接物

| 阶段 | 输入 | 输出 | 关键字段 |
| :--- | :--- | :--- | :--- |
| 检索 | 疾病关键词 | `eval_results/geo_evaluation_report.json` | `candidates[].accession`、`gpl`、`samples`、`data_type`、`total_score`、`grade` |
| 下载 | 上游 JSON 或单个 GSE | 标准目录、`info.md`、`grouping.txt` | 目录名、GSM 列表、分组名、平台号 |
| 建项 | GSE、GPL、GSM 分组、先验基因 | `build/<projectId>.json` | `pipelineDag`、`groupingDesign`、`biologicalPriors`、`references` |

## 字段映射

上游报告与下载脚本使用不同命名，下载脚本内部做了兼容：

| 上游字段 | 下载脚本内部字段 | 说明 |
| :--- | :--- | :--- |
| `accession` | `gse` | GSE 编号 |
| `samples` | `samples` | 样本数，仅用于日志 |
| `data_type` | `modality` | `bulk_rnaseq`、`scrna`、`spatial` 等 |
| `gpl` | `gpl` | 平台号 |

报告既可以是纯数组，也可以是 `{ "candidates": [...] }` 包装对象，两种都能读取。

## 失败模式与恢复

| 现象 | 原因 | 处理 |
| :--- | :--- | :--- |
| 检索返回 0 条 | 关键词过窄或疾病名拼写不一致 | 换用英文疾病名或 MeSH 词，放宽 `--retmax` |
| 所有候选都被判 C 级 | 样本量不足或只有表达矩阵 | 接受现实并换数据集，不要为了分数手工改规则 |
| 下载时提示超过 1GB | 安全保护触发 | 确认磁盘与网络后加 `--force-download-raw` |
| 下载后缺 counts | GEO 本身未提供，或文件名不在识别列表 | 查看 `info.md` 第三章，必要时手工补充并在备注中记录 |
| 校验报双命名缺失一侧 | 手工改了 JSON 只改了一边 | 用生成器重新生成，不要手改双字段 |
| 校验报 DAG 与标准步骤不一致 | 手工增删了步骤 | 通过 `isExploratory` 与 `targetKoGene` 控制形态，不要手改 `pipelineDag` |

## 替换阶段

- 只想评估数据：只用 `geo-mining-workflow`，把 JSON 接入你自己的流程。
- 已有 GSE：跳过检索，直接用 `geo-mining-download --gse`。
- 已有自有数据：跳过前两步，把样本与分组写进配置文件，直接用 `geo-workbench-bridge`。
- 目标系统字段不同：保留生成器的内部模型，改写输出适配器，不要把私有字段塞进 `SKILL.md`。

## 版本策略

三个技能独立版本号，仓库整体一个版本号。修改交接字段属于破坏性变更，必须同时提升上游与下游的小版本，并在 `CHANGELOG.md` 记录。

当前版本：

| 组件 | 版本 |
| :--- | :--- |
| 仓库 | 1.0.0 |
| geo-mining-workflow | 1.5.0 |
| geo-mining-download | 1.1.0 |
| geo-workbench-bridge | 2.0.0 |

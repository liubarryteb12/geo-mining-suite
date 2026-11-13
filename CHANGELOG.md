# Changelog

## 1.0.0 (2026-11-13)

首个开源版本，三个技能合并为单仓库。

### geo-mining-workflow 1.5.0

- 脚本改为技能内自包含，不再依赖项目根目录的 `geo_mining_workflow/`。
- 新增 NCBI 请求重试与配置目录自动解析。
- 移除写死的本地路径与私有环境引用。

### geo-mining-download 1.1.0

- 输出目录强制由 `--output-dir` 提供，示例路径改为占位符。
- 保留 1GB 大文件拦截、`--dry-run` 预检与五章节 `info.md` 生成。
- 清理运行时缓存文件。

### geo-workbench-bridge 2.0.0

- 生成器新增 CLI：`--input`、`--out`、`--out-dir`、`--validate`。
- 新增独立校验器 `validate_manifest.js`，不再依赖私有服务端 `project.js`。
- 新增 JSON Schema `schema/workbench-manifest.schema.json`。
- `SKILL.md` 改为通用适配器描述，保留 20 模块契约与四套 DAG 形态。

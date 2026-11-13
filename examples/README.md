# 示例

`demo-bulk/` 是一个完全虚构的 Bulk RNA-seq 课题，用于演示从配置到需求单再到校验的完整过程。

所有标识符都是占位符：

- `GSE999001`、`GSE999002` 不对应真实数据集。
- `GSM9000001` 到 `GSM9000020` 是人工编号。
- `GENE_A` 到 `GENE_C` 不是真实基因符号。

运行：

```bash
node skills/geo-workbench-bridge/scripts/generate_full_manifest.js \
  --input examples/demo-bulk/config.json \
  --out-dir build \
  --validate
```

真实课题请从 `geo-mining-download` 生成的 `info.md` 与 `grouping.txt` 中提取 GSE、GPL 与 GSM。

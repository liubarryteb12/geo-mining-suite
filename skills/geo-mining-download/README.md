# geo-mining-download

GEO 原始数据规范化下载与建档，技能套件的第二段。

安装依赖：

```bash
pip install -r requirements.txt
```

先预检，再正式下载：

```bash
python scripts/download_geo.py --output-dir "/data/geo" --gse GSE245825 --modality bulk_rnaseq --disease-zh "示例疾病" --dry-run
python scripts/download_geo.py --output-dir "/data/geo" --gse GSE245825 --modality bulk_rnaseq --disease-zh "示例疾病"
```

产物包含标准目录、原始文件、`info.md` 与 `grouping.txt`。命名规则见 `references/folder_naming_rules.md`，档案模板见 `references/info_template.md`。

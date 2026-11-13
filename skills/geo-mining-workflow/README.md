# geo-mining-workflow

GEO 数据集检索与五维质量评估，技能套件的第一段。

安装依赖：

```bash
pip install -r requirements.txt
```

运行：

```bash
python scripts/search_geo.py --query "Diabetic Nephropathy" --disease_zh "糖尿病肾病" --retmax 10
```

产物在 `eval_results/`，把其中的 JSON 传给 `geo-mining-download` 即可继续。

规则说明见 `references/scoring_rules.md`，与外部工具的协同方式见 `references/companion_skills_guide.md`。

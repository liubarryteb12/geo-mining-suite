# Contributing

## 开发环境

```bash
pip install -r skills/geo-mining-workflow/requirements.txt
pip install -r skills/geo-mining-download/requirements.txt
node --version
```

## 提交前检查

```bash
npm test
python -m py_compile skills/geo-mining-workflow/scripts/*.py
python -m py_compile skills/geo-mining-download/scripts/*.py
```

`npm test` 覆盖四套 DAG 形态与三类错误输入，不访问网络。

## 修改约定

- 三个技能各自自包含，不要在技能之间 `import` 对方的脚本。
- 技能之间只通过文件交接，字段变更必须同步更新 `docs/pipeline.md`。
- `SKILL.md` 不写绝对路径、私有仓库地址、个人目录。
- 新增契约字段必须同时提供 camelCase 与 snake_case，并更新 JSON Schema 与校验器。
- 涉及真实课题的示例必须脱敏，换成占位符数据集与基因名。

## 数据与隐私

不要提交以下内容：

- 真实患者数据或可识别信息。
- 未发表课题的样本表、分组与靶点。
- 下载后的 GEO 原始文件，仓库只保留代码与文档。

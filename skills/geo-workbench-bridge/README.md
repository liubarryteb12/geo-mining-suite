# geo-workbench-bridge

需求单生成与契约校验，技能套件的第三段。

无第三方依赖，Node.js 18 及以上即可：

```bash
node scripts/generate_full_manifest.js --input ../../examples/demo-bulk/config.json --out-dir build --validate
```

核心文件：

- `scripts/generate_full_manifest.js`：配置扩展为全契约需求单，内置四套标准 DAG。
- `scripts/validate_manifest.js`：独立校验器，不依赖任何私有服务端。
- `schema/workbench-manifest.schema.json`：JSON Schema。
- `references/workbench_manifest_spec.md`：20 模块字段说明。
- `references/downstream_decision_matrix.md`：湿实验反哺建议。

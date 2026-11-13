#!/usr/bin/env node
/**
 * 四套 DAG 形态与三类错误输入的自检，不依赖网络与第三方包。
 * 运行：npm test
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

const { buildFullSpecManifest, LINE_STEPS } = require('../skills/geo-workbench-bridge/scripts/generate_full_manifest.js');
const { validate } = require('../skills/geo-workbench-bridge/scripts/validate_manifest.js');

const demoPath = path.join(__dirname, '..', 'examples', 'demo-bulk', 'config.json');
const demo = JSON.parse(fs.readFileSync(demoPath, 'utf8'));

const cases = [
  { name: 'line1 targeted', patch: { lineId: 'line1_bulk' }, steps: 15 },
  { name: 'line2 targeted', patch: { lineId: 'line2_scrna', targetKoGene: 'GENE_A' }, steps: 22 },
  { name: 'line3 targeted', patch: { lineId: 'line3_spatial', targetKoGene: 'GENE_A' }, steps: 17 },
  { name: 'line3 exploratory', patch: { lineId: 'line3_spatial', isExploratory: true, targetKoGene: '' }, steps: 15 }
];

let failed = 0;

for (const testCase of cases) {
  const input = { ...demo, ...testCase.patch };
  const manifest = buildFullSpecManifest(input);
  const result = validate(manifest);
  try {
    assert.strictEqual(manifest.pipelineDag.length, testCase.steps, `DAG 步数不是 ${testCase.steps}`);
    assert.deepStrictEqual(result.errors, [], `校验错误: ${result.errors.join(' | ')}`);
    console.log(`[PASS] ${testCase.name} | dag=${manifest.pipelineDag.length}`);
  } catch (error) {
    failed += 1;
    console.log(`[FAIL] ${testCase.name} | ${error.message}`);
  }
}

const negativeCases = [
  {
    name: 'line3 targeted without targetKoGene',
    build: () => buildFullSpecManifest({ ...demo, lineId: 'line3_spatial', targetKoGene: '' }),
    expect: 'targetKoGene'
  },
  {
    name: 'invalid GSM id',
    build: () => {
      const manifest = buildFullSpecManifest({ ...demo, lineId: 'line1_bulk' });
      manifest.groupingDesign.groups[0].sampleIds[0] = 'SAMPLE_1';
      manifest.grouping_design = manifest.groupingDesign;
      return manifest;
    },
    expect: 'GSM'
  },
  {
    name: 'missing pipeline_dag alias',
    build: () => {
      const manifest = buildFullSpecManifest({ ...demo, lineId: 'line1_bulk' });
      delete manifest.pipeline_dag;
      return manifest;
    },
    expect: '双命名'
  }
];

for (const negative of negativeCases) {
  const result = validate(negative.build());
  const matched = result.errors.some((msg) => msg.includes(negative.expect));
  if (matched) {
    console.log(`[PASS] reject ${negative.name}`);
  } else {
    failed += 1;
    console.log(`[FAIL] reject ${negative.name} | 未命中期望错误 ${negative.expect}`);
  }
}

assert.ok(Object.keys(LINE_STEPS).length === 3, '应定义三条分析线');

if (failed > 0) {
  console.log(`\n${failed} 项失败`);
  process.exit(1);
}
console.log('\n全部自检通过');

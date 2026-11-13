#!/usr/bin/env node
/**
 * validate_manifest.js
 *
 * 独立需求单校验器，不依赖任何外部工作台服务端代码。
 * 用途：在导入目标系统之前，确认 manifest.json 满足 20 模块契约、
 * 双命名一致、DAG 完整、样本编号合法、虚拟敲除与靶基因匹配。
 *
 * 用法：
 *   node validate_manifest.js <manifest.json> [--json] [--quiet]
 *
 * 退出码：0 通过，1 失败，2 参数或读取错误。
 */

const fs = require('fs');
const path = require('path');
const { LINE_STEPS } = require('./generate_full_manifest.js');

const DUAL_PAIRS = [
  ['basicInfo', 'basic_info'],
  ['dataSource', 'data_source'],
  ['groupingDesign', 'grouping_design'],
  ['pipelineDag', 'pipeline_dag'],
  ['biologicalPriors', 'biological_priors'],
  ['phenotypeModules', 'phenotype_modules'],
  ['analysisCutoffs', 'analysis_cutoffs'],
  ['plotLayoutConfig', 'plot_layout_config'],
  ['experimentalDesign', 'experimental_design'],
  ['validationGroupMapping', 'validation_group_mapping'],
  ['wgcnaConfig', 'wgcna_config'],
  ['aclAndOutput', 'acl_and_output'],
  ['dataFiles', 'data_files'],
  ['modIds', 'mod_ids']
];

const REQUIRED_ANY = [
  ['manifest_version'],
  ['schema_version'],
  ['id', 'projectId', 'project_id'],
  ['lineId', 'line_id', 'seriesId'],
  ['basicInfo', 'basic_info'],
  ['dataSource', 'data_source'],
  ['groupingDesign', 'grouping_design'],
  ['pipelineDag', 'pipeline_dag'],
  ['steps', 'modIds', 'mod_ids'],
  ['biologicalPriors', 'biological_priors'],
  ['phenotypeModules', 'phenotype_modules'],
  ['analysisCutoffs', 'analysis_cutoffs'],
  ['plotLayoutConfig', 'plot_layout_config'],
  ['experimentalDesign', 'experimental_design'],
  ['validationGroupMapping', 'validation_group_mapping'],
  ['wgcnaConfig', 'wgcna_config'],
  ['references'],
  ['aclAndOutput', 'acl_and_output'],
  ['figure_templates'],
  ['dataFiles', 'data_files'],
  ['notes']
];

const LINE_ENUM = ['line1_bulk', 'line2_scrna', 'line3_spatial'];

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function deepEqual(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function validate(manifest) {
  const errors = [];
  const warnings = [];

  if (!isPlainObject(manifest)) {
    errors.push('根节点必须是 JSON 对象');
    return { errors, warnings, summary: {} };
  }

  for (const aliases of REQUIRED_ANY) {
    const present = aliases.filter((key) => Object.prototype.hasOwnProperty.call(manifest, key));
    if (present.length === 0) {
      errors.push(`缺少契约模块: ${aliases.join(' 或 ')}`);
    }
  }

  const lineId = manifest.lineId || manifest.line_id || manifest.seriesId;
  if (!LINE_ENUM.includes(lineId)) {
    errors.push(`lineId 不在枚举内: ${String(lineId)}`);
  }

  const projectId = manifest.projectId || manifest.project_id || manifest.id || '';
  if (!/^[A-Za-z0-9_]+$/.test(projectId)) {
    errors.push(`项目 ID 只能包含字母、数字、下划线: ${String(projectId)}`);
  }
  const idValues = [manifest.id, manifest.projectId, manifest.project_id].filter((v) => v !== undefined);
  if (idValues.length > 1 && new Set(idValues).size !== 1) {
    errors.push('id、projectId、project_id 三者不一致');
  }

  for (const [camel, snake] of DUAL_PAIRS) {
    if (manifest[camel] === undefined) errors.push(`双命名缺失一侧: ${camel}`);
    if (manifest[snake] === undefined) errors.push(`双命名缺失一侧: ${snake}`);
    if (manifest[camel] !== undefined && manifest[snake] !== undefined && !deepEqual(manifest[camel], manifest[snake])) {
      errors.push(`双命名内容不一致: ${camel} 与 ${snake}`);
    }
  }

  const dag = manifest.pipelineDag || manifest.pipeline_dag || [];
  const steps = manifest.steps || [];
  const modIds = manifest.modIds || manifest.mod_ids || [];

  if (!Array.isArray(dag) || dag.length === 0) {
    errors.push('pipelineDag 为空');
  } else {
    const stepIds = dag.map((s) => s && s.stepId);
    const stepModIds = dag.map((s) => s && s.mod_id);
    dag.forEach((step, index) => {
      if (!isPlainObject(step)) {
        errors.push(`pipelineDag 第 ${index + 1} 项不是对象`);
        return;
      }
      if (step.order !== index + 1) {
        errors.push(`pipelineDag 顺序断裂: 第 ${index + 1} 项 order=${step.order}`);
      }
      if (!step.stepId) errors.push(`pipelineDag 第 ${index + 1} 项缺少 stepId`);
      if (!step.mod_id) errors.push(`pipelineDag 第 ${index + 1} 项缺少 mod_id`);
    });
    if (new Set(stepIds).size !== stepIds.length) {
      errors.push('pipelineDag 存在重复 stepId');
    }
    if (new Set(stepModIds).size !== stepModIds.length) {
      errors.push('pipelineDag 存在重复 mod_id');
    }

    const canonical = (LINE_STEPS[lineId] || []).map((s) => s.stepId);
    const mode = manifest.analysisMode || manifest.analysis_mode || '';
    const isExploratory = mode === 'exploratory' || String(manifest.notes || '').includes('exploratory');
    const expected = canonical.filter((id) => {
      if (!isExploratory) return true;
      return !id.includes('knockout') && !id.includes('dr_post');
    });
    if (expected.length > 0 && !deepEqual(stepIds, expected)) {
      errors.push(
        `DAG 与标准步骤不一致: 期望 ${expected.length} 步 [${expected.join(', ')}]，实际 ${stepIds.length} 步`
      );
    }

    if (!deepEqual(steps, stepIds)) {
      errors.push('steps 与 pipelineDag 的 stepId 顺序不一致');
    }
    if (!deepEqual(modIds, stepModIds)) {
      errors.push('modIds 与 pipelineDag 的 mod_id 顺序不一致');
    }
  }

  const priors = manifest.biologicalPriors || manifest.biological_priors || {};
  const targetKoGene = priors.targetKoGene || priors.target_ko_gene || manifest.koGene || '';
  const hasKoStep = Array.isArray(dag) && dag.some((s) => String(s && s.stepId).includes('knockout'));
  if (hasKoStep && !targetKoGene) {
    errors.push('包含虚拟敲除步骤但未提供 targetKoGene');
  }
  if (!hasKoStep && targetKoGene) {
    warnings.push('提供了 targetKoGene 但 DAG 中没有虚拟敲除步骤');
  }
  if (priors.focusGenes && !Array.isArray(priors.focusGenes)) {
    errors.push('focusGenes 必须是数组');
  }

  const dataSource = manifest.dataSource || manifest.data_source || {};
  const datasets = Array.isArray(dataSource.datasets) ? dataSource.datasets : [];
  if (datasets.length === 0) {
    errors.push('dataSource.datasets 为空');
  } else {
    datasets.forEach((d, index) => {
      if (!/^GSE\d+$/.test(String(d.gse || ''))) {
        errors.push(`数据集 ${index + 1} 的 gse 格式非法: ${String(d.gse)}`);
      }
      if (!/^GPL\d+$/.test(String(d.gpl || ''))) {
        errors.push(`数据集 ${index + 1} 的 gpl 格式非法: ${String(d.gpl)}`);
      }
    });
    const summed = datasets.reduce((sum, d) => sum + (Number(d.sampleCount) || 0), 0);
    if (Number(dataSource.sampleCount) !== summed) {
      errors.push(`dataSource.sampleCount=${dataSource.sampleCount} 与数据集样本数之和 ${summed} 不一致`);
    }
  }

  const grouping = manifest.groupingDesign || manifest.grouping_design || {};
  const groups = Array.isArray(grouping.groups) ? grouping.groups : [];
  if (groups.length < 2) {
    errors.push('分组数量少于 2');
  }
  const allSamples = [];
  groups.forEach((g, index) => {
    if (!Array.isArray(g.sampleIds)) {
      errors.push(`分组 ${index + 1} 的 sampleIds 不是数组`);
      return;
    }
    g.sampleIds.forEach((id) => {
      allSamples.push(id);
      if (!/^GSM\d+$/.test(String(id))) {
        errors.push(`样本编号必须以 GSM 开头: ${String(id)}`);
      }
    });
  });
  if (new Set(allSamples).size !== allSamples.length) {
    errors.push('同一 GSM 样本出现在多个分组中');
  }
  if (datasets.length > 0) {
    const declared = Number(dataSource.sampleCount) || 0;
    if (allSamples.length !== declared) {
      errors.push(`分组样本总数 ${allSamples.length} 与 dataSource.sampleCount ${declared} 不一致`);
    }
  }

  const references = Array.isArray(manifest.references) ? manifest.references : [];
  references.forEach((ref, index) => {
    if (!ref || typeof ref !== 'object') {
      errors.push(`references 第 ${index + 1} 项不是对象`);
      return;
    }
    if (!ref.name) errors.push(`references 第 ${index + 1} 项缺少 name`);
    if (!ref.path) errors.push(`references 第 ${index + 1} 项缺少 path`);
    if (!(Number(ref.size) > 0)) errors.push(`references 第 ${index + 1} 项 size 非法`);
  });

  const cutoffs = manifest.analysisCutoffs || manifest.analysis_cutoffs || {};
  ['adj_p_threshold', 'p_threshold'].forEach((key) => {
    if (cutoffs[key] !== undefined) {
      const value = Number(cutoffs[key]);
      if (!(value > 0 && value < 1)) errors.push(`${key} 应在 0 与 1 之间: ${cutoffs[key]}`);
    }
  });

  const basicInfo = manifest.basicInfo || manifest.basic_info || {};
  if (!basicInfo.name) errors.push('basicInfo.name 为空');
  if (!basicInfo.disease) warnings.push('basicInfo.disease 为空');

  if (references.length === 0) warnings.push('references 为空，导入后文献列表会显示 0 篇');
  if (!manifest.notes) warnings.push('notes 为空，建议补充合规声明与实验背景');
  if (!manifest.phenotypeModules || Object.keys(manifest.phenotypeModules).length === 0) {
    warnings.push('phenotypeModules 为空，富集分析的生物学背景会缺失');
  }

  return {
    errors,
    warnings,
    summary: {
      projectId,
      lineId,
      dagSteps: Array.isArray(dag) ? dag.length : 0,
      datasets: datasets.length,
      samples: allSamples.length,
      references: references.length
    }
  };
}

function main() {
  const args = process.argv.slice(2);
  const file = args.find((a) => !a.startsWith('--'));
  const asJson = args.includes('--json');
  const quiet = args.includes('--quiet');

  if (!file) {
    console.error('用法: node validate_manifest.js <manifest.json> [--json] [--quiet]');
    process.exit(2);
  }

  let manifest;
  try {
    manifest = JSON.parse(fs.readFileSync(path.resolve(file), 'utf8'));
  } catch (error) {
    console.error(`读取或解析失败: ${error.message}`);
    process.exit(2);
  }

  const result = validate(manifest);
  const passed = result.errors.length === 0;

  if (asJson) {
    console.log(JSON.stringify({ passed, file: path.resolve(file), ...result }, null, 2));
  } else if (!quiet || !passed) {
    const s = result.summary;
    if (passed) {
      console.log(
        `PASS ${path.basename(file)} | line=${s.lineId} | dag=${s.dagSteps} | samples=${s.samples} | refs=${s.references}`
      );
    } else {
      console.log(`FAIL ${path.basename(file)} | ${result.errors.length} 个错误，${result.warnings.length} 个警告`);
      result.errors.forEach((msg, index) => console.log(`  E${index + 1}. ${msg}`));
    }
    if (result.warnings.length > 0 && !quiet) {
      result.warnings.forEach((msg, index) => console.log(`  W${index + 1}. ${msg}`));
    }
  }

  process.exit(passed ? 0 : 1);
}

if (require.main === module) {
  main();
}

module.exports = { validate, DUAL_PAIRS, REQUIRED_ANY, LINE_ENUM };

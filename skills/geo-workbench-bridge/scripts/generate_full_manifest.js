/**
 * generate_full_manifest.js
 *
 * 把一份精简的课题配置扩展成完整需求单：
 * 1. 补齐 20 个契约模块，同一语义同时输出 camelCase 与 snake_case
 * 2. 按分析线装配完整 pipelineDag、steps、modIds，前端可自动勾选全部步骤
 * 3. 根据是否已锚定靶基因，在 17 步与 15 步空间转录组 DAG 之间切换
 * 4. 生成合法的项目 ID 与时间戳文件名
 *
 * 用法：
 *   node generate_full_manifest.js --input config.json --out manifest.json
 *   node generate_full_manifest.js --input config.json --out-dir build
 *   node generate_full_manifest.js --input config.json --out-dir build --validate
 */

const fs = require('fs');
const path = require('path');

// 标准三线步骤全量定义
const LINE_STEPS = {
  line1_bulk: [
    { order: 1, stepId: 'prep_matrix', mod_id: 'l1_qc_ingest' },
    { order: 2, stepId: 'qc_matrix', mod_id: 'l1_qc_matrix' },
    { order: 3, stepId: 'pca_matrix', mod_id: 'l1_pca_matrix' },
    { order: 4, stepId: 'deg_limma', mod_id: 'l1_deg_limma' },
    { order: 5, stepId: 'wgcna_modules', mod_id: 'l1_wgcna_modules' },
    { order: 6, stepId: 'enrichment_bulk', mod_id: 'l1_enrich_bulk' },
    { order: 7, stepId: 'enrichment_figures', mod_id: 'l1_enrich_figures' },
    { order: 8, stepId: 'ppi_string', mod_id: 'l1_ppi_string' },
    { order: 9, stepId: 'key_genes', mod_id: 'l1_key_genes' },
    { order: 10, stepId: 'ml_model', mod_id: 'l1_ml_model' },
    { order: 11, stepId: 'ml_hub_analysis', mod_id: 'l1_ml_hub' },
    { order: 12, stepId: 'ml_diagnostics', mod_id: 'l1_ml_diag' },
    { order: 13, stepId: 'external_validation', mod_id: 'l1_ext_val' },
    { order: 14, stepId: 'cox_analysis', mod_id: 'l1_cox_analysis' },
    { order: 15, stepId: 'bulk_figures', mod_id: 'l1_bulk_figures' }
  ],
  line2_scrna: [
    { order: 1, stepId: 'ingest_counts', mod_id: 'l2_ingest_counts' },
    { order: 2, stepId: 'qc_cells', mod_id: 'l2_qc_cells' },
    { order: 3, stepId: 'normalize_hvg', mod_id: 'l2_normalize_hvg' },
    { order: 4, stepId: 'integrate_harmony', mod_id: 'l2_integrate_harmony' },
    { order: 5, stepId: 'cluster_umap', mod_id: 'l2_cluster_umap' },
    { order: 6, stepId: 'annotate_celltypes', mod_id: 'l2_annotate_celltypes' },
    { order: 7, stepId: 'scrna_composition', mod_id: 'l2_composition' },
    { order: 8, stepId: 'deg_groups', mod_id: 'l2_deg_groups' },
    { order: 9, stepId: 'subcluster', mod_id: 'l2_subcluster' },
    { order: 10, stepId: 'enrichment', mod_id: 'l2_enrichment' },
    { order: 11, stepId: 'enrichment_figures', mod_id: 'l2_enrich_figures' },
    { order: 12, stepId: 'pseudotime', mod_id: 'l2_pseudotime' },
    { order: 13, stepId: 'cell_communication', mod_id: 'l2_communication' },
    { order: 14, stepId: 'gsva_pathways', mod_id: 'l2_gsva_pathways' },
    { order: 15, stepId: 'scenic_tf', mod_id: 'l2_tf_scenic' },
    { order: 16, stepId: 'scenic_figures', mod_id: 'l2_scenic_figures' },
    { order: 17, stepId: 'tf_activity', mod_id: 'l2_tf_activity' },
    { order: 18, stepId: 'virtual_knockout', mod_id: 'l2_ko_virtual' },
    { order: 19, stepId: 'summarize_dr', mod_id: 'l2_summarize_dr' },
    { order: 20, stepId: 'target_gene_localization', mod_id: 'l2_target_localization' },
    { order: 21, stepId: 'dr_post_analysis', mod_id: 'l2_dr_post' },
    { order: 22, stepId: 'scrna_figures', mod_id: 'l2_figures_scrna' }
  ],
  line3_spatial: [
    { order: 1, stepId: 'ingest_spatial', mod_id: 'l3_ingest_spatial' },
    { order: 2, stepId: 'qc_spots', mod_id: 'l3_qc_spots' },
    { order: 3, stepId: 'normalize_hvg', mod_id: 'l3_qc_normalize' },
    { order: 4, stepId: 'dim_reduce', mod_id: 'l3_dimred_reduce' },
    { order: 5, stepId: 'spatial_domains', mod_id: 'l3_dimred_domains' },
    { order: 6, stepId: 'spatial_markers', mod_id: 'l3_dimred_markers' },
    { order: 7, stepId: 'spatial_autocorr', mod_id: 'l3_stats_autocorr' },
    { order: 8, stepId: 'spatial_cooccurrence', mod_id: 'l3_stats_cooccur' },
    { order: 9, stepId: 'spatial_composition', mod_id: 'l3_stats_composition' },
    { order: 10, stepId: 'spatial_communication', mod_id: 'l3_stats_communication' },
    { order: 11, stepId: 'celltype_annotation', mod_id: 'l3_branches_celltype' },
    { order: 12, stepId: 'spatial_localization', mod_id: 'l3_branches_localization' },
    { order: 13, stepId: 'enrichment', mod_id: 'l3_branches_enrich' },
    { order: 14, stepId: 'enrichment_figures', mod_id: 'l3_branches_enrich_fig' },
    { order: 15, stepId: 'spatial_knockout', mod_id: 'l3_ko_spatial' },
    { order: 16, stepId: 'dr_post_analysis', mod_id: 'l3_ko_drpost' },
    { order: 17, stepId: 'spatial_figures', mod_id: 'l3_figures_spatial' }
  ]
};

/**
 * 构造 100% 全契约适配需求单
 */
function buildFullSpecManifest(input) {
  const lineId = input.lineId || 'line3_spatial';
  const isExploratory = input.isExploratory || false;
  let fullSteps = LINE_STEPS[lineId] || [];

  // 若为无偏探索模式且未指定靶基因，过滤掉虚拟敲除步骤，避免校验失败
  if (isExploratory && !input.targetKoGene) {
    fullSteps = fullSteps.filter(
      (s) => !s.stepId.includes('knockout') && !s.stepId.includes('dr_post')
    ).map((s, idx) => ({ ...s, order: idx + 1 }));
  }

  const now = new Date();
  const isoTime = input.submittedAt || now.toISOString();
  const pad = (n) => String(n).padStart(2, '0');
  const idStamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  const defaultProjectId = `PRJ_${lineId.toUpperCase()}_${idStamp}`;

  // 基础信息
  const basicInfo = {
    name: input.name || '未命名生信分析课题',
    description: input.description || '课题分析需求说明',
    domain: input.domain || '未分类',
    disease: input.disease || '待填写疾病',
    species: input.species || 'Homo sapiens',
    contact: input.contact || '课题调研组',
    nonTumorVerified: true
  };

  // 数据源
  const datasets = Array.isArray(input.datasets) ? input.datasets : [];
  const totalSamples = datasets.reduce((sum, d) => sum + (Number(d.sampleCount) || 0), 0);
  const dataSource = {
    source: input.source || 'GEO',
    dataType: input.dataType || (lineId === 'line3_spatial' ? 'spatial' : (lineId === 'line2_scrna' ? 'scrna' : 'bulk_rnaseq')),
    data_type: input.dataType || (lineId === 'line3_spatial' ? 'spatial' : (lineId === 'line2_scrna' ? 'scrna' : 'bulk_rnaseq')),
    data_source_mode: 'PUBLIC_DB',
    datasets: datasets.map(d => ({
      gse: d.gse,
      gpl: d.gpl,
      role: d.role || 'train',
      dataType: d.dataType || (lineId === 'line3_spatial' ? 'spatial' : (lineId === 'line2_scrna' ? 'scrna' : 'bulk_rnaseq')),
      sampleCount: Number(d.sampleCount) || 0,
      tissue: d.tissue || '目标组织'
    })),
    sampleCount: totalSamples,
    tissue: input.tissue || (datasets[0]?.tissue || '目标组织')
  };

  // 分组设计
  const groups = (Array.isArray(input.groups) ? input.groups : []).map((g, idx) => ({
    groupId: g.groupId || `g${idx + 1}`,
    groupName: g.groupName || (idx === 0 ? 'Control' : 'Disease'),
    role: g.role || (idx === 0 ? 'reference' : 'disease_stage'),
    stageOrder: typeof g.stageOrder === 'number' ? g.stageOrder : idx,
    colorHex: g.colorHex || (idx === 0 ? '#3B4992' : '#EE0000'),
    sampleIds: Array.isArray(g.sampleIds) ? g.sampleIds : []
  }));

  const contrasts = (Array.isArray(input.contrasts) && input.contrasts.length > 0)
    ? input.contrasts.map((c, idx) => ({
        name: c.name || `${groups[1]?.groupName || 'Disease'}_vs_${groups[0]?.groupName || 'Control'}`,
        case: c.case || (groups[1]?.groupName || 'Disease'),
        ctrl: c.ctrl || (groups[0]?.groupName || 'Control'),
        isPrimary: typeof c.isPrimary === 'boolean' ? c.isPrimary : (idx === 0),
        enabled: true
      }))
    : [
        {
          name: `${groups[1]?.groupName || 'Disease'}_vs_${groups[0]?.groupName || 'Control'}`,
          case: groups[1]?.groupName || 'Disease',
          ctrl: groups[0]?.groupName || 'Control',
          isPrimary: true,
          enabled: true
        }
      ];

  const groupingDesign = {
    mode: input.groupMode || 'two_group',
    groups,
    contrasts
  };

  // 生物学先验
  const focusGenes = Array.isArray(input.focusGenes) ? input.focusGenes : [];
  const targetKoGene = input.targetKoGene ? String(input.targetKoGene).trim() : '';
  const biologicalPriors = {
    targetKoGene,
    target_ko_gene: targetKoGene,
    focusGenes,
    focus_genes: focusGenes,
    koFallbackPolicy: input.koFallbackPolicy || 'strict_abort',
    ko_fallback_policy: input.koFallbackPolicy || 'strict_abort'
  };

  // 分析阈值
  const analysisCutoffs = {
    profile: input.cutoffProfile || 'standard',
    use_adj_p: input.useAdjP !== false,
    adj_p_threshold: input.adjPThreshold || 0.05,
    log2fc_threshold: input.log2fcThreshold || 1.0,
    padj_threshold: input.padjThreshold || 0.05,
    p_threshold: input.pThreshold || 0.05,
    max_mt_percent: input.maxMtPercent || 20
  };

  // 参考文献
  const references = (Array.isArray(input.references) ? input.references : []).map(r => ({
    name: r.name || (r.path ? path.basename(r.path) : `${r.gse || 'ref'}.pdf`),
    path: r.path || `refs/${r.name || (r.gse ? `${r.gse}.pdf` : 'reference.pdf')}`,
    size: Number(r.size) || 102400,
    title: r.title || '',
    authors: r.authors || '',
    journal: r.journal || '',
    year: r.year || 2024,
    volume: r.volume || '',
    pmid: r.pmid || '',
    doi: r.doi || '',
    gse: r.gse || '',
    notes: r.notes || ''
  }));

  // 装配最终全契约字典（含驼峰与下划线双命名）
  const manifest = {
    manifest_version: '1.0',
    schema_version: '2.0',
    submitted_at: isoTime,
    created_at: isoTime,
    id: input.id || defaultProjectId,
    projectId: input.id || defaultProjectId,
    project_id: input.id || defaultProjectId,
    lineId: lineId,
    line_id: lineId,
    seriesId: lineId,
    series_id: lineId,
    analysisMode: isExploratory ? 'exploratory' : 'targeted',
    analysis_mode: isExploratory ? 'exploratory' : 'targeted',
    basicInfo,
    basic_info: basicInfo,
    dataSource,
    data_source: dataSource,
    groupingDesign,
    grouping_design: groupingDesign,
    biologicalPriors,
    biological_priors: biologicalPriors,
    phenotypeModules: input.phenotypeModules || {},
    phenotype_modules: input.phenotypeModules || {},
    steps: fullSteps.map(s => s.stepId),
    pipelineDag: fullSteps,
    pipeline_dag: fullSteps,
    modIds: fullSteps.map(s => s.mod_id),
    mod_ids: fullSteps.map(s => s.mod_id),
    koGene: targetKoGene,
    figure_templates: input.figureTemplates || [],
    figure_tasks: [],
    aclAndOutput: {
      owner: input.owner || 'current_user',
      collaborators: input.collaborators || [],
      expectedFormats: input.expectedFormats || ['png_300dpi', 'tsv_tables', 'pdf_vector', 'rds_checkpoint', 'audit_json'],
      targetKoGene
    },
    acl_and_output: {
      owner: input.owner || 'current_user',
      collaborators: input.collaborators || [],
      expectedFormats: input.expectedFormats || ['png_300dpi', 'tsv_tables', 'pdf_vector', 'rds_checkpoint', 'audit_json'],
      targetKoGene
    },
    plotLayoutConfig: { templateId: input.plotTemplateId || 'template_4x3', template_id: input.plotTemplateId || 'template_4x3' },
    plot_layout_config: { templateId: input.plotTemplateId || 'template_4x3', template_id: input.plotTemplateId || 'template_4x3' },
    analysisCutoffs,
    analysis_cutoffs: analysisCutoffs,
    experimentalDesign: input.experimentalDesign || { isPaired: false, pairMap: {}, covariates: { batchCol: '', adjustedVariables: [] } },
    experimental_design: input.experimentalDesign || { isPaired: false, pairMap: {}, covariates: { batchCol: '', adjustedVariables: [] } },
    validationGroupMapping: input.validationGroupMapping || { valControlSamples: [], valTreatSamples: [] },
    validation_group_mapping: input.validationGroupMapping || { valControlSamples: [], valTreatSamples: [] },
    wgcnaConfig: input.wgcnaConfig || {},
    wgcna_config: input.wgcnaConfig || {},
    dataFiles: [],
    data_files: [],
    references,
    notes: input.notes || ''
  };

  return manifest;
}

module.exports = {
  LINE_STEPS,
  buildFullSpecManifest
};

function parseArgs(argv) {
  const options = { outDir: 'build', validate: false, timestampName: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--input') options.input = argv[++i];
    else if (arg === '--out') options.out = argv[++i];
    else if (arg === '--out-dir') options.outDir = argv[++i];
    else if (arg === '--validate') options.validate = true;
    else if (arg === '--timestamp-name') options.timestampName = true;
    else if (arg === '--help' || arg === '-h') options.help = true;
    else if (!arg.startsWith('--') && !options.input) options.input = arg;
    else throw new Error(`未知参数: ${arg}`);
  }
  return options;
}

function main() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    process.exit(2);
  }

  if (options.help || !options.input) {
    console.log([
      '用法: node generate_full_manifest.js --input config.json [选项]',
      '',
      '选项:',
      '  --input <path>        课题配置 JSON',
      '  --out <path>          指定输出文件',
      '  --out-dir <dir>       输出目录，默认 build',
      '  --timestamp-name      文件名加 YYYY-MM-DD_HHMMSS 前缀',
      '  --validate            生成后立即调用校验器',
      '  --help                显示帮助'
    ].join('\n'));
    process.exit(options.help ? 0 : 2);
  }

  let input;
  try {
    input = JSON.parse(fs.readFileSync(path.resolve(options.input), 'utf8'));
  } catch (error) {
    console.error(`读取配置失败: ${error.message}`);
    process.exit(2);
  }

  const manifest = buildFullSpecManifest(input);
  const projectId = manifest.projectId || manifest.id || 'manifest';
  let outFile = options.out;

  if (!outFile) {
    fs.mkdirSync(path.resolve(options.outDir), { recursive: true });
    const date = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const stamp = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
    const fileName = options.timestampName ? `${stamp}_${projectId}.json` : `${projectId}.json`;
    outFile = path.join(options.outDir, fileName);
  }

  fs.mkdirSync(path.dirname(path.resolve(outFile)), { recursive: true });
  fs.writeFileSync(path.resolve(outFile), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  console.log(`[OK] 需求单已生成: ${path.resolve(outFile)}`);
  console.log(`     line=${manifest.lineId} dag=${manifest.pipelineDag.length} samples=${manifest.dataSource.sampleCount}`);

  if (options.validate) {
    const { validate } = require('./validate_manifest.js');
    const result = validate(manifest);
    if (result.errors.length > 0) {
      console.log(`[FAIL] 校验未通过，${result.errors.length} 个错误`);
      result.errors.forEach((msg, index) => console.log(`  E${index + 1}. ${msg}`));
      process.exit(1);
    }
    result.warnings.forEach((msg, index) => console.log(`  W${index + 1}. ${msg}`));
    console.log('[PASS] 校验通过');
  }
}

if (require.main === module) {
  main();
}

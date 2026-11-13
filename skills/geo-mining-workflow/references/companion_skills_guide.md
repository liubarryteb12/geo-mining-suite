# 伴生协同技能（Companion Skills）安装与联动开发指南

本指南为 `geo-mining-workflow`（GEO 检索与质量评估）与两大外部开源技能 **`agent-reach`**、**`BrowserSkill`** 的协同联动规范。

---

## 一、 两大伴生技能定位与安装方法

### 1. `agent-reach`（开源社区与配套源码深度检索）
* **开源地址**：[https://github.com/Panniantong/agent-reach](https://github.com/Panniantong/agent-reach)
* **核心定位**：极轻量级跨平台只读内容抓取器。负责在终端直接抓取论文作者存放在 GitHub 的清洗代码/分析脚本、抓取学术论坛（Reddit/Twitter/B站等）对特定 GSE 数据集实验缺陷或批次效应的讨论。
* **安装方法**：
  ```bash
  # 方式 1：Python 包安装
  pip install agent-reach
  # 或通过 uv 安装
  uv tool install agent-reach

  # 方式 2：作为通用 Skill 挂载到宿主目录
  # 将代码克隆或放置到 ~/.gemini/skills/agent-reach/
  ```
* **基础自检与配置**：
  ```bash
  agent-reach channels      # 查看支持的平台与参数
  agent-reach --version     # 确认 CLI 就绪
  ```

---

### 2. `BrowserSkill`（机构内网鉴权与收费文献破壁）
* **开源地址**：[https://github.com/Tencent/BrowserSkill](https://github.com/Tencent/BrowserSkill)
* **核心定位**：由腾讯开源的真实浏览器桥梁（CLI + 浏览器扩展）。负责借用你日常正在使用的 Chrome / Edge 浏览器已有登录态（继承高校/医院 VPN、CARSI 图书馆账号、Web of Science），突破 Nature/Cell 等期刊的付费壁垒下载全文及临床补充大表，并接管 NCBI 人机验证。
* **安装方法**：
  * **第一步：安装 CLI (`bsk`)**
    * **Windows (PowerShell)**：
      ```powershell
      irm https://raw.githubusercontent.com/Tencent/BrowserSkill/main/install.ps1 | iex
      ```
    * **macOS / Linux**：
      ```bash
      curl -fsSL https://raw.githubusercontent.com/Tencent/BrowserSkill/main/install.sh | sh
      export PATH="${BSK_INSTALL_DIR:-$HOME/.local/bin}:$PATH"
      ```
  * **第二步：安装浏览器扩展**
    * 在 Chrome Web Store 或 Edge 外接程序商店搜索并启用 **BrowserSkill** 插件。
  * **第三步：Agent 对接**
    * 在终端执行：`bsk install-skill` 完成与本地 Coding Agent 的对接绑定。

---

## 二、 联动调用预留规范（Linkage Protocols）

在执行 `geo-mining-workflow` 检索与打分时，系统遵循以下标准化联动协议：

### 场景 1：发现 GSE 关联的 GitHub 仓库
当元数据或论文中包含作者的数据处理代码链接时：
1. **联动判定**：检查系统是否存在 `agent-reach` 命令。
2. **存在时触发**：
   ```bash
   agent-reach github repo <owner>/<repo>
   # 或直接读取仓库下的数据清洗或聚类脚本：
   agent-reach read https://github.com/<owner>/<repo>/blob/main/scripts/processing.R
   ```
3. **成果回流**：将作者清洗好的分期表或降维注释补充纳入“临床表型丰度（维度三）”加分项。
4. **未安装降级**：若未安装 `agent-reach`，仅在打分报告质检卡中附上原始 GitHub 链接，提示用户手动查阅。

---

### 场景 2：深度核验需要下载收费论文全文或补充附表（Paywall）
当 GSE 缺乏详细 Overall Design，但属于 S/A 级潜在优质数据集，需要调阅顶级期刊全文：
1. **联动判定**：检查系统是否存在 `bsk`（BrowserSkill）命令。
2. **存在时触发**：
   ```bash
   bsk open "https://doi.org/<DOI_OR_PUBMED_URL>"
   # 借用日常浏览器已有校园网/机构 VPN 登录态下载包含临床随访信息的 Supplementary Table (Excel)
   ```
3. **成果回流**：解析附件中的真实临床表型（生存时间、药物反应、组织活检病理），补全评分。
4. **未安装降级**：若未安装 `BrowserSkill`，仅依赖 PubMed 开放摘要打分，并在建议项提示“建议使用机构内网核验全文”。

---

### 场景 3：NCBI 触发人机验证（CAPTCHA）或速率限制
当大批量探测元数据被 NCBI Cloudflare 拦截时：
1. **触发 `BrowserSkill` 接管**：
   * 唤起可视化 Agent 窗口加载页面，触发 Human-in-the-Loop 机制。
   * 用户在弹出的日常浏览器窗口中点击完成滑动验证/验证码。
   * Agent 借由验证通过的会话恢复自动化抓取。

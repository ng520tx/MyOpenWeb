---
name: tutorial-doc
description: 续写或修改 doc/ 目录下的《MyOpenWeb 修炼手册》教材（HTML 系列）。当用户要求"续写第 X 章教材"、"新增教材章节"、"修改修炼手册"、"更新 doc 教程"时使用，保证新章节与既有 10 章的设计系统、栏目结构、写作风格完全一致。
---

# MyOpenWeb 修炼手册 · 编写规范

`doc/` 目录是一套面向作者本人（19 年前端/Android 经验，Python/AI 初学）的 AI 应用开发教材，共 `index.html` + `ch01`~`ch10` 十章，纯静态 HTML，双击即开、零 CDN。

## 文件与资产结构

- 每章一个文件：`doc/chNN-slug.html`（如 `ch04-rag.html`）
- 共享资产：`doc/assets/tutorial.css`（设计系统）+ `doc/assets/tutorial.js`（侧栏/主题/高亮器/进度条）
- 新增章节必须同步修改 `tutorial.js` 顶部的 `CHAPTERS` 数组（侧栏与上一章/下一章导航自动生成，无需改任何其他页面）
- 临时截图 `doc/assets/_shot_*.png` 不入库（用后删除）

## 页面骨架（复制任意一章改，不要从零写）

```html
<div class="layout">
  <aside class="sidebar"></aside>          <!-- 空壳，JS 自动填充 -->
  <main class="content"><article class="article">
    <div class="ch-head">…徽章/标题/lede/ch-meta…</div>
    <div class="goals">…学习目标 3-5 条…</div>
    <h2 class="sec-t"><span class="no">SECTION N.1</span>小节标题</h2>
    …正文…
    <div class="iv-zone">…面试卡…</div>
    <div class="recap">…本章小结…</div>
    <div class="ch-nav" data-auto></div>   <!-- 空壳，JS 自动填充 -->
  </article></main>
</div>
<script src="assets/tutorial.js"></script>
```

## 固定栏目顺序（每章必备）

学习目标（goals）→ 若干 SECTION（概念+读代码）→ 动手实验（try-it，可多个穿插）→ 面试官视角（iv-zone）→ 本章小结（recap，"装进口袋的 N 句话"）→ 章间导航。

## 组件速查

| 组件 | 类名 | 用途 |
|---|---|---|
| 前端类比框 | `.analogy`（内含 `.tag` + `<p>`） | 每个新概念都锚定到 React/TS/Android/SQL 已有知识 |
| 坑点警示 | `.pitfall` | 高频错误、与 JS 的差异陷阱 |
| 重点强调 | `.keypoint` | 一句话定义、面试话术、核心公式 |
| 对照表 | `table.cmp-table`（高亮格加 `class="y"`） | TS vs Python、方案对比、trade-off |
| 代码块 | `<pre data-lang="python" data-path="server/services/rag.py（真实代码）">` | JS 自动包装成带头部的高亮块；lang 支持 python/ts/js/kotlin/bash/sql/json |
| 代码解读 | `.code-notes`（紧跟代码块，内放 `<ul>`） | 逐条讲解上方代码的关键行 |
| 动手实验 | `.try-it` | 可直接复制执行的命令（WSL venv 环境） |
| 面试卡 | `details.iv-card`（summary 内 `.q-no` + 问题 + `.chev`） | 折叠问答；`iv-zone` 头部 `.cnt` 由 JS 自动计数 |
| 小结 | `.recap`（`.r-head` + `.r-body ul`） | 每条一句话，加粗关键词 |

## 写作规范（灵魂所在）

1. **类比教学法**：每个新概念第一时间映射到作者已有知识（venv≈node_modules、装饰器≈注解、SSE 服务端≈前端 reader 的对面、向量检索≈ORDER BY score DESC LIMIT k）。
2. **真实代码优先**：读代码栏目必须引用仓库真实文件与真实行为，`data-path` 标注来源并注明"（真实代码）"或"（伪代码）"；引用前先 Read 源文件核实，不允许凭记忆编造。
3. **面试卡三段式**：参考答案（第一人称、结合项目、带具体数字）→ 可选 `.followup`（追问预判）。答案落点永远是"约束决定选型"而非贬低其他方案。
4. **数字锚点**：评测数据引用 `server/eval/results*.md` 的真实数字（如 Hit@1 0.82→0.93→1.00、rerank CPU 5 秒）。
5. **语言**：中文正文，术语首次出现给英文全称；不用 emoji；加粗用于关键结论而非装饰。

## 视觉基调

出版物级阅读体验：暖纸浅色默认（--paper #f7f4ed、松绿主色 #1a6b52、琥珀 #b07c22）+ 深色切换（左下角按钮 / URL 加 `?theme=dark`）。区别于 `docs/architecture.html` 的深色工程风——教材是"手册"，架构页是"档案"。

## 完成后的验证

用无头 Chrome 截图自查（桌面 1440 / 移动 390 / 深色三种形态）：

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --disable-gpu `
  --run-all-compositor-stages-before-draw --hide-scrollbars --virtual-time-budget=6000 `
  --screenshot="doc\assets\_shot.png" --window-size=1440,3000 `
  "file:///d:/ai_one/MyOpenWeb/doc/chNN-xxx.html"
```

检查项：代码高亮生效、表格不溢出、面试卡计数正确、侧栏当前章高亮、上一章/下一章链接正确。截图看完即删。

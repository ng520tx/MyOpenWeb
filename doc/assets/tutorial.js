/* MyOpenWeb 教材共享脚本：侧栏导航生成 / 主题切换 / 语法高亮 / 阅读进度 */
(function () {
  "use strict";

  var CHAPTERS = [
    { file: "index.html", no: "", title: "教材首页 · 学习路线", part: "" },
    { file: "ch01-python.html", no: "01", title: "Python 速成", part: "第一部分 · 基础" },
    { file: "ch02-fastapi.html", no: "02", title: "FastAPI 后端解剖", part: "第一部分 · 基础" },
    { file: "ch03-llm.html", no: "03", title: "LLM 基础与协议归一", part: "第一部分 · 基础" },
    { file: "ch03b-prompt-context.html", no: "03½", title: "Prompt 工程与上下文策略", part: "第一部分 · 基础" },
    { file: "ch04-rag.html", no: "04", title: "RAG 检索增强全链路", part: "第二部分 · 核心原理" },
    { file: "ch05-agent.html", no: "05", title: "Agent 工具调用循环", part: "第二部分 · 核心原理" },
    { file: "ch06-mcp.html", no: "06", title: "MCP 协议与 Server", part: "第二部分 · 核心原理" },
    { file: "ch07-eval.html", no: "07", title: "评测体系与 LLMOps", part: "第三部分 · 工程与进阶" },
    { file: "ch08-engineering.html", no: "08", title: "工程化：测试/CI/部署", part: "第三部分 · 工程与进阶" },
    { file: "ch09-roadmap.html", no: "09", title: "精进路线与生态地图", part: "第三部分 · 工程与进阶" },
    { file: "ch10-interview.html", no: "10", title: "面试通关手册", part: "第三部分 · 工程与进阶" }
  ];

  /* ---------- 主题 ---------- */
  var saved = null;
  try { saved = localStorage.getItem("mow-tutorial-theme"); } catch (e) { /* file:// 某些环境禁用 */ }
  var urlTheme = (location.search.match(/[?&]theme=(dark|light)/) || [])[1];
  if (urlTheme) saved = urlTheme;
  if (saved === "dark") document.documentElement.setAttribute("data-theme", "dark");

  function toggleTheme() {
    var root = document.documentElement;
    var dark = root.getAttribute("data-theme") === "dark";
    if (dark) root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", "dark");
    try { localStorage.setItem("mow-tutorial-theme", dark ? "light" : "dark"); } catch (e) { }
    var btn = document.querySelector(".theme-btn");
    if (btn) btn.textContent = dark ? "☾ 切换深色" : "☀ 切换浅色";
  }

  /* ---------- 侧栏 ---------- */
  function buildSidebar() {
    var host = document.querySelector(".sidebar");
    if (!host) return;
    var current = location.pathname.split("/").pop() || "index.html";
    var html = [
      '<a class="side-brand" href="index.html">',
      '  <span class="mark">敲</span>',
      '  <span><span class="t">MyOpenWeb 修炼手册</span><br><span class="s">AI Application Dev</span></span>',
      "</a>"
    ];
    var lastPart = null;
    CHAPTERS.forEach(function (ch) {
      if (ch.part !== lastPart && ch.part) {
        html.push('<div class="side-sec">' + ch.part + "</div>");
        lastPart = ch.part;
      }
      var cls = "side-link" + (ch.file === current ? " current" : "");
      html.push(
        '<a class="' + cls + '" href="' + ch.file + '">' +
        (ch.no ? '<span class="no">' + ch.no + "</span>" : '<span class="no">☰</span>') +
        "<span>" + ch.title + "</span></a>"
      );
    });
    html.push('<div class="side-foot">');
    html.push('<button class="theme-btn" type="button">☾ 切换深色</button>');
    html.push('<a class="side-gh" href="https://github.com/ng520tx/MyOpenWeb" target="_blank" rel="noopener">github.com/ng520tx/MyOpenWeb</a>');
    html.push("</div>");
    host.innerHTML = html.join("");
    host.querySelector(".theme-btn").addEventListener("click", toggleTheme);
    if (document.documentElement.getAttribute("data-theme") === "dark") {
      host.querySelector(".theme-btn").textContent = "☀ 切换浅色";
    }

    /* 章间导航（页脚上一章/下一章）自动填充 */
    var navHost = document.querySelector(".ch-nav[data-auto]");
    if (navHost) {
      var idx = CHAPTERS.findIndex(function (c) { return c.file === current; });
      var prev = idx > 0 ? CHAPTERS[idx - 1] : null;
      var next = idx >= 0 && idx < CHAPTERS.length - 1 ? CHAPTERS[idx + 1] : null;
      var frag = "";
      frag += prev
        ? '<a class="prev" href="' + prev.file + '"><div class="dir">← 上一章</div><div class="t">' + (prev.no ? prev.no + " · " : "") + prev.title + "</div></a>"
        : '<a class="spacer"></a>';
      frag += next
        ? '<a class="next" href="' + next.file + '"><div class="dir">下一章 →</div><div class="t">' + (next.no ? next.no + " · " : "") + next.title + "</div></a>"
        : '<a class="spacer"></a>';
      navHost.innerHTML = frag;
    }
  }

  /* ---------- 移动端抽屉 ---------- */
  function buildMobileNav() {
    var btn = document.createElement("button");
    btn.className = "menu-btn";
    btn.type = "button";
    btn.innerHTML = "☰";
    var scrim = document.createElement("div");
    scrim.className = "scrim";
    document.body.appendChild(btn);
    document.body.appendChild(scrim);
    var sb = document.querySelector(".sidebar");
    function close() { sb.classList.remove("open"); scrim.classList.remove("show"); }
    btn.addEventListener("click", function () {
      sb.classList.toggle("open");
      scrim.classList.toggle("show");
    });
    scrim.addEventListener("click", close);
    sb.addEventListener("click", function (e) { if (e.target.closest("a")) close(); });
  }

  /* ---------- 阅读进度 ---------- */
  function buildProgress() {
    var bar = document.createElement("div");
    bar.className = "progress";
    bar.innerHTML = "<i></i>";
    document.body.appendChild(bar);
    var fill = bar.firstChild;
    function update() {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      fill.style.width = (h > 0 ? (window.scrollY / h) * 100 : 0) + "%";
    }
    window.addEventListener("scroll", update, { passive: true });
    update();
  }

  /* ---------- 轻量语法高亮 ---------- */
  var LANG_KEYWORDS = {
    python: "def|class|import|from|as|return|if|elif|else|for|while|in|not|and|or|is|None|True|False|try|except|finally|raise|with|async|await|yield|lambda|pass|break|continue|global|nonlocal|assert|del",
    ts: "const|let|var|function|return|if|else|for|while|in|of|new|class|interface|type|extends|implements|import|from|export|default|async|await|yield|try|catch|finally|throw|null|undefined|true|false|this|typeof|instanceof|keyof|as|enum|readonly|static|public|private|protected|void|never|any|unknown|string|number|boolean",
    js: "const|let|var|function|return|if|else|for|while|in|of|new|class|extends|import|from|export|default|async|await|yield|try|catch|finally|throw|null|undefined|true|false|this|typeof|instanceof",
    kotlin: "fun|val|var|class|object|interface|override|private|public|internal|return|if|else|when|for|while|in|is|as|null|true|false|companion|init|constructor|suspend|data|sealed|enum|import|package",
    bash: "cd|ls|echo|export|source|curl|python|python3|pip|docker|git|pnpm|npm|ollama|wsl|sudo|mkdir|rm|cat|grep|tail|head",
    sql: "SELECT|FROM|WHERE|ORDER|BY|LIMIT|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|VIRTUAL|USING|JOIN|ON|AS|AND|OR|NOT|NULL|DESC|ASC|GROUP|MATCH",
    json: ""
  };

  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function highlight(code, lang) {
    /* 单遍 tokenizer：注释/字符串/装饰器/数字/单词 合成一个交替正则，
       按位置顺序扫描输出，天然互斥，避免多轮替换的占位符冲突。 */
    var kwSet = {};
    var kw = LANG_KEYWORDS[lang] || "";
    if (kw) {
      kw.split("|").forEach(function (w) { kwSet[lang === "sql" ? w.toUpperCase() : w] = 1; });
    }
    var comment;
    if (lang === "python" || lang === "bash") comment = "#[^\\n]*";
    else if (lang === "sql") comment = "--[^\\n]*";
    else comment = "\\/\\*[\\s\\S]*?\\*\\/|\\/\\/[^\\n]*";
    var str = "\"\"\"[\\s\\S]*?\"\"\"|'''[\\s\\S]*?'''|\"(?:[^\"\\\\\\n]|\\\\.)*\"|'(?:[^'\\\\\\n]|\\\\.)*'|`(?:[^`\\\\]|\\\\.)*`";
    var deco = "@[\\w.]+";
    var num = "\\b(?:0x[\\da-fA-F]+|\\d+\\.?\\d*)\\b";
    var word = "[A-Za-z_][\\w]*";
    var re = new RegExp("(" + comment + ")|(" + str + ")|(" + deco + ")|(" + num + ")|(" + word + ")", "g");

    var out = "";
    var last = 0;
    var m;
    while ((m = re.exec(code))) {
      out += esc(code.slice(last, m.index));
      var t = m[0];
      if (m[1] !== undefined) {
        out += '<span class="tk-c">' + esc(t) + "</span>";
      } else if (m[2] !== undefined) {
        out += '<span class="tk-s">' + esc(t) + "</span>";
      } else if (m[3] !== undefined) {
        out += (lang === "python" || lang === "kotlin")
          ? '<span class="tk-d">' + esc(t) + "</span>" : esc(t);
      } else if (m[4] !== undefined) {
        out += '<span class="tk-n">' + esc(t) + "</span>";
      } else {
        var key = lang === "sql" ? t.toUpperCase() : t;
        if (kwSet[key]) out += '<span class="tk-k">' + esc(t) + "</span>";
        else if (/^\s*\(/.test(code.slice(re.lastIndex))) out += '<span class="tk-f">' + esc(t) + "</span>";
        else out += esc(t);
      }
      last = re.lastIndex;
    }
    out += esc(code.slice(last));
    return out;
  }

  function buildCodeBlocks() {
    document.querySelectorAll("pre[data-lang]").forEach(function (pre) {
      var lang = pre.getAttribute("data-lang");
      var path = pre.getAttribute("data-path") || "";
      var code = pre.textContent.replace(/^\n+|\s+$/g, "");
      var wrap = document.createElement("div");
      wrap.className = "code-block";
      wrap.innerHTML =
        '<div class="code-head"><span class="dots"><i></i><i></i><i></i></span>' +
        '<span class="path">' + esc(path) + '</span>' +
        '<span class="lang">' + esc(lang) + "</span></div>" +
        '<pre><code>' + highlight(code, lang) + "</code></pre>";
      pre.replaceWith(wrap);
    });
  }

  /* ---------- 面试题计数 ---------- */
  function countInterview() {
    document.querySelectorAll(".iv-zone").forEach(function (zone) {
      var cnt = zone.querySelectorAll(".iv-card").length;
      var el = zone.querySelector(".cnt");
      if (el) el.textContent = cnt + " 题";
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    buildSidebar();
    buildMobileNav();
    buildProgress();
    buildCodeBlocks();
    countInterview();
  });
})();

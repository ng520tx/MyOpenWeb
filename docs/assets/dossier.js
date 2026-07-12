/* MyOpenWeb 工程文档站共享脚本：侧栏/TOC/滚动高亮/代码高亮/进度条/动效 */
(function () {
  "use strict";

  var DOCS = [
    { file: "index.html", no: "", title: "文档中心", sec: "" },
    { file: "architecture.html", no: "D-00", title: "架构展示页（对外档案）", sec: "总览" },
    { file: "project-architecture.html", no: "D-01", title: "项目架构", sec: "工程手册" },
    { file: "rag-agent-copilot.html", no: "D-02", title: "RAG + Agent 模块", sec: "工程手册" },
    { file: "troubleshooting.html", no: "D-03", title: "排障手册", sec: "工程手册" },
    { file: "open-webui-analysis.html", no: "D-04", title: "Open WebUI 对照分析", sec: "研究笔记" },
    { file: "fnm-node-version-management.html", no: "D-05", title: "fnm Node 版本管理", sec: "研究笔记" }
  ];

  /* ---------- 侧栏：站点导航 + 本页 TOC ---------- */
  function buildSidebar() {
    var host = document.querySelector(".sidebar");
    if (!host) return;
    var current = location.pathname.split("/").pop() || "index.html";
    var html = [
      '<a class="side-brand" href="index.html">',
      '  <span class="mark">档</span>',
      '  <span><span class="t">MyOpenWeb 工程文档</span><br><span class="s">Engineering Dossier</span></span>',
      "</a>"
    ];
    var lastSec = null;
    DOCS.forEach(function (d) {
      if (d.sec && d.sec !== lastSec) {
        html.push('<div class="side-sec">' + d.sec + "</div>");
        lastSec = d.sec;
      }
      var cls = "side-link" + (d.file === current ? " current" : "");
      html.push(
        '<a class="' + cls + '" href="' + d.file + '">' +
        '<span class="no">' + (d.no || "☰") + "</span>" +
        "<span>" + d.title + "</span></a>"
      );
      if (d.file === current && d.file !== "index.html") {
        html.push('<nav class="side-toc" data-toc></nav>');
      }
    });
    /* 教材路径：本地仓库在 ../doc/，GitHub Pages 部署在 ../manual/ */
    var manualHref = /github\.io$/.test(location.hostname) ? "../manual/" : "../doc/index.html";
    html.push('<div class="side-foot">');
    html.push('<a href="' + manualHref + '">↗ 修炼手册（教材）</a>');
    html.push('<a href="https://github.com/ng520tx/MyOpenWeb" target="_blank" rel="noopener">↗ github.com/ng520tx/MyOpenWeb</a>');
    html.push("</div>");
    host.innerHTML = html.join("");

    buildToc(host.querySelector("[data-toc]"));
    buildFootNav(current);
  }

  function slug(text, used) {
    var base = text.trim().toLowerCase().replace(/[^\w\u4e00-\u9fa5]+/g, "-").replace(/^-+|-+$/g, "") || "sec";
    var s = base, i = 2;
    while (used[s]) { s = base + "-" + i++; }
    used[s] = 1;
    return s;
  }

  function buildToc(host) {
    if (!host) return;
    var heads = document.querySelectorAll(".article h2");
    if (!heads.length) return;
    var used = {};
    var frag = "";
    heads.forEach(function (h) {
      var no = h.querySelector(".no");
      var label = h.textContent.replace(no ? no.textContent : "", "").trim();
      if (!h.id) h.id = slug(label, used);
      frag += '<a href="#' + h.id + '">' + (no ? '<span class="n">' + no.textContent + "</span>" : "") + label + "</a>";
    });
    host.innerHTML = frag;

    /* scrollspy */
    var links = host.querySelectorAll("a");
    var map = {};
    links.forEach(function (a) { map[a.getAttribute("href").slice(1)] = a; });
    var active = null;
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) {
            if (active) active.classList.remove("on");
            active = map[en.target.id];
            if (active) active.classList.add("on");
          }
        });
      }, { rootMargin: "-8% 0px -78% 0px" });
      heads.forEach(function (h) { io.observe(h); });
    }
  }

  function buildFootNav(current) {
    var navHost = document.querySelector(".doc-foot-nav[data-auto]");
    if (!navHost) return;
    var idx = -1;
    DOCS.forEach(function (d, i) { if (d.file === current) idx = i; });
    var prev = idx > 0 ? DOCS[idx - 1] : null;
    var next = idx >= 0 && idx < DOCS.length - 1 ? DOCS[idx + 1] : null;
    var frag = "";
    frag += prev
      ? '<a class="prev" href="' + prev.file + '"><div class="dir">← 上一篇</div><div class="t">' + (prev.no ? prev.no + " · " : "") + prev.title + "</div></a>"
      : '<a class="spacer"></a>';
    frag += next
      ? '<a class="next" href="' + next.file + '"><div class="dir">下一篇 →</div><div class="t">' + (next.no ? next.no + " · " : "") + next.title + "</div></a>"
      : '<a class="spacer"></a>';
    navHost.innerHTML = frag;
  }

  /* ---------- 小节自动编号（h2 .no 为空则填充） ---------- */
  function numberSections() {
    var heads = document.querySelectorAll(".article h2");
    heads.forEach(function (h, i) {
      var no = h.querySelector(".no");
      if (no && !no.textContent.trim()) {
        no.textContent = (i + 1 < 10 ? "0" : "") + (i + 1);
      }
    });
  }

  /* ---------- 移动端抽屉 ---------- */
  function buildMobileNav() {
    var sb = document.querySelector(".sidebar");
    if (!sb) return;
    var btn = document.createElement("button");
    btn.className = "menu-btn";
    btn.type = "button";
    btn.innerHTML = "☰";
    var scrim = document.createElement("div");
    scrim.className = "scrim";
    document.body.appendChild(btn);
    document.body.appendChild(scrim);
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

  /* ---------- 轻量语法高亮（与教材同一 tokenizer 思路） ---------- */
  var LANG_KEYWORDS = {
    python: "def|class|import|from|as|return|if|elif|else|for|while|in|not|and|or|is|None|True|False|try|except|finally|raise|with|async|await|yield|lambda|pass|break|continue|global|nonlocal|assert|del",
    ts: "const|let|var|function|return|if|else|for|while|in|of|new|class|interface|type|extends|implements|import|from|export|default|async|await|yield|try|catch|finally|throw|null|undefined|true|false|this|typeof|instanceof|keyof|as|enum|readonly|static|public|private|protected|void|never|any|unknown|string|number|boolean",
    js: "const|let|var|function|return|if|else|for|while|in|of|new|class|extends|import|from|export|default|async|await|yield|try|catch|finally|throw|null|undefined|true|false|this|typeof|instanceof",
    kotlin: "fun|val|var|class|object|interface|override|private|public|internal|return|if|else|when|for|while|in|is|as|null|true|false|companion|init|constructor|suspend|data|sealed|enum|import|package",
    bash: "cd|ls|echo|export|source|curl|python|python3|pip|docker|git|pnpm|npm|npx|node|ollama|wsl|sudo|mkdir|rm|cat|grep|tail|head|winget|fnm|nvm|corepack|Get-Command|Remove-Item",
    powershell: "cd|ls|echo|winget|fnm|node|npm|pnpm|corepack|Get-Command|Remove-Item|Set-ExecutionPolicy|netsh|if|else|function|param|return",
    sql: "SELECT|FROM|WHERE|ORDER|BY|LIMIT|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|VIRTUAL|USING|JOIN|ON|AS|AND|OR|NOT|NULL|DESC|ASC|GROUP|MATCH|EXTENSION|INDEX|GENERATED|ALWAYS|STORED",
    json: "",
    yaml: "",
    text: ""
  };

  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function highlight(code, lang) {
    if (lang === "text") return esc(code);
    var kwSet = {};
    var kw = LANG_KEYWORDS[lang] || "";
    if (kw) {
      kw.split("|").forEach(function (w) { kwSet[lang === "sql" ? w.toUpperCase() : w] = 1; });
    }
    var comment;
    if (lang === "python" || lang === "bash" || lang === "powershell" || lang === "yaml") comment = "#[^\\n]*";
    else if (lang === "sql") comment = "--[^\\n]*";
    else comment = "\\/\\*[\\s\\S]*?\\*\\/|\\/\\/[^\\n]*";
    var str = "\"\"\"[\\s\\S]*?\"\"\"|'''[\\s\\S]*?'''|\"(?:[^\"\\\\\\n]|\\\\.)*\"|'(?:[^'\\\\\\n]|\\\\.)*'|`(?:[^`\\\\]|\\\\.)*`";
    var deco = "@[\\w.]+";
    var num = "\\b(?:0x[\\da-fA-F]+|\\d+\\.?\\d*)\\b";
    var word = "[A-Za-z_][\\w-]*";
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
        '<button class="copy" type="button">COPY</button>' +
        '<span class="lang">' + esc(lang) + "</span></div>" +
        '<pre><code>' + highlight(code, lang) + "</code></pre>";
      wrap.querySelector(".copy").addEventListener("click", function () {
        var btn = this;
        function done(ok) {
          btn.textContent = ok ? "COPIED" : "FAILED";
          setTimeout(function () { btn.textContent = "COPY"; }, 1400);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(code).then(function () { done(true); }, function () { done(false); });
        } else { done(false); }
      });
      pre.replaceWith(wrap);
    });
  }

  /* ---------- 表格包裹（横向滚动） ---------- */
  function wrapTables() {
    document.querySelectorAll(".article table").forEach(function (tb) {
      if (tb.parentElement.classList.contains("table-wrap")) return;
      var wrap = document.createElement("div");
      wrap.className = "table-wrap";
      tb.parentNode.insertBefore(wrap, tb);
      wrap.appendChild(tb);
    });
  }

  /* ---------- 滚动 reveal ---------- */
  function buildReveal() {
    var items = document.querySelectorAll(".reveal");
    if (!items.length || !("IntersectionObserver" in window)) {
      items.forEach(function (el) { el.classList.add("in"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, { rootMargin: "0px 0px -6% 0px" });
    items.forEach(function (el) { io.observe(el); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    numberSections();
    buildCodeBlocks();
    wrapTables();
    buildSidebar();
    buildMobileNav();
    buildProgress();
    buildReveal();
  });
})();

/*
 * Render a model reply: Markdown (marked), sanitized (DOMPurify), with LaTeX math (KaTeX).
 *
 * marked treats "\[" and "\(" as escaped brackets and drops the backslash, so math must be
 * taken out before Markdown runs and put back after sanitizing. Code is protected first so
 * that "$" or "\(" inside code is never read as math.
 */
(function (root) {
  "use strict";

  const CODE = /```[\s\S]*?(?:```|$)|`[^`\n]+`/g;
  // Order matters: display forms before inline forms.
  const MATH = [
    { re: /\$\$([\s\S]+?)\$\$/g, display: true },
    { re: /\\\[([\s\S]+?)\\\]/g, display: true },
    { re: /\\\(([\s\S]+?)\\\)/g, display: false },
    // $x$ only when the dollars hug the math and no digit follows, so "$5 and $10" stays text.
    { re: /\$(?=\S)([^$\n]*?\S)\$(?!\d)/g, display: false },
  ];

  function stash(store, prefix, value) {
    store.push(value);
    return prefix + (store.length - 1) + "X";
  }

  function renderMath(tex, display) {
    if (!root.katex) return null;
    try {
      return root.katex.renderToString(tex.trim(), { displayMode: display, throwOnError: false, output: "html" });
    } catch (e) {
      return null;
    }
  }

  function renderRich(raw) {
    const code = [];
    const math = [];
    let text = raw.replace(CODE, (m) => stash(code, "PETALCODE", m));

    MATH.forEach(function (rule) {
      text = text.replace(rule.re, function (whole, tex) {
        const html = renderMath(tex, rule.display);
        if (html === null) return whole;
        const token = stash(math, "PETALMATH", rule.display ? '<div class="math-display">' + html + "</div>" : html);
        // Keep display math in its own paragraph so Markdown does not merge it into text.
        return rule.display ? "\n\n" + token + "\n\n" : token;
      });
    });

    const restore = (store) => (m, i) => (store[Number(i)] === undefined ? m : store[Number(i)]);
    text = text.replace(/PETALCODE(\d+)X/g, restore(code));
    let html = root.DOMPurify.sanitize(root.marked.parse(text));
    // KaTeX output is inserted after sanitizing: KaTeX escapes its input and runs with trust off.
    html = html.replace(/<p>\s*PETALMATH(\d+)X\s*<\/p>/g, restore(math));
    html = html.replace(/PETALMATH(\d+)X/g, restore(math));
    return html;
  }

  root.renderRich = renderRich;
})(window);

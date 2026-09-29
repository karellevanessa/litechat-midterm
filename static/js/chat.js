(function () {
  "use strict";

  const chat = document.getElementById("chat");
  if (!chat) return;
  const messages = document.getElementById("messages");
  const form = document.getElementById("composer");
  const input = document.getElementById("content");
  const sendBtn = document.getElementById("send-btn");
  const csrf = JSON.parse(document.body.getAttribute("hx-headers"))["X-CSRFToken"];

  function renderMarkdown(el, raw) {
    el.dataset.raw = raw;
    el.innerHTML = DOMPurify.sanitize(marked.parse(raw));
  }

  function scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
  }

  function escapeText(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, "<br>");
  }

  function addUserBubble(text) {
    const wrap = document.createElement("div");
    wrap.className = "msg user";
    wrap.innerHTML = '<div class="bubble">' + escapeText(text) + "</div>";
    messages.appendChild(wrap);
  }

  function addAssistantBubble() {
    const wrap = document.createElement("div");
    wrap.className = "msg assistant";
    wrap.innerHTML =
      '<div class="bubble"><button type="button" class="copy-btn" title="Copy" aria-label="Copy">&#128203;</button>' +
      '<div class="md"><span class="typing">Thinking…</span></div></div><div class="meta"></div>';
    messages.appendChild(wrap);
    return { md: wrap.querySelector(".md"), meta: wrap.querySelector(".meta"), bubble: wrap.querySelector(".bubble") };
  }

  function showError(target, text) {
    target.md.innerHTML = "";
    target.bubble.classList.add("error-bubble");
    const p = document.createElement("p");
    p.textContent = text;
    target.md.appendChild(p);
  }

  function setBalance(balance, outOfCredit) {
    const el = document.getElementById("balance");
    if (el) el.textContent = balance;
    const chip = document.getElementById("credit-chip");
    if (chip) chip.classList.toggle("empty", !!outOfCredit);
  }

  function refreshSessions() {
    const list = document.getElementById("session-list");
    if (list && window.htmx) htmx.ajax("GET", list.dataset.url, { target: "#session-list", swap: "innerHTML" });
  }

  async function send(text) {
    const empty = document.getElementById("chat-empty");
    if (empty) empty.remove();
    addUserBubble(text);
    const target = addAssistantBubble();
    scrollToBottom();

    const body = new FormData();
    body.append("content", text);
    let response;
    try {
      response = await fetch(chat.dataset.sendUrl, { method: "POST", body: body, headers: { "X-CSRFToken": csrf } });
    } catch (err) {
      showError(target, "Network error. Please try again.");
      return;
    }
    if (!response.ok) {
      let message = "Something went wrong (" + response.status + ").";
      try { message = (await response.json()).error || message; } catch (e) { /* not JSON */ }
      showError(target, message);
      if (response.status === 402) setBalance(document.getElementById("balance").textContent, true);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let raw = "";
    let pending = false;
    const paint = () => { pending = false; renderMarkdown(target.md, raw); scrollToBottom(); };

    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let nl;
      while ((nl = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (!line) continue;
        const event = JSON.parse(line);
        if (event.type === "delta") {
          raw += event.text;
          if (!pending) { pending = true; requestAnimationFrame(paint); }
        } else if (event.type === "done") {
          renderMarkdown(target.md, raw);
          if (event.empty) target.md.innerHTML = '<p class="muted"><em>The model returned no text.</em></p>';
          target.meta.textContent = event.model + " · " + event.cost;
          setBalance(event.balance, event.out_of_credit);
          refreshSessions();
        } else if (event.type === "error") {
          showError(target, event.message);
        }
      }
    }
    scrollToBottom();
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || sendBtn.disabled) return;
    input.value = "";
    autoGrow();
    sendBtn.disabled = true;
    try { await send(text); } finally { sendBtn.disabled = false; input.focus(); }
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  function autoGrow() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 200) + "px";
  }
  input.addEventListener("input", autoGrow);

  messages.addEventListener("click", function (e) {
    const btn = e.target.closest(".copy-btn");
    if (!btn) return;
    const md = btn.parentElement.querySelector(".md");
    navigator.clipboard.writeText(md.dataset.raw || md.textContent).then(function () {
      btn.textContent = "✓";
      setTimeout(function () { btn.innerHTML = "&#128203;"; }, 1200);
    });
  });

  document.querySelectorAll("#messages .md").forEach(function (el) { renderMarkdown(el, el.textContent); });
  scrollToBottom();
  input.focus();
})();

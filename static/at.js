(() => {
  if (document.__atjs_mo) return;
  document.__atjs_mo = new MutationObserver((recs) => recs.forEach((r) => r.type === "childList" && r.addedNodes.forEach((n) => process(n))));
  let send = (elt, type, detail, bub) => elt.dispatchEvent(new CustomEvent("@:" + type, { detail, cancelable: true, bubbles: bub !== false, composed: true }));
  let attr = (elt, name, defaultVal) => elt.getAttribute(name) || defaultVal;
  let init = (elt) => {
    let options = {};
    if (elt.__atjs || !send(elt, "init", { options })) return;
    elt.__atjs = async (evt) => {
      let reqs = (elt.__atjs.requests ||= new Set());
      let form = elt.form || elt.closest("form");
      let body = new FormData(form ?? undefined, evt.submitter);
      if (!form && elt.name) body.append(elt.name, elt.value);
      let ac = new AbortController();
      let cfg = {
        trigger: evt,
        action: attr(elt, "@action"),
        method: attr(elt, "@method", "GET").toUpperCase(),
        target: document.querySelector(attr(elt, "@target")) ?? elt,
        swap: attr(elt, "@swap", "none"),
        body,
        drop: reqs.size,
        abort: ac.abort.bind(ac),
        signal: ac.signal,
        preventTrigger: true,
        fetch: fetch.bind(window),
      };
      let go = send(elt, "config", { cfg, requests: reqs });
      if (cfg.preventTrigger) evt.preventDefault();
      if (!go || cfg.drop) return;
      if (/GET|DELETE/.test(cfg.method)) {
        let params = new URLSearchParams(cfg.body);
        if (params.size) cfg.action += (/\?/.test(cfg.action) ? "&" : "?") + params;
        cfg.body = null;
      }
      reqs.add(cfg);
      try {
        if (cfg.confirm) {
          let result = await cfg.confirm();
          if (!result) return;
        }
        if (!send(elt, "before", { cfg, requests: reqs })) return;
        cfg.response = await cfg.fetch(cfg.action, cfg);
        cfg.text = await cfg.response.text();
        if (!send(elt, "after", { cfg })) return;
      } catch (error) {
        send(elt, "error", { cfg, error });
        return;
      } finally {
        reqs.delete(cfg);
        send(elt, "finally", { cfg });
      }
      let doSwap = () => {
        if (cfg.swap instanceof Function) return cfg.swap(cfg);
        else if (cfg.swap === "delete") cfg.target.remove();
        else if (/(before|after)(begin|end)/.test(cfg.swap)) cfg.target.insertAdjacentHTML(cfg.swap, cfg.text);
        else if (cfg.swap in cfg.target) cfg.target[cfg.swap] = cfg.text;
        else if (cfg.swap !== "none") throw cfg.swap;
      };
      await doSwap();
      send(elt, "swapped", { cfg });
      if (!document.contains(elt)) send(document, "swapped", { cfg });
    };
    elt.__atjs.evt = attr(elt, "@trigger", elt.matches("form") ? "submit" : elt.matches("input:not([type=button]),select,textarea") ? "change" : "click");
    elt.addEventListener(elt.__atjs.evt, elt.__atjs, options);
    send(elt, "inited", {}, false);
  };
  let process = (n) => {
    if (n.matches && n.matches("[\\@action]")) init(n);
    if (n.querySelectorAll) n.querySelectorAll("[\\@action]").forEach(init);
  };
  document.addEventListener("@:process", (evt) => process(evt.target));
  document.addEventListener("DOMContentLoaded", () => {
    document.__atjs_mo.observe(document.documentElement, { childList: true, subtree: true });
    process(document.body);
  });
})();
// fixi confirmation extension
document.addEventListener("@:config", (evt) => {
  var confirmationMessage = evt.target.getAttribute("@confirm");
  if (confirmationMessage) {
    evt.detail.cfg.confirm = () => confirm(confirmationMessage);
  }
});
document.addEventListener("@:config", (evt) => {
  console.log(evt);
});
document.addEventListener("@:init", (evt) => {
  console.log("init", evt);
});
document.addEventListener("@:inited", (evt) => {
  console.log("inited", evt);
});
document.addEventListener("@:process", (evt) => {
  console.log(evt);
});
document.addEventListener("@:before", (evt) => {
  console.log(evt);
});
document.addEventListener("@:after", (evt) => {
  console.log(evt);
});
document.addEventListener("@:error", (evt) => {
  console.log(evt);
});
document.addEventListener("@:finally", (evt) => {
  console.log(evt);
});
document.addEventListener("@:swapped", (evt) => {
  console.log(evt);
});

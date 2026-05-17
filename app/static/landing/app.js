/**
 * DanfeZap landing — preenche links CTA com o número real do bot,
 * lido do endpoint /api/landing/config.
 */
(function () {
  "use strict";

  const ctas = document.querySelectorAll(".js-cta-bot");
  if (ctas.length === 0) return;

  fetch("/api/landing/config")
    .then(function (r) { return r.json(); })
    .then(function (cfg) {
      const numero = (cfg && cfg.bot_numero) || "";
      if (!numero) return;
      const url = "https://wa.me/" + encodeURIComponent(numero)
                + "?text=" + encodeURIComponent("Olá! Quero usar o DanfeZap.");
      ctas.forEach(function (a) {
        a.setAttribute("href", url);
        a.setAttribute("target", "_blank");
        a.setAttribute("rel", "noopener");
      });
    })
    .catch(function () {
      // Silencioso — o link continua "#" mas a página renderiza.
    });
})();

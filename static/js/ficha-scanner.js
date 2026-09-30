(function () {
  "use strict";

  const AGENT_URL = "http://127.0.0.1:17654";
  const REQUEST_TIMEOUT_MS = 5 * 60 * 1000;

  function setStatus(element, message, kind) {
    element.textContent = message;
    element.classList.remove("text-muted", "text-success", "text-danger", "text-primary");
    element.classList.add(kind || "text-muted");
  }

  async function responseError(response) {
    try {
      const body = await response.json();
      return body.error || "El agente de escaneo devolvió un error.";
    } catch (error) {
      return "El agente de escaneo devolvió un error.";
    }
  }

  function attachPdf(input, blob, filename) {
    const file = new File([blob], filename, {type: "application/pdf", lastModified: Date.now()});
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", {bubbles: true}));
  }

  async function scan(button, input, status) {
    const pagesText = window.prompt("¿Cuántas páginas tiene la ficha firmada?", "1");
    if (pagesText === null) return;

    const pages = Number.parseInt(pagesText, 10);
    if (!Number.isInteger(pages) || pages < 1 || pages > 20) {
      setStatus(status, "Indica entre 1 y 20 páginas.", "text-danger");
      return;
    }

    button.disabled = true;
    setStatus(status, pages === 1 ? "Escaneando…" : `Escaneando ${pages} páginas…`, "text-primary");
    const controller = new AbortController();
    const timeout = window.setTimeout(function () { controller.abort(); }, REQUEST_TIMEOUT_MS);

    try {
      const response = await fetch(`${AGENT_URL}/scan`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({pages: pages}),
        signal: controller.signal
      });
      if (!response.ok) throw new Error(await responseError(response));

      const blob = await response.blob();
      if (blob.type !== "application/pdf" && !blob.type.includes("pdf")) {
        throw new Error("El agente no devolvió un documento PDF.");
      }
      const filename = response.headers.get("X-Scan-Filename") || `ficha-firmada-${Date.now()}.pdf`;
      attachPdf(input, blob, filename);
      setStatus(status, `${pages === 1 ? "Página escaneada" : "Páginas escaneadas"}. Pulsa Guardar.`, "text-success");
    } catch (error) {
      if (error.name === "AbortError") {
        setStatus(status, "El escaneo tardó demasiado y fue cancelado.", "text-danger");
      } else if (error instanceof TypeError) {
        setStatus(status, "Agente no disponible. Inícialo en esta computadora y vuelve a intentar.", "text-danger");
      } else {
        setStatus(status, error.message || "No se pudo completar el escaneo.", "text-danger");
      }
    } finally {
      window.clearTimeout(timeout);
      button.disabled = false;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-ficha-scanner]").forEach(function (container) {
      const button = container.querySelector("[data-scanner-start]");
      const input = container.querySelector("[data-scanner-file-input]");
      const status = container.querySelector("[data-scanner-status]");
      if (!button || !input || !status) return;
      button.addEventListener("click", function () { scan(button, input, status); });
    });
  });
})();

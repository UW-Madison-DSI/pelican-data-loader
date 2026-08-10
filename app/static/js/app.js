// One small progressive enhancement. Everything else is server-rendered.

// Copy the <pre> next to a [data-copy] button.
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;

  const code = button.parentElement?.querySelector("pre code");
  if (!code) return;

  try {
    await navigator.clipboard.writeText(code.innerText);
    const original = button.textContent;
    button.textContent = "Copied";
    setTimeout(() => {
      button.textContent = original;
    }, 1500);
  } catch {
    button.textContent = "Press Ctrl+C";
  }
});

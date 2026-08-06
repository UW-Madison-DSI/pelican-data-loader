// Two small progressive enhancements. Everything else is server-rendered.

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

// Theme toggle. Persisted so a reload does not snap back, and initialised from
// the OS preference on a first visit.
const THEMES = { light: "uwmadison", dark: "uwmadison-dark" };
const STORAGE_KEY = "uwdf-theme";

function applyTheme(mode) {
  document.documentElement.setAttribute("data-theme", THEMES[mode]);
  const icon = document.querySelector("[data-theme-icon]");
  if (icon) icon.textContent = mode === "dark" ? "☽" : "☀";
}

const stored = localStorage.getItem(STORAGE_KEY);
applyTheme(stored || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));

document.addEventListener("click", (event) => {
  if (!event.target.closest("[data-theme-toggle]")) return;
  const next = document.documentElement.getAttribute("data-theme") === THEMES.dark ? "light" : "dark";
  localStorage.setItem(STORAGE_KEY, next);
  applyTheme(next);
});

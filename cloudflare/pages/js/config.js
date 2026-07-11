/* Production Worker URL — edit the line below to point at your own deployed Worker (README Step 3) */
window.JUSTICE_COMPASS_API =
  window.JUSTICE_COMPASS_API ||
  (window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
    ? "http://localhost:8787"
    : "https://justice-compass-api.justicebrobro.workers.dev");

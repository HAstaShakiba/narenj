// The main button downloads for the visitor's system; the GitHub API fills in the newest files.
const platform = /Windows/i.test(navigator.userAgent) ? "windows"
  : /Mac/i.test(navigator.platform || navigator.userAgent) ? "macos"
  : /Linux|X11/i.test(navigator.userAgent) ? "linux" : null;
const button = document.getElementById("download");
const label = document.getElementById("download-label");
const fallback = { windows: button.dataset.windows, macos: button.dataset.macos, linux: "#install" };
const fa = document.documentElement.lang === "fa";
const names = fa
  ? { windows: "دانلود برای ویندوز", macos: "دانلود برای مک", linux: "نصب روی اوبونتو / دبیان" }
  : { windows: "Download for Windows", macos: "Download for macOS", linux: "Install on Ubuntu / Debian" };
if (platform) {
  button.href = fallback[platform];
  label.textContent = names[platform];
  showPanel(platform);
}

(async () => {
  try {
    const res = await fetch("https://api.github.com/repos/HAstaShakiba/narenj/releases/latest");
    if (!res.ok) return;
    const release = await res.json();
    const assets = release.assets || [];
    const find = suffix => assets.find(a => a.name.endsWith(suffix));
    const asset = platform === "windows" ? find("-setup.exe") : platform === "macos" ? find("-macos.dmg") : null;
    if (asset) button.href = asset.browser_download_url;
    const size = asset ? ` · ${Math.round(asset.size / 1048576)} MB` : "";
    document.getElementById("release-meta").textContent =
      `Version ${release.tag_name.replace(/^v/, "")}${size} · MIT license`;
  } catch (e) { /* keep the links built into the page */ }
})();

// Install tabs.
function showPanel(id) {
  for (const tab of document.querySelectorAll(".tab")) {
    tab.setAttribute("aria-selected", String(tab.dataset.panel === id));
  }
  for (const panel of document.querySelectorAll(".panel")) panel.hidden = panel.id !== id;
}
for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => showPanel(tab.dataset.panel));
}

// Copy buttons on code blocks.
for (const pre of document.querySelectorAll("pre")) {
  const copy = document.createElement("button");
  copy.className = "copy";
  const words = fa ? ["کپی", "کپی شد", "انتخاب و کپی کنید"] : ["Copy", "Copied", "Select & copy"];
  copy.textContent = words[0];
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(pre.querySelector("code").innerText.trim());
      copy.textContent = words[1];
      setTimeout(() => (copy.textContent = words[0]), 1500);
    } catch (e) { copy.textContent = words[2]; }
  });
  pre.appendChild(copy);
}

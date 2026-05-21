// ClarityOS desktop — Electron main process.
//
// Spawns one BrowserWindow that loads either the local Vite dev server
// (in development) or the bundled dist/index.html (in production). The
// renderer process is the same React tree that lives under src/, and
// it talks to the existing ClarityOS Cloud Run backend over HTTPS via
// the same /me/threads + /me/vault endpoints the web client uses.
//
// Security:
//   * nodeIntegration=false, contextIsolation=true.
//   * preload.js exposes a narrow IPC surface (no Node primitives leak
//     to the renderer).
//   * devtools opens automatically in dev, never in production.

const { app, BrowserWindow, Menu, shell, ipcMain } = require("electron");
const path = require("node:path");

const IS_DEV = process.env.NODE_ENV === "development";
const DEV_URL = process.env.CLARITYOS_DESKTOP_DEV_URL || "http://localhost:5174";

// Resolve the platform-appropriate icon. macOS uses the .icns bundle
// (electron-builder embeds it during packaging), Windows uses the
// multi-size .ico, Linux uses the 1024 PNG.
function resolveIcon() {
  const dir = path.join(__dirname, "icon");
  if (process.platform === "darwin") return path.join(dir, "icon.icns");
  if (process.platform === "win32")  return path.join(dir, "icon.ico");
  return path.join(dir, "icon.png");
}

let mainWindow = null;

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 720,
    minHeight: 480,
    title: "ClarityOS",
    icon: resolveIcon(),
    backgroundColor: "#04121b",
    show: false,                     // wait for ready-to-show to avoid flash
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      // Allow the renderer to fetch the cloud backend without CORS
      // gymnastics — the renderer runs under file:// in production
      // and the backend is on a different origin.
      webSecurity: true,
    },
  });

  // Defer the first paint so the dark background doesn't flash white.
  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  // External links (target=_blank, mailto:, etc.) open in the OS browser
  // instead of inside the Electron window — keeps the chat surface
  // single-purpose.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://") || url.startsWith("https://")) {
      shell.openExternal(url);
    }
    return { action: "deny" };
  });

  if (IS_DEV) {
    mainWindow.loadURL(DEV_URL);
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(__dirname, "dist", "index.html"));
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// Tighten the default menu so the Cmd/Ctrl+W shortcut closes the
// window cleanly + Cmd/Ctrl+R reloads in dev. In production we strip
// the View menu's "Toggle Developer Tools" entry.
function buildMenu() {
  const isMac = process.platform === "darwin";
  const template = [
    ...(isMac ? [{
      label: app.name,
      submenu: [
        { role: "about" },
        { type: "separator" },
        { role: "services" },
        { type: "separator" },
        { role: "hide" },
        { role: "hideOthers" },
        { role: "unhide" },
        { type: "separator" },
        { role: "quit" },
      ],
    }] : []),
    {
      label: "File",
      submenu: [
        {
          label: "New Thread",
          accelerator: "CmdOrCtrl+N",
          click: () => {
            mainWindow?.webContents.send("clarityos:new-thread");
          },
        },
        { type: "separator" },
        isMac ? { role: "close" } : { role: "quit" },
      ],
    },
    {
      label: "Edit",
      submenu: [
        { role: "undo" }, { role: "redo" }, { type: "separator" },
        { role: "cut" }, { role: "copy" }, { role: "paste" },
        { role: "selectAll" },
      ],
    },
    {
      label: "View",
      submenu: IS_DEV
        ? [
            { role: "reload" },
            { role: "forceReload" },
            { role: "toggleDevTools" },
            { type: "separator" },
            { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" },
          ]
        : [
            { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" },
          ],
    },
    {
      label: "Window",
      submenu: [
        { role: "minimize" }, { role: "zoom" },
        ...(isMac ? [
          { type: "separator" },
          { role: "front" },
        ] : [
          { role: "close" },
        ]),
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// IPC — small surface today. The renderer mostly talks directly to
// the cloud backend over fetch(); IPC is only here so the menu's
// "New Thread" can nudge the renderer.
ipcMain.handle("clarityos:get-platform", () => process.platform);
ipcMain.handle("clarityos:get-version", () => app.getVersion());

app.whenReady().then(() => {
  buildMenu();
  createMainWindow();

  // macOS — re-create the window when the dock icon is clicked while
  // no windows are open (standard Mac behaviour).
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
});

// Quit on all-windows-closed everywhere except macOS, where apps
// typically stay alive in the dock.
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

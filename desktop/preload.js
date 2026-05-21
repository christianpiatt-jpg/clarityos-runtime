// ClarityOS desktop — preload script.
//
// Runs in an isolated world before the renderer's React bundle loads.
// Exposes a narrow IPC surface via contextBridge so the renderer can
// call menu-driven actions ("new thread") and read host metadata
// without ever seeing Node primitives.
//
// All ClarityOS backend traffic goes through plain fetch() in the
// renderer — that's why this surface is tiny on purpose.

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("clarityos", {
  /**
   * Subscribe to the menu's "New Thread" command (Cmd/Ctrl+N).
   * Returns an unsubscribe function so React can detach in cleanup.
   */
  onNewThread: (handler) => {
    const wrapped = (_event) => handler();
    ipcRenderer.on("clarityos:new-thread", wrapped);
    return () => ipcRenderer.removeListener("clarityos:new-thread", wrapped);
  },

  /** Resolve the host platform string. */
  getPlatform: () => ipcRenderer.invoke("clarityos:get-platform"),

  /** App version (from package.json — useful for the about dialog). */
  getVersion: () => ipcRenderer.invoke("clarityos:get-version"),
});

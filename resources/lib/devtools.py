# -*- coding: utf-8 -*-
"""Developer tools for JioTV Direct addon.
Bi-directional file transfer server + real-time log streaming.
Managed by service.py (persistent process) so start/stop actually works."""

from __future__ import unicode_literals

import os
import io
import json
import time
import socket
import cgi
import threading
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingTCPServer
from urllib.parse import urlparse, parse_qs, unquote, quote

import xbmc
import xbmcvfs
import xbmcaddon

DEV_SERVER_PORT = 48997

# ─── Utilities ───────────────────────────────────────────────────────────────

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def find_port(start=DEV_SERVER_PORT, attempts=10):
    for p in range(start, start + attempts):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('', p))
            s.close()
            return p
        except OSError:
            continue
    return start


def _human_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _get_kodi_log_path():
    return xbmcvfs.translatePath("special://logpath/kodi.log")


# ─── Web UI (single self-contained HTML) ─────────────────────────────────────

def _build_web_ui():
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JioTV Dev Tools</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0f0f1a;color:#e0e0e0;min-height:100vh}
.header{background:linear-gradient(135deg,#1a1a3e,#0f3460);padding:16px 24px;display:flex;align-items:center;gap:16px;border-bottom:2px solid #e94560}
.header h1{font-size:20px;color:#fff}.header span{color:#e94560;font-size:14px}
.tabs{display:flex;gap:0;background:#16213e;border-bottom:1px solid #333}
.tab{padding:12px 24px;cursor:pointer;border-bottom:3px solid transparent;color:#888;font-weight:600;transition:.2s}
.tab:hover{color:#ccc}.tab.active{color:#e94560;border-bottom-color:#e94560;background:#1a1a3e}
.content{max-width:1200px;margin:0 auto;padding:20px}
.panel{display:none}.panel.active{display:block}

/* File Manager */
.breadcrumb{display:flex;align-items:center;gap:4px;padding:12px 16px;background:#16213e;border-radius:8px;margin-bottom:16px;flex-wrap:wrap;font-size:14px}
.breadcrumb a{color:#4fc3f7;text-decoration:none;cursor:pointer}.breadcrumb a:hover{text-decoration:underline}
.breadcrumb span{color:#666}
.toolbar{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.btn{padding:8px 16px;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;transition:.2s}
.btn-primary{background:#e94560;color:#fff}.btn-primary:hover{background:#c0392b}
.btn-secondary{background:#2d2d4e;color:#ccc;border:1px solid #444}.btn-secondary:hover{background:#3d3d5e}
.file-list{background:#16213e;border-radius:8px;overflow:hidden}
.file-row{display:flex;align-items:center;padding:10px 16px;border-bottom:1px solid #222;transition:.15s;gap:12px}
.file-row:hover{background:#1e2a45}
.file-icon{font-size:20px;width:28px;text-align:center;flex-shrink:0}
.file-name{flex:1;font-size:14px;word-break:break-all}
.file-name a{color:#e0e0e0;text-decoration:none;cursor:pointer}.file-name a:hover{color:#4fc3f7}
.file-meta{color:#666;font-size:12px;flex-shrink:0;text-align:right;min-width:80px}
.file-actions{display:flex;gap:6px;flex-shrink:0}
.file-actions .btn{padding:4px 10px;font-size:12px}
.upload-zone{border:2px dashed #444;border-radius:8px;padding:32px;text-align:center;color:#666;margin-top:16px;transition:.2s;cursor:pointer}
.upload-zone:hover,.upload-zone.dragover{border-color:#e94560;color:#e94560;background:rgba(233,69,96,0.05)}
.upload-zone input{display:none}

/* Log Viewer */
.log-controls{display:flex;gap:12px;margin-bottom:12px;align-items:center;flex-wrap:wrap}
.log-controls label{color:#888;font-size:13px}
.log-controls input[type=checkbox]{accent-color:#e94560}
.log-controls select,.log-controls input[type=text]{background:#1e2a45;color:#e0e0e0;border:1px solid #444;border-radius:4px;padding:6px 10px;font-size:13px}
#log-output{background:#0a0a14;border:1px solid #222;border-radius:8px;padding:12px;font-family:'Cascadia Code','Fira Code',monospace;font-size:12px;
  line-height:1.6;height:calc(100vh - 240px);overflow-y:auto;white-space:pre-wrap;word-break:break-all}
.log-error{color:#e94560}.log-warning{color:#f39c12}.log-info{color:#2ecc71}.log-debug{color:#888}
.status-dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:6px}
.status-dot.connected{background:#2ecc71;box-shadow:0 0 6px #2ecc71}.status-dot.disconnected{background:#e94560}
</style>
</head>
<body>
<div class="header">
  <h1>🛠 JioTV Dev Tools</h1>
  <span id="host-info"></span>
</div>
<div class="tabs">
  <div class="tab active" onclick="switchTab('files')">📁 File Manager</div>
  <div class="tab" onclick="switchTab('logs')">📋 Live Logs</div>
</div>

<!-- File Manager Panel -->
<div class="content">
<div id="files-panel" class="panel active">
  <div class="breadcrumb" id="breadcrumb"></div>
  <div class="toolbar">
    <button class="btn btn-secondary" onclick="navigateTo(currentPath)">🔄 Refresh</button>
    <button class="btn btn-secondary" onclick="goUp()">⬆ Parent</button>
    <label class="btn btn-primary" style="cursor:pointer">
      ⬆ Upload Files <input type="file" id="file-input" multiple onchange="uploadFiles(this.files)">
    </label>
  </div>
  <div class="file-list" id="file-list"></div>
  <div class="upload-zone" id="drop-zone">
    📂 Drag & drop files here to upload to the current directory
  </div>
</div>

<!-- Log Viewer Panel -->
<div id="logs-panel" class="panel">
  <div class="log-controls">
    <span><span class="status-dot disconnected" id="log-status"></span><span id="log-status-text">Disconnected</span></span>
    <button class="btn btn-primary" id="log-toggle" onclick="toggleLogStream()">▶ Start Streaming</button>
    <button class="btn btn-secondary" onclick="clearLogs()">🗑 Clear</button>
    <label><input type="checkbox" id="auto-scroll" checked> Auto-scroll</label>
    <label>Filter: <input type="text" id="log-filter" placeholder="e.g. JioTV, ERROR" oninput="applyFilter()"></label>
    <label>Level: <select id="log-level" onchange="applyFilter()">
      <option value="all">All</option><option value="error">Errors</option>
      <option value="warning">Warnings+</option><option value="info">Info+</option>
    </select></label>
  </div>
  <div id="log-output"></div>
</div>
</div>

<script>
let currentPath = '';
let logStreaming = false;
let logEventSource = null;
let allLogLines = [];

document.getElementById('host-info').textContent = location.host;

// ─── Tab switching ───
function switchTab(tab) {
  document.querySelectorAll('.tab').forEach((t,i) => t.classList.toggle('active', ['files','logs'][i]===tab));
  document.getElementById('files-panel').classList.toggle('active', tab==='files');
  document.getElementById('logs-panel').classList.toggle('active', tab==='logs');
}

// ─── File Manager ───
async function navigateTo(path) {
  currentPath = path;
  try {
    const resp = await fetch('/api/browse?path=' + encodeURIComponent(path));
    const data = await resp.json();
    renderBreadcrumb(data.path);
    renderFileList(data.entries);
  } catch(e) { console.error(e); }
}

function renderBreadcrumb(path) {
  const bc = document.getElementById('breadcrumb');
  const parts = path.replace(/\\/g,'/').split('/').filter(Boolean);
  let html = '<a onclick="navigateTo(\'\')">🏠 Root</a>';
  let accumulated = '';
  parts.forEach((p,i) => {
    accumulated += p + '/';
    html += ' <span>/</span> <a onclick="navigateTo(\'' + accumulated.replace(/'/g,"\\'") + '\')">' + p + '</a>';
  });
  bc.innerHTML = html;
}

function renderFileList(entries) {
  const list = document.getElementById('file-list');
  if(!entries || entries.length===0){ list.innerHTML='<div class="file-row"><div class="file-name" style="color:#666">Empty directory</div></div>'; return; }
  entries.sort((a,b) => {
    if(a.is_dir && !b.is_dir) return -1;
    if(!a.is_dir && b.is_dir) return 1;
    return a.name.localeCompare(b.name);
  });
  let html = '';
  entries.forEach(e => {
    const icon = e.is_dir ? '📁' : (e.name.match(/\.(zip|gz|tar)$/i) ? '📦' : e.name.match(/\.(py|js|xml|json|html|css)$/i) ? '📄' : '📎');
    const size = e.is_dir ? '' : _humanSize(e.size);
    const dlBtn = e.is_dir ? '' : `<button class="btn btn-secondary" onclick="downloadFile('${(e.full_path||'').replace(/\\/g,'\\\\').replace(/'/g,"\\'")}')">⬇</button>`;
    const clickAction = e.is_dir ? `onclick="navigateTo('${(e.full_path||'').replace(/\\/g,'\\\\').replace(/'/g,"\\'")}')"` : '';
    html += `<div class="file-row">
      <div class="file-icon">${icon}</div>
      <div class="file-name"><a ${clickAction}>${e.name}</a></div>
      <div class="file-meta">${size}</div>
      <div class="file-actions">${dlBtn}</div>
    </div>`;
  });
  list.innerHTML = html;
}

function _humanSize(b) {
  if(b==null) return '';
  for(const u of ['B','KB','MB','GB']){ if(b<1024) return b.toFixed(b<10?1:0)+' '+u; b/=1024; }
  return b.toFixed(1)+' TB';
}

function goUp() {
  let p = currentPath.replace(/\\/g,'/').replace(/\/$/,'');
  const i = p.lastIndexOf('/');
  navigateTo(i > 0 ? p.substring(0, i) : '');
}

function downloadFile(path) {
  window.open('/api/download?path=' + encodeURIComponent(path), '_blank');
}

async function uploadFiles(files) {
  if(!files.length) return;
  const fd = new FormData();
  fd.append('dest', currentPath);
  for(let f of files) fd.append('files', f);
  try {
    const resp = await fetch('/api/upload', {method:'POST', body:fd});
    const r = await resp.json();
    alert(r.message || 'Upload complete');
    navigateTo(currentPath);
  } catch(e) { alert('Upload failed: '+e); }
}

// Drag and drop
const dz = document.getElementById('drop-zone');
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('dragover'); });
dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
dz.addEventListener('drop', e => { e.preventDefault(); dz.classList.remove('dragover'); uploadFiles(e.dataTransfer.files); });

// ─── Log Viewer (SSE) ───
function toggleLogStream() {
  if(logStreaming) stopLogStream(); else startLogStream();
}

function startLogStream() {
  if(logEventSource) logEventSource.close();
  logEventSource = new EventSource('/api/logs/stream');
  logEventSource.onmessage = function(e) {
    allLogLines.push(e.data);
    if(allLogLines.length > 5000) allLogLines = allLogLines.slice(-4000);
    applyFilter();
  };
  logEventSource.onopen = function() {
    logStreaming = true;
    document.getElementById('log-status').className = 'status-dot connected';
    document.getElementById('log-status-text').textContent = 'Streaming';
    document.getElementById('log-toggle').textContent = '⏹ Stop';
  };
  logEventSource.onerror = function() {
    if(logStreaming) {
      document.getElementById('log-status').className = 'status-dot disconnected';
      document.getElementById('log-status-text').textContent = 'Reconnecting...';
    }
  };
}

function stopLogStream() {
  if(logEventSource) { logEventSource.close(); logEventSource = null; }
  logStreaming = false;
  document.getElementById('log-status').className = 'status-dot disconnected';
  document.getElementById('log-status-text').textContent = 'Disconnected';
  document.getElementById('log-toggle').textContent = '▶ Start Streaming';
}

function clearLogs() { allLogLines = []; document.getElementById('log-output').innerHTML = ''; }

function applyFilter() {
  const filter = document.getElementById('log-filter').value.toLowerCase();
  const level = document.getElementById('log-level').value;
  const out = document.getElementById('log-output');
  let html = '';
  allLogLines.forEach(line => {
    const ll = line.toLowerCase();
    if(filter && !ll.includes(filter)) return;
    if(level==='error' && !ll.includes('error')) return;
    if(level==='warning' && !(ll.includes('error')||ll.includes('warning'))) return;
    if(level==='info' && ll.includes('debug:')) return;
    let cls = '';
    if(ll.includes('error')) cls='log-error';
    else if(ll.includes('warning')) cls='log-warning';
    else if(ll.includes('info')) cls='log-info';
    else cls='log-debug';
    html += `<span class="${cls}">${escHtml(line)}</span>\n`;
  });
  out.innerHTML = html;
  if(document.getElementById('auto-scroll').checked) out.scrollTop = out.scrollHeight;
}

function escHtml(t) { return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// Init
navigateTo('');
</script>
</body>
</html>"""


# ─── HTTP Handler ────────────────────────────────────────────────────────────

class DevToolsHandler(BaseHTTPRequestHandler):
    """Handles file browsing, upload, download, and live log streaming."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == '/' or path == '':
            self._serve_html()
        elif path == '/api/browse':
            self._api_browse(params)
        elif path == '/api/download':
            self._api_download(params)
        elif path == '/api/logs/stream':
            self._api_log_stream()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/upload':
            self._api_upload()
        else:
            self.send_error(404)

    # ── Serve web UI ──
    def _serve_html(self):
        html = _build_web_ui().encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    # ── Browse directory ──
    def _api_browse(self, params):
        req_path = params.get('path', [''])[0]

        # Default to common useful roots
        if not req_path:
            roots = self._get_system_roots()
            self._json_response({'path': '', 'entries': roots})
            return

        target = unquote(req_path)
        if not os.path.isdir(target):
            self._json_response({'error': 'Not a directory', 'path': target, 'entries': []}, 400)
            return

        entries = []
        try:
            for name in os.listdir(target):
                full = os.path.join(target, name)
                entry = {'name': name, 'full_path': full, 'is_dir': os.path.isdir(full)}
                if not entry['is_dir']:
                    try:
                        entry['size'] = os.path.getsize(full)
                    except:
                        entry['size'] = 0
                entries.append(entry)
        except PermissionError:
            self._json_response({'error': 'Permission denied', 'path': target, 'entries': []}, 403)
            return

        self._json_response({'path': target, 'entries': entries})

    def _get_system_roots(self):
        """Return useful starting points for browsing."""
        roots = []
        # Kodi special paths
        for label, special in [
            ('Kodi Home', 'special://home/'),
            ('Kodi Addons', 'special://home/addons/'),
            ('Kodi Userdata', 'special://userdata/'),
            ('Kodi Temp', 'special://temp/'),
            ('Kodi Log', 'special://logpath/'),
        ]:
            resolved = xbmcvfs.translatePath(special)
            if os.path.isdir(resolved):
                roots.append({'name': f'{label} → {resolved}', 'full_path': resolved, 'is_dir': True})

        # OS drive roots
        if os.name == 'nt':
            import string
            for d in string.ascii_uppercase:
                dp = f'{d}:\\'
                if os.path.isdir(dp):
                    roots.append({'name': dp, 'full_path': dp, 'is_dir': True})
        else:
            for p in ['/', '/sdcard', '/storage']:
                if os.path.isdir(p):
                    roots.append({'name': p, 'full_path': p, 'is_dir': True})

        return roots

    # ── Download file ──
    def _api_download(self, params):
        filepath = unquote(params.get('path', [''])[0])
        if not filepath or not os.path.isfile(filepath):
            self.send_error(404, 'File not found')
            return

        filename = os.path.basename(filepath)
        try:
            size = os.path.getsize(filepath)
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', str(size))
            self.end_headers()

            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except Exception as e:
            self.send_error(500, str(e))

    # ── Upload files ──
    def _api_upload(self):
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self._json_response({'error': 'Expected multipart/form-data'}, 400)
            return

        # Parse the multipart data
        boundary = content_type.split('boundary=')[-1].encode()
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        # Extract destination path from the form
        dest_path = ''
        files_saved = []

        parts = body.split(b'--' + boundary)
        for part in parts:
            if b'Content-Disposition' not in part:
                continue

            header_end = part.find(b'\r\n\r\n')
            if header_end < 0:
                continue

            header_section = part[:header_end].decode('utf-8', errors='replace')
            file_data = part[header_end + 4:]
            # Strip trailing \r\n--
            if file_data.endswith(b'\r\n'):
                file_data = file_data[:-2]
            if file_data.endswith(b'--'):
                file_data = file_data[:-2]
            if file_data.endswith(b'\r\n'):
                file_data = file_data[:-2]

            if 'name="dest"' in header_section:
                dest_path = file_data.decode('utf-8', errors='replace').strip()
            elif 'name="files"' in header_section:
                # Extract filename
                fn_start = header_section.find('filename="')
                if fn_start < 0:
                    continue
                fn_start += 10
                fn_end = header_section.find('"', fn_start)
                filename = header_section[fn_start:fn_end]

                if not filename:
                    continue

                # Determine save path
                if dest_path and os.path.isdir(dest_path):
                    save_path = os.path.join(dest_path, filename)
                else:
                    # Default to Kodi temp
                    save_path = os.path.join(
                        xbmcvfs.translatePath("special://temp/"),
                        filename
                    )

                try:
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    with open(save_path, 'wb') as f:
                        f.write(file_data)
                    files_saved.append(save_path)
                except Exception as e:
                    files_saved.append(f"FAILED: {filename} ({e})")

        self._json_response({
            'message': f'Uploaded {len(files_saved)} file(s)',
            'files': files_saved
        })

    # ── SSE Log Stream ──
    def _api_log_stream(self):
        """Stream kodi.log using Server-Sent Events (SSE)."""
        log_path = _get_kodi_log_path()

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        try:
            # Start from end of file (don't dump entire history)
            if os.path.isfile(log_path):
                f = open(log_path, 'r', encoding='utf-8', errors='replace')
                f.seek(0, 2)  # Seek to end
            else:
                # Wait for file to appear
                f = None

            while True:
                if f is None:
                    if os.path.isfile(log_path):
                        f = open(log_path, 'r', encoding='utf-8', errors='replace')
                        f.seek(0, 2)
                    else:
                        time.sleep(1)
                        continue

                line = f.readline()
                if line:
                    line = line.rstrip('\n\r')
                    if line:
                        self.wfile.write(f"data: {line}\n\n".encode('utf-8'))
                        self.wfile.flush()
                else:
                    # Check if log was rotated
                    try:
                        current_size = os.path.getsize(log_path)
                        if current_size < f.tell():
                            f.close()
                            f = open(log_path, 'r', encoding='utf-8', errors='replace')
                    except:
                        pass
                    time.sleep(0.3)  # Poll interval

        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # Client disconnected
        except Exception:
            pass
        finally:
            if f:
                try:
                    f.close()
                except:
                    pass

    # ── Helpers ──
    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass


# ─── Server Management (called from service.py) ─────────────────────────────

_dev_server = None
_dev_thread = None
_dev_port = None


def start_server():
    """Start the dev tools server. Returns (ip, port) tuple or None."""
    global _dev_server, _dev_thread, _dev_port

    if _dev_server:
        stop_server()

    port = find_port()
    try:
        _dev_server = ThreadingTCPServer(("", port), DevToolsHandler)
        _dev_server.daemon_threads = True
        _dev_thread = threading.Thread(target=_dev_server.serve_forever)
        _dev_thread.daemon = True
        _dev_thread.start()
        _dev_port = port

        ip = get_local_ip()
        xbmc.log(f"[JioTV-DevTools] Server started at http://{ip}:{port}/", xbmc.LOGINFO)
        return ip, port
    except Exception as e:
        xbmc.log(f"[JioTV-DevTools] Failed to start server: {e}", xbmc.LOGERROR)
        _dev_server = None
        return None


def stop_server():
    """Stop the dev tools server."""
    global _dev_server, _dev_thread, _dev_port

    if _dev_server:
        try:
            _dev_server.shutdown()
            _dev_server.server_close()
        except Exception:
            pass
        _dev_server = None
        _dev_thread = None
        _dev_port = None
        xbmc.log("[JioTV-DevTools] Server stopped", xbmc.LOGINFO)
        return True
    return False


def is_running():
    return _dev_server is not None


def get_url():
    if _dev_server and _dev_port:
        return f"http://{get_local_ip()}:{_dev_port}/"
    return None

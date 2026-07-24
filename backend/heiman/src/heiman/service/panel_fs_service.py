import asyncio
import json
import re
import time
import uuid
import zipfile
from io import BytesIO
from typing import Dict, Optional

import httpx
from loguru import logger

SESSION_TTL_SECONDS = 30 * 60

class PanelFsService:
    def __init__(self):
        self._sessions: Dict[str, dict] = {}

    async def open_session(self, panel_url: str, sync_data: dict = None) -> Dict:
        if not panel_url:
            raise ValueError("缺少 panelUrl")

        logger.info("[PanelFS] Opening session for panel: %s", panel_url[:100])

        session_id = str(uuid.uuid4())
        sync_data = sync_data or {}

        zip_bytes = await self._download_zip(panel_url)
        files = self._extract_zip(zip_bytes)

        entry_url = f"/__panel_fs__/{session_id}/index.html"
        file_count = len(files)

        session = {
            "files": files,
            "sync_data": sync_data,
            "created_at": time.time(),
            "last_accessed": time.time(),
            "timer": None,
        }

        session["timer"] = asyncio.create_task(self._schedule_cleanup(session_id))

        self._sessions[session_id] = session

        logger.info("[PanelFS] Session created: %s, files: %d", session_id, file_count)

        return {
            "sessionId": session_id,
            "entryUrl": entry_url,
            "fileCount": file_count,
        }

    async def close_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False

        if session.get("timer"):
            session["timer"].cancel()

        del self._sessions[session_id]
        logger.info("[PanelFS] Session closed: %s", session_id)
        return True

    BRIDGE_JS_PATH = "__bridge__.js"

    def get_file(self, session_id: str, file_path: str) -> Optional[bytes]:
        session = self._sessions.get(session_id)
        if not session:
            return None

        session["last_accessed"] = time.time()

        file_path = self._normalize_path(file_path)

        if file_path == self.BRIDGE_JS_PATH:
            return self._build_bridge_js(session["sync_data"])

        if file_path == "index.html":
            html_content = session["files"].get("index.html")
            if html_content:
                return self._inject_bridge_js(html_content, session_id)

        return session["files"].get(file_path) or session["files"].get(f"www/{file_path}")

    def get_mime_type(self, file_path: str) -> str:
        ext = file_path.split(".")[-1].lower() if "." in file_path else ""
        mime_map = {
            "html": "text/html; charset=utf-8",
            "htm": "text/html; charset=utf-8",
            "js": "application/javascript; charset=utf-8",
            "css": "text/css; charset=utf-8",
            "json": "application/json",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
            "svg": "image/svg+xml",
            "ico": "image/x-icon",
            "woff": "font/woff",
            "woff2": "font/woff2",
            "ttf": "font/ttf",
            "map": "application/json",
            "txt": "text/plain; charset=utf-8",
        }
        return mime_map.get(ext, "application/octet-stream")

    async def _download_zip(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    def _extract_zip(self, zip_bytes: bytes) -> Dict[str, bytes]:
        files = {}
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if not name.endswith("/"):
                    content = zf.read(name)
                    normalized_name = self._normalize_path(name)
                    files[normalized_name] = content
                    files[name] = content
        return files

    def _normalize_path(self, name: str) -> str:
        return str(name or "").replace("\\", "/").lstrip("./").lstrip("/")

    _CSP_META_RE = re.compile(
        r'<meta\s+[^>]*http-equiv\s*=\s*["\']?Content-Security-Policy["\']?[^>]*/?>',
        re.IGNORECASE,
    )

    def _strip_csp_meta(self, html_str: str) -> str:
        """Remove Content-Security-Policy meta tags so injected inline scripts work."""
        return self._CSP_META_RE.sub("", html_str)

    def _build_bridge_js(self, sync_data: dict) -> bytes:
        """Build the bridge JS as a standalone script file (no inline issues).

        DSBridge protocol (matching Vue reference project webDsBridge.js):
        - iframe -> parent: {{ type:'dsbridge-call', method, params, callbackId }}
        - parent -> iframe: {{ type:'dsbridge-result', callbackId, result }}
        - parent -> iframe push: {{ type:'dsbridge-native', method, args }}
        """
        payload = json.dumps(sync_data or {}, ensure_ascii=False)
        js = f"""/*! panel web bridge */
(function () {{
  var SYNC = {payload};
  window.__PANEL_BRIDGE_SYNC__ = SYNC;
  window.__PANEL_BRIDGE_ORIGIN__ = '*';

  window.addEventListener('message', function (event) {{
    var msg = event.data;
    if (!msg || typeof msg !== 'object') return;

    if (msg.type === 'dsbridge-result' && msg.callbackId) {{
      var cb = window[msg.callbackId];
      if (typeof cb === 'function') {{
        try {{ cb(msg.result); }} catch (e) {{ console.warn('[Bridge] cb error', e); }}
        delete window[msg.callbackId];
      }}
      return;
    }}

    if (msg.type === 'dsbridge-native' && msg.method) {{
      var args = Array.isArray(msg.args) ? msg.args : [];
      if (typeof window._handleMessageFromNative === 'function') {{
        window._handleMessageFromNative({{
          method: msg.method,
          data: JSON.stringify(args),
          callbackId: String(msg.callbackId || Date.now())
        }});
      }} else if (window._dsf && typeof window._dsf[msg.method] === 'function') {{
        window._dsf[msg.method].apply(window._dsf, args);
      }}
    }}
  }});

  window._dsbridge = {{
    call: function (method) {{
      // DSBridge call(method, [args], [callback])
      var cb = null;
      var raw = null;
      var extra = Array.prototype.slice.call(arguments, 1);

      if (extra.length && typeof extra[extra.length - 1] === 'function') {{
        cb = extra.pop();
      }}
      if (extra.length) {{
        raw = extra[0];
      }}

      var params;
      if (raw == null || raw === '') {{
        params = {{}};
      }} else if (typeof raw === 'string') {{
        try {{ params = JSON.parse(raw); }} catch (e) {{ params = raw; }}
      }} else {{
        params = raw;
      }}

      var cid = 'dscb_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      if (cb) {{
        window[cid] = cb;
      }}

      window.parent.postMessage({{
        type: 'dsbridge-call',
        method: method,
        params: params,
        callbackId: cid
      }}, '*');
    }},
    register: function (method, fn) {{
      window._dsf = window._dsf || {{}};
      window._dsf[method] = fn;
    }},
    registerAsyn: function (method, fn) {{
      window._dsf = window._dsf || {{}};
      window._dsf[method] = function () {{
        var args = Array.prototype.slice.call(arguments);
        var callbackId = args.pop();
        fn.apply(null, args.concat([function (ret) {{
          window.parent.postMessage({{
            type: 'dsbridge-result',
            callbackId: callbackId,
            result: ret
          }}, '*');
        }}]));
      }};
    }}
  }};
  window.dsBridge = window._dsbridge;
  window.WebViewJavascriptBridge = window._dsbridge;
}})();
"""
        return js.encode("utf-8")

    def _inject_bridge_js(self, html_content: bytes, _session_id: str) -> bytes:
        """Inject <script src> tag referencing the external bridge file, avoiding CSP inline-script issues."""
        try:
            html_str = html_content.decode("utf-8")
            html_str = self._strip_csp_meta(html_str)

            bridge_tag = f'<script src="./{self.BRIDGE_JS_PATH}"></script>'

            if "</head>" in html_str:
                html_str = html_str.replace("</head>", bridge_tag + "\n</head>")
            elif "<body" in html_str:
                body_match = list(re.finditer(r'<body\b[^>]*>', html_str, re.IGNORECASE))
                if body_match:
                    pos = body_match[0].start()
                    html_str = html_str[:pos] + bridge_tag + "\n" + html_str[pos:]
                else:
                    html_str = bridge_tag + "\n" + html_str
            else:
                html_str = bridge_tag + "\n" + html_str

            return html_str.encode("utf-8")
        except Exception as e:
            logger.error("[PanelFS] Failed to inject bridge tag: %s", e)
            return html_content

    async def _schedule_cleanup(self, session_id: str):
        await asyncio.sleep(SESSION_TTL_SECONDS)
        self.close_session(session_id)

    def cleanup_expired(self):
        now = time.time()
        expired = [sid for sid, sess in self._sessions.items() if now - sess["last_accessed"] > SESSION_TTL_SECONDS]
        for sid in expired:
            self.close_session(sid)
import logging
import socket
import webbrowser
from typing import Optional

from aiohttp import web

from psn.constants import NPSSO_COOKIE_URL, PSN_STORE_URL

logger = logging.getLogger(__name__)

DONE_PATH = "/done"
OPEN_PATH = "/open"

_OPEN_TARGETS = {
    "store": PSN_STORE_URL,
    "npsso": NPSSO_COOKIE_URL,
}

# Galaxy reliably matches navigations to playstation.com (it does NOT hook
# http://127.0.0.1 loopback navigations), so we finish the flow by redirecting
# there. The NPSSO token is captured locally and never placed in this URL.
COMPLETION_URL = "https://www.playstation.com/"
COMPLETION_END_URI_REGEX = r"^https://www\.playstation\.com/"

_FORM_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Connect PlayStation Network</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Segoe UI", system-ui, sans-serif; background: #151515;
         color: #f5f5f5; margin: 0; padding: 16px 18px; line-height: 1.35;
         font-size: 13px; }}
  h2 {{ margin: 0 0 8px; font-size: 18px; }}
  code, kbd {{ background: #2a2a2a; padding: 1px 4px; border-radius: 3px;
              font-family: Consolas, monospace; font-size: 11px; }}
  kbd {{ border: 1px solid #555; }}
  .hint {{ color: #999; font-size: 11px; margin: 0 0 10px; }}
  .field {{ margin-bottom: 10px; }}
  .field-label {{ display: block; margin-bottom: 4px; color: #ddd; }}
  .url-row {{ display: flex; gap: 6px; align-items: center; }}
  .url-row input {{ flex: 1; min-width: 0; margin: 0; padding: 6px 8px;
                    font-family: Consolas, monospace; font-size: 11px;
                    border: 1px solid #444; background: #222; color: #fff;
                    border-radius: 4px; }}
  .action-btn {{ padding: 6px 10px; background: #333; color: #eee;
                 border: 1px solid #555; border-radius: 4px; cursor: pointer;
                 font-size: 11px; line-height: 1; flex-shrink: 0; }}
  .action-btn:hover {{ background: #444; }}
  .action-btn.done {{ background: #1a5c1a; border-color: #2d8a2d; }}
  .open-btn {{ background: #1a3a6e; border-color: #2a5090; }}
  .open-btn:hover {{ background: #234a82; }}
  #npsso {{ width: 100%; padding: 8px; margin: 4px 0 10px; border: 1px solid #444;
            background: #222; color: #fff; border-radius: 4px; font-size: 13px; }}
  button[type="submit"] {{ padding: 8px 18px; background: #00439c; color: #fff;
            border: 0; border-radius: 4px; cursor: pointer; font-size: 13px; }}
  button[type="submit"]:hover {{ background: #0050c0; }}
  .footer {{ margin-top: 8px; margin-bottom: 0; }}
</style>
<script>
var MOD_KEY = /Mac|iPhone|iPad/i.test(navigator.platform || navigator.userAgent)
  ? "\\u2318" : "Ctrl";
function copyText(inputId, buttonId) {{
  var input = document.getElementById(inputId);
  var button = document.getElementById(buttonId);
  input.focus();
  input.select();
  input.setSelectionRange(0, input.value.length);
  var copied = false;
  try {{ copied = document.execCommand("copy"); }} catch (e) {{}}
  if (!copied && navigator.clipboard) {{
    navigator.clipboard.writeText(input.value).then(function() {{
      showDone(button);
    }}).catch(function() {{ showSelectHint(button); }});
    return;
  }}
  if (copied) {{ showDone(button); }} else {{ showSelectHint(button); }}
}}
function showDone(button, label) {{
  var original = button.textContent;
  button.textContent = label || "\\u2713";
  button.classList.add("done");
  setTimeout(function() {{
    button.textContent = original;
    button.classList.remove("done");
  }}, 1200);
}}
function showSelectHint(button) {{
  var original = button.textContent;
  button.textContent = MOD_KEY + "+C";
  setTimeout(function() {{ button.textContent = original; }}, 1500);
}}
function openTarget(target, buttonId) {{
  var button = document.getElementById(buttonId);
  fetch("{open_path}?target=" + encodeURIComponent(target))
    .then(function(resp) {{
      if (resp.ok) {{ showDone(button); }}
      else {{ showDone(button, "!"); }}
    }})
    .catch(function() {{ showDone(button, "!"); }});
}}
document.addEventListener("DOMContentLoaded", function() {{
  var el = document.getElementById("shortcuts");
  if (el) {{
    el.textContent = MOD_KEY + "+C copy, " + MOD_KEY + "+V paste, " + MOD_KEY + "+A select all"
      + " (right-click disabled)";
  }}
}});
</script>
</head>
<body>
  <h2>Connect your PSN account</h2>
  <p class="hint">Use Open to launch your system browser, or Copy and
     <span id="shortcuts"></span>.</p>

  <div class="field">
    <span class="field-label">1. Sign in at</span>
    <div class="url-row">
      <input id="url-store" type="text" readonly value="https://store.playstation.com">
      <button type="button" class="action-btn open-btn" id="open-store"
              onclick="openTarget('store', 'open-store')">Open</button>
      <button type="button" class="action-btn" id="copy-store"
              onclick="copyText('url-store', 'copy-store')">Copy</button>
    </div>
  </div>

  <div class="field">
    <span class="field-label">2. Open NPSSO cookie page, copy <code>npsso</code> from JSON</span>
    <div class="url-row">
      <input id="url-npsso" type="text" readonly
             value="https://ca.account.sony.com/api/v1/ssocookie">
      <button type="button" class="action-btn open-btn" id="open-npsso"
              onclick="openTarget('npsso', 'open-npsso')">Open</button>
      <button type="button" class="action-btn" id="copy-npsso"
              onclick="copyText('url-npsso', 'copy-npsso')">Copy</button>
    </div>
  </div>

  <form action="{done_path}" method="get" autocomplete="off">
    <label class="field-label" for="npsso">3. Paste token (<span id="paste-key"></span>)</label>
    <input id="npsso" name="npsso" type="text" placeholder="64-character token" autofocus>
    <button type="submit">Connect</button>
  </form>
  <p class="hint footer">Token stays on your computer. Served locally by the plugin.</p>
  <script>document.getElementById("paste-key").textContent = MOD_KEY + "+V";</script>
</body>
</html>
"""

_MISSING_TOKEN_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Missing token</title>
<style>body{{font-family:"Segoe UI",system-ui,sans-serif;background:#151515;color:#f5f5f5;
margin:0;padding:28px;}} a{{color:#4ea0ff;}}</style></head>
<body><h2>No token entered</h2>
<p>Please <a href="/">go back</a> and paste your NPSSO token.</p></body></html>
"""


def _find_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


class LocalAuthServer:
    def __init__(self):
        self._runner: Optional[web.AppRunner] = None
        self.port: Optional[int] = None
        self.captured_npsso: Optional[str] = None

    async def start(self) -> int:
        if self._runner is not None:
            return self.port

        self.captured_npsso = None
        app = web.Application()
        app.router.add_get("/", self._handle_form)
        app.router.add_get(DONE_PATH, self._handle_done)
        app.router.add_get(OPEN_PATH, self._handle_open)

        self._runner = web.AppRunner(app)
        await self._runner.setup()

        self.port = _find_free_port()
        site = web.TCPSite(self._runner, "127.0.0.1", self.port)
        await site.start()
        logger.info("Local PSN auth server listening on 127.0.0.1:%s", self.port)
        return self.port

    async def stop(self):
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self.port = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    @property
    def end_uri_regex(self) -> str:
        return COMPLETION_END_URI_REGEX

    async def _handle_form(self, _request):
        return web.Response(
            text=_FORM_HTML.format(done_path=DONE_PATH, open_path=OPEN_PATH),
            content_type="text/html",
        )

    async def _handle_open(self, request):
        target = (request.query.get("target") or "").strip().lower()
        url = _OPEN_TARGETS.get(target)
        if not url:
            return web.Response(status=400, text="Unknown target")
        logger.info("Opening system browser for PSN auth target=%s", target)
        webbrowser.open(url)
        return web.Response(status=204)

    async def _handle_done(self, request):
        token = (request.query.get("npsso") or "").strip()
        if not token:
            return web.Response(
                text=_MISSING_TOKEN_HTML, content_type="text/html", status=400
            )
        self.captured_npsso = token
        logger.info("Captured NPSSO token from local form; redirecting to complete auth")
        # Redirect to a URL Galaxy will match so it calls pass_login_credentials.
        raise web.HTTPFound(COMPLETION_URL)

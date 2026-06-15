from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def fetch_html_with_chrome_cdp(url: str, *, timeout: int = 30) -> str:
    chrome_path = find_chrome_path()
    if not chrome_path:
        raise RuntimeError("Google Chrome executable was not found.")
    node_path = shutil.which("node")
    if not node_path:
        raise RuntimeError("Node.js executable was not found.")

    script_path = Path(tempfile.mkdtemp(prefix="trial-registry-cdp-script-")) / "fetch.js"
    script_path.write_text(CHROME_CDP_FETCH_SCRIPT, encoding="utf-8")
    try:
        completed = subprocess.run(
            [node_path, str(script_path), chrome_path, url, str(timeout)],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout + 10,
        )
    finally:
        shutil.rmtree(script_path.parent, ignore_errors=True)

    if not completed.stdout.strip():
        error = completed.stderr.strip() or f"Chrome CDP fetch exited with code {completed.returncode}."
        raise RuntimeError(error)
    payload = json.loads(completed.stdout)
    if not payload.get("ok"):
        raise RuntimeError(str(payload.get("error") or "Chrome CDP fetch failed."))
    html = payload.get("html")
    if not isinstance(html, str) or not html:
        raise RuntimeError("Chrome CDP fetch returned empty HTML.")
    return html


def find_chrome_path() -> str:
    candidates = [
        os.environ.get("TRIAL_REGISTRY_CHROME_PATH", ""),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
        shutil.which("chromium-browser") or "",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return ""


def chrome_cdp_enabled() -> bool:
    value = os.environ.get("TRIAL_REGISTRY_ENABLE_CHROME_CDP", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


CHROME_CDP_FETCH_SCRIPT = r"""
const {spawn} = require('node:child_process');
const http = require('node:http');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const chromePath = process.argv[2];
const targetUrl = process.argv[3];
const timeoutSeconds = Number(process.argv[4] || 30);
const port = 9300 + Math.floor(Math.random() * 1000);
const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'trial-registry-cdp-'));
let proc;

function output(payload) {
  process.stdout.write(JSON.stringify(payload));
}

function cleanup() {
  if (proc) {
    try { proc.kill('SIGTERM'); } catch (_) {}
  }
  try { fs.rmSync(userData, { recursive: true, force: true }); } catch (_) {}
}

function requestJson(pathname, method='GET') {
  return new Promise((resolve, reject) => {
    const req = http.request(
      { host: '127.0.0.1', port, path: pathname, method, headers: { 'Content-Length': 0 } },
      (res) => {
        let body = '';
        res.on('data', (chunk) => body += chunk);
        res.on('end', () => {
          try { resolve(JSON.parse(body)); }
          catch (_) { reject(new Error(body.slice(0, 200))); }
        });
      }
    );
    req.on('error', reject);
    req.end();
  });
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let nextId = 1;
  const pending = new Map();
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      pending.get(message.id)(message);
      pending.delete(message.id);
    }
  };
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });
  return {
    ws,
    send(method, params={}) {
      const id = nextId++;
      ws.send(JSON.stringify({ id, method, params }));
      return new Promise((resolve) => pending.set(id, resolve));
    }
  };
}

async function main() {
  proc = spawn(chromePath, [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userData}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-background-networking',
    '--disable-extensions',
    targetUrl,
  ], { stdio: 'ignore' });

  const deadline = Date.now() + timeoutSeconds * 1000;
  let tabs = [];
  while (Date.now() < deadline) {
    try {
      tabs = await requestJson('/json');
      if (tabs.length) break;
    } catch (_) {}
    await wait(250);
  }
  const target = tabs.find((tab) => (tab.url || '').includes(new URL(targetUrl).hostname)) || tabs[0];
  if (!target || !target.webSocketDebuggerUrl) {
    throw new Error('Chrome CDP target was not available.');
  }

  const cdp = await connect(target.webSocketDebuggerUrl);
  await cdp.send('Runtime.enable');
  await cdp.send('Page.enable');

  let result = null;
  while (Date.now() < deadline) {
    await wait(1000);
    const evalResult = await cdp.send('Runtime.evaluate', {
      expression: `JSON.stringify({title: document.title, text: document.body ? document.body.innerText : '', html: document.documentElement ? document.documentElement.outerHTML : ''})`,
      returnByValue: true,
    });
    const value = evalResult?.result?.result?.value;
    if (value) {
      result = JSON.parse(value);
      if (result.html && result.html.length > 1000 && result.text) {
        break;
      }
    }
  }
  cdp.ws.close();
  if (!result || !result.html) {
    throw new Error('Chrome CDP did not return page HTML.');
  }
  output({ ok: true, html: result.html, title: result.title || '' });
}

main()
  .catch((error) => {
    output({ ok: false, error: String(error && error.message ? error.message : error) });
    process.exitCode = 1;
  })
  .finally(cleanup);
"""

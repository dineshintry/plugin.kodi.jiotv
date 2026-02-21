# -*- coding: utf-8 -*-

import socket
import threading
from socketserver import ThreadingTCPServer

from codequick import Script
from codequick.script import Settings
from kodi_six import xbmcgui
from xbmc import Monitor, executebuiltin

from resources.lib import proxy


def serveForever(handler):
    try:
        handler.serve_forever()
    except Exception as e:
        Script.log(f"Service error: {e}", lvl=Script.ERROR)


def find_available_port(start_port=48996, max_attempts=10):
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('', port))
            sock.close()
            return port
        except OSError:
            continue
    return start_port  # Fallback to original port


# Find available port to avoid conflicts
_PORT = find_available_port()
Script.log(f"Starting JioTV proxy on port: {_PORT}", lvl=Script.INFO)

try:
    handler = ThreadingTCPServer(("", _PORT), proxy.JioTVProxy)
    t = threading.Thread(target=serveForever, args=(handler,))
    t.setDaemon(True)
    t.start()
    Script.log("JioTV proxy service started successfully", lvl=Script.INFO)
except Exception as e:
    Script.log(f"Failed to start JioTV proxy service: {e}", lvl=Script.ERROR)

# if not Settings.get_boolean("popup"):
#     xbmcgui.Dialog().ok("JioTV Notification",
#                         "Custom JioTV Add-on")

if Settings.get_boolean("m3ugen"):
    executebuiltin(
        "RunPlugin(plugin://plugin.kodi.jiotv/resources/lib/main/m3ugen/?notify=no)"
    )

monitor = Monitor()
while not monitor.abortRequested():
    if monitor.waitForAbort(10):
        handler.shutdown()
        handler.server_close()
        break

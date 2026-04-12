# -*- coding: utf-8 -*-

import socket
import threading
from socketserver import ThreadingTCPServer

from codequick import Script
from codequick.script import Settings
from kodi_six import xbmcgui
from xbmc import Monitor, executebuiltin
from xbmcaddon import Addon

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


# ─── JioTV Proxy (always running) ───────────────────────────────────────────

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

if Settings.get_boolean("m3ugen"):
    executebuiltin(
        "RunPlugin(plugin://plugin.kodi.jiotv/resources/lib/main/m3ugen/?notify=no)"
    )

# ─── Pre-warm TLS connections ────────────────────────────────────────────────
# On Android TV via mobile hotspot, initial TLS handshakes can take 15+ seconds.
# Pre-warming establishes the TLS session on startup so playback is fast.
def _prewarm_tls():
    try:
        from resources.lib.utils import get_session
        session = get_session()
        session.head("https://jiotvapi.media.jio.com/", timeout=(15, 5))
        Script.log("[PREWARM] TLS connection to jiotvapi.media.jio.com established", lvl=Script.INFO)
    except Exception as e:
        Script.log(f"[PREWARM] TLS pre-warm failed (non-critical): {e}", lvl=Script.INFO)

_prewarm_thread = threading.Thread(target=_prewarm_tls)
_prewarm_thread.daemon = True
_prewarm_thread.start()

# ─── Environment Network Patch ──────────────────────────────────────────────
# Android Mobile Hotspots frequently broadcast broken IPv6 routes, causing
# inputstream.adaptive (which uses Kodi's native Curl without Python's patches)
# to constantly timeout and fail. We bypass this entirely by globally disabling
# IPv6 inside Kodi's advancedsettings.xml file.
def _apply_ipv6_hotspot_patch():
    try:
        from xbmc import translatePath
        import xml.etree.ElementTree as ET
        import os
        
        # Use py3 / kodi v19+ translatePath correctly
        try:
            from xbmcvfs import translatePath
        except ImportError:
            pass
            
        adv_path = translatePath("special://masterprofile/advancedsettings.xml")
        modified = False
        
        if os.path.exists(adv_path):
            try:
                tree = ET.parse(adv_path)
                root = tree.getroot()
            except Exception:
                root = ET.Element("advancedsettings")
                tree = ET.ElementTree(root)
        else:
            root = ET.Element("advancedsettings")
            tree = ET.ElementTree(root)
            
        network = root.find("network")
        if network is None:
            network = ET.SubElement(root, "network")
            
        disableipv6 = network.find("disableipv6")
        if disableipv6 is None:
            disableipv6 = ET.SubElement(network, "disableipv6")
            disableipv6.text = "true"
            modified = True
        elif disableipv6.text != "true":
            disableipv6.text = "true"
            modified = True
            
        if modified:
            try:
                tree.write(adv_path, encoding="utf-8", xml_declaration=True)
                Script.log("[HOTSPOT PATCH] Successfully applied <disableipv6> to advancedsettings.xml.", lvl=Script.INFO)
                Script.notify("JioTV Restart Required", "Hotspot Network Optimizer applied. Please RESTART Kodi.")
            except Exception as e:
                Script.log(f"[HOTSPOT PATCH] Failed to write advancedsettings.xml: {e}", lvl=Script.WARNING)
    except Exception as e:
        Script.log(f"[HOTSPOT PATCH] Critical error writing advancedsettings: {e}", lvl=Script.ERROR)

# Run patch check async so it doesn't block startup
_patch_thread = threading.Thread(target=_apply_ipv6_hotspot_patch)
_patch_thread.daemon = True
_patch_thread.start()

# ─── Dev Tools Server (toggled via settings) ────────────────────────────────

_dev_server_running = False


def _check_dev_server():
    """Start or stop dev server based on the devserver_enabled setting."""
    global _dev_server_running
    from resources.lib.constants import DEV_MODE

    if not DEV_MODE:
        return

    try:
        enabled = Addon().getSetting("devserver_enabled") == "true"
    except Exception:
        enabled = False

    from resources.lib import devtools

    if enabled and not devtools.is_running():
        result = devtools.start_server()
        if result:
            ip, port = result
            _dev_server_running = True
            Script.log(f"[DEV] Dev server started at http://{ip}:{port}/", lvl=Script.INFO)

    elif not enabled and devtools.is_running():
        devtools.stop_server()
        _dev_server_running = False
        Script.log("[DEV] Dev server stopped", lvl=Script.INFO)


# Check on startup
_check_dev_server()


# ─── Main Loop ──────────────────────────────────────────────────────────────

class ServiceMonitor(Monitor):
    def onSettingsChanged(self):
        """Called by Kodi when any addon setting changes."""
        _check_dev_server()


monitor = ServiceMonitor()
while not monitor.abortRequested():
    if monitor.waitForAbort(1):
        handler.shutdown()
        handler.server_close()
        # Also stop dev server on exit
        try:
            from resources.lib import devtools
            devtools.stop_server()
        except Exception:
            pass
        break

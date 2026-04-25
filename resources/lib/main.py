# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from codequick import run

# Import modules to register routes
from resources.lib.recorder import record_live_stream, download_vod as _recorder_download_vod, download_vod_fast as _recorder_download_vod_fast, download_vod_superfast as _recorder_download_vod_superfast
from resources.lib.vod import (
    show_featured,
    show_vod,
    show_vod_category,
    show_vod_channels,
    show_vod_channels_by_language,
    show_vod_channel_content,
)
from resources.lib.menu import root, show_listby, show_category, show_epg
from resources.lib.player import play as player_play
from resources.lib.auth import login, logout, setmobile, applyall
from resources.lib.pvr import m3ugen as pvr_m3ugen, epg_setup, pvrsetup, cleanup

# Compatibility routes for old M3Us and settings
from codequick import Route, Resolver, Script

@Route.register
def root(*args, **kwargs):
    from resources.lib.menu import root as _root
    return _root(*args, **kwargs)

@Resolver.register
def play(*args, **kwargs):
    return player_play(*args, **kwargs)

@Script.register
def m3ugen(*args, **kwargs):
    return pvr_m3ugen(*args, **kwargs)

@Script.register
def login(*args, **kwargs):
    from resources.lib.auth import login as _login
    return _login(*args, **kwargs)

@Script.register
def logout(*args, **kwargs):
    from resources.lib.auth import logout as _logout
    return _logout(*args, **kwargs)

@Script.register
def pvrsetup(*args, **kwargs):
    from resources.lib.pvr import pvrsetup as _pvrsetup
    return _pvrsetup(*args, **kwargs)

@Script.register
def applyall(*args, **kwargs):
    from resources.lib.auth import applyall as _applyall
    return _applyall(*args, **kwargs)

@Script.register
def setmobile(*args, **kwargs):
    from resources.lib.auth import setmobile as _setmobile
    return _setmobile(*args, **kwargs)

@Script.register
def download_vod(*args, **kwargs):
    from resources.lib.recorder import download_vod as _download_vod
    return _download_vod(*args, **kwargs)

@Script.register
def download_vod_fast(*args, **kwargs):
    from resources.lib.recorder import download_vod_fast as _download_vod_fast
    return _download_vod_fast(*args, **kwargs)

@Script.register
def download_vod_superfast(*args, **kwargs):
    from resources.lib.recorder import download_vod_superfast as _download_vod_superfast
    return _download_vod_superfast(*args, **kwargs)

@Script.register
def backupsettings(*args, **kwargs):
    from resources.lib.utils import backupSettings
    backupSettings()
    from codequick import Script
    Script.notify("JioTV", "Account data backed up")

@Script.register
def restoresettings(*args, **kwargs):
    from resources.lib.utils import restoreSettings
    restoreSettings()
    from codequick import Script
    Script.notify("JioTV", "Account data restored")


@Script.register
def backupfavourites(*args, **kwargs):
    from resources.lib.utils import backupFavourites
    backupFavourites()

@Script.register
def restorefavourites(*args, **kwargs):
    from resources.lib.utils import restoreFavourites
    restoreFavourites()

@Script.register
def sharefavourites(*args, **kwargs):
    from resources.lib.utils import shareFavourites
    shareFavourites()

@Script.register
def importfavourites(*args, **kwargs):
    from resources.lib.utils import importFavourites
    importFavourites()

@Script.register
def cleanup(*args, **kwargs):
    from resources.lib.pvr import cleanup as _cleanup
    return _cleanup(*args, **kwargs)

@Script.register
def record_live_stream(*args, **kwargs):
    from resources.lib.recorder import record_live_stream as _record
    return _record(*args, **kwargs)

@Script.register
def start_dev_server(*args, **kwargs):
    from xbmcaddon import Addon
    import xbmcgui
    addon = Addon()
    addon.setSetting("devserver_enabled", "true")
    # Give service.py a moment to start the server
    import xbmc
    xbmc.sleep(1500)
    from resources.lib.devtools import get_local_ip
    port = 48997  # Default port
    ip = get_local_ip()
    url = f"http://{ip}:{port}/"
    xbmcgui.Dialog().ok(
        "Dev Tools Server",
        f"Server is starting at:\n\n[B]{url}[/B]\n\n"
        f"Open this URL in your laptop/phone browser.\n"
        f"• File Manager: browse, upload, download files\n"
        f"• Live Logs: stream Kodi logs in real-time"
    )

@Script.register
def stop_dev_server(*args, **kwargs):
    from xbmcaddon import Addon
    addon = Addon()
    addon.setSetting("devserver_enabled", "false")
    from codequick import Script as S
    S.notify("Dev Tools", "Server stopped")

@Script.register
def toggle_debug(*args, **kwargs):
    import xbmc
    import json
    from codequick import Script as S
    # Read current debug state
    payload = {"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue",
               "params": {"setting": "debug.showloginfo"}}
    result = json.loads(xbmc.executeJSONRPC(json.dumps(payload)))
    current = result.get("result", {}).get("value", False)
    new_val = not current
    payload = {"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue",
               "params": {"setting": "debug.showloginfo", "value": new_val}}
    xbmc.executeJSONRPC(json.dumps(payload))
    state = "ON" if new_val else "OFF"
    S.notify("Debug Logging", f"Kodi debug logging: {state}")

@Script.register
def copy_log(*args, **kwargs):
    import xbmcvfs
    from xbmcgui import Dialog
    from codequick import Script as S
    
    # Locate the log file
    log_file = xbmcvfs.translatePath("special://logpath/kodi.log")
    if not xbmcvfs.exists(log_file):
        S.notify("Error", "kodi.log not found.")
        return
        
    dialog = Dialog()
    dest_dir = dialog.browse(3, "Select folder to export kodi.log", "files")
    if dest_dir:
        # Construct path keeping Kodi VFS compatibility in mind
        if not dest_dir.endswith('/') and not dest_dir.endswith('\\'):
            dest_dir += '/'
        dest = dest_dir + "kodi.log"
        try:
            if xbmcvfs.exists(dest):
                xbmcvfs.delete(dest)
            xbmcvfs.copy(log_file, dest)
            S.notify("Success", "kodi.log copied successfully")
        except Exception as e:
            S.log(f"Failed to copy kodi.log: {e}", lvl=S.ERROR)
            S.notify("Error", "Failed to copy kodi.log")

if __name__ == "__main__":
    run()

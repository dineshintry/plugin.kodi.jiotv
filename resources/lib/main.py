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

if __name__ == "__main__":
    run()

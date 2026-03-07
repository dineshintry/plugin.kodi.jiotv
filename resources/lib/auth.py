# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from time import sleep
from codequick import Script
from codequick.script import Settings
from codequick.storage import PersistentDict
from codequick.utils import keyboard
from xbmcgui import Dialog, DialogProgress
from resources.lib.constants import ADDON, ADDON_ID
from resources.lib.utils import (
    sendOTPV2,
    login as ULogin,
    logout as ULogout,
    get_local_ip,
    kodi_rpc,
    Monitor,
)

monitor = Monitor()

@Script.register
def login(plugin):
    method = Dialog().yesno(
        "Login", "Select Login Method", yeslabel="Keyboard", nolabel="WEB"
    )
    if method == 1:
        login_type = Dialog().yesno(
            "Login", "Select Login Type", yeslabel="OTP", nolabel="Password"
        )
        if login_type == 1:
            mobile = Settings.get_string("mobile")
            if not mobile or (len(mobile) != 10):
                mobile = Dialog().numeric(0, "Enter your Jio mobile number")
                ADDON.setSetting("mobile", mobile)
            error = sendOTPV2(mobile)
            if error:
                Script.notify("Login Error", error)
                return
            otp = Dialog().numeric(0, "Enter OTP")
            ULogin(mobile, otp, mode="otp")
        elif login_type == 0:
            username = keyboard("Enter your Jio mobile number or email")
            password = keyboard("Enter your password", hidden=True)
            ULogin(username, password)
    elif method == 0:
        pDialog = DialogProgress()
        pDialog.create(
            "JioTV", "Visit [B]http://%s:48996/[/B] to login" % get_local_ip()
        )
        for i in range(120):
            sleep(1)
            with PersistentDict("headers") as db:
                headers = db.get("headers")
            if headers or pDialog.iscanceled():
                break
            pDialog.update(i)
        pDialog.close()


@Script.register
def setmobile(plugin):
    prevMobile = Settings.get_string("mobile")
    mobile = Dialog().numeric(0, "Update Jio mobile number", prevMobile)
    kodi_rpc("Addons.SetAddonEnabled", {"addonid": ADDON_ID, "enabled": False})
    ADDON.setSetting("mobile", mobile)
    kodi_rpc("Addons.SetAddonEnabled", {"addonid": ADDON_ID, "enabled": True})
    monitor.waitForAbort(1)
    Script.notify("Jio number set", "")


@Script.register
def applyall(plugin):
    kodi_rpc("Addons.SetAddonEnabled", {"addonid": ADDON_ID, "enabled": False})
    monitor.waitForAbort(1)
    kodi_rpc("Addons.SetAddonEnabled", {"addonid": ADDON_ID, "enabled": True})
    monitor.waitForAbort(1)
    Script.notify("All settings applied", "")


@Script.register
def logout(plugin):
    ULogout()

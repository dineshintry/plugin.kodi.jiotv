# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import gzip
import requests
import urlquick
import xml.etree.ElementTree as ET
from codequick import Script
from codequick.script import Settings
from xbmc import executebuiltin
from xbmcaddon import Addon
from xbmcgui import DialogProgress
from resources.lib.constants import (
    EPG_SRC,
    PLAY_URL,
    M3U_CHANNEL,
    IMG_CATCHUP,
    M3U_SRC,
    EPG_PATH,
)
from resources.lib.utils import (
    getCachedChannels,
    getCachedDictionary,
    check_addon,
    _setup,
    cleanLocalCache,
)

@Script.register
def m3ugen(plugin, notify="yes"):
    channels = getCachedChannels()
    if not channels:
        if notify == "yes":
            Script.notify("JioTV", "Error: Unable to load channel list. Check your connection.")
        return
        
    dictionary = getCachedDictionary()
    if not dictionary:
        if notify == "yes":
            Script.notify("JioTV", "Error: Unable to load channel dictionary.")
        return
        
    GENRE_MAP = dictionary.get("channelCategoryMapping")
    LANG_MAP = dictionary.get("languageIdMapping")

    m3ustr = '#EXTM3U x-tvg-url="%s"\n' % EPG_SRC

    for i, channel in enumerate(channels):
        channel_id = int(channel.get("channel_id"))
        
        if 5000 <= channel_id <= 5022:
            continue

        if str(channel.get("channelLanguageId")) not in LANG_MAP.keys():
            lang = "Extra"
        else:
            lang = LANG_MAP[str(channel.get("channelLanguageId"))]

        if str(channel.get("channelCategoryId")) not in GENRE_MAP.keys():
            genre = "Extragenre"
        else:
            genre = GENRE_MAP[str(channel.get("channelCategoryId"))]

        if not Settings.get_boolean(lang):
            continue

        group = lang + ";" + genre
        _play_url = PLAY_URL + "channel_id={0}".format(channel_id)

        catchup = ""
        if channel.get("isCatchupAvailable"):
            catchup = ' catchup="vod" catchup-source="{0}channel_id={1}&showtime={{H}}{{M}}{{S}}&srno={{Y}}{{m}}{{d}}&programId={{catchup-id}}" catchup-days="7"'.format(
                PLAY_URL, channel_id
            )

        m3ustr += M3U_CHANNEL.format(
            tvg_id=channel_id,
            channel_name=channel.get("channel_name"),
            group_title=group,
            tvg_chno=int(channel.get("channel_order", i)) + 1,
            tvg_logo=IMG_CATCHUP + channel.get("logoUrl", ""),
            catchup=catchup,
            play_url=_play_url,
        )

    zee_channels = [
            {"@id": "5016", "display-name": "Zee Anmol Cinema", "icon": {"@src": "https://akamaividz2.zee5.com/image/upload/w_396,h_224,c_scale,f_webp,q_auto:eco/resources/0-9-zeeanmol/cover/1920x77021724318"}},
            {"@id": "5017", "display-name": "Zee Action", "icon": {"@src": "https://akamaividz2.zee5.com/image/upload/w_396,h_224,c_scale,f_webp,q_auto:eco/resources/0-9-zeeaction/cover/1920x770126103899"}},
            {"@id": "5023", "display-name": "Zee Chitramandir", "icon": {"@src": "https://akamaividz2.zee5.com/image/upload/w_1755,h_987,c_scale,f_webp,q_auto:eco/resources/0-9-394/list_clean/1920x1080liste8fe4dcfd539403d973018b5d3e16309.png"}},
            {"@id": "5024", "display-name": "Zee Anmol TV", "icon": {"@src": "https://akamaividz2.zee5.com/image/upload/w_1755,h_987,c_scale,f_webp,q_auto:eco/resources/0-9-zeeanmol/list_clean/1920x1080list0481942c331940e0a2356355bcdec8bb.png"}},
            {"@id": "5025", "display-name": "Zee Anmol Cinema_2", "icon": {"@src": "https://akamaividz2.zee5.com/image/upload/w_396,h_224,c_scale,f_webp,q_auto:eco/resources/0-9-zeeanmol/cover/1920x77021724318"}},
            {"@id": "5026", "display-name": "Big Magic", "icon": {"@src": "https://akamaividz2.zee5.com/image/upload/w_396,h_224,c_scale,f_webp,q_auto:eco/resources/0-9-zeeanmol/cover/1920x77021724318"}},
    ]

    for zee in zee_channels:
        cid = zee["@id"]
        name = zee["display-name"]
        logo = zee["icon"]["@src"]

        m3ustr += (
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" group-title="ZEE" tvg-logo="{logo}",{name}\n'
            f'plugin://plugin.kodi.jiotv/resources/lib/player/play/?channel_id={cid}\n'
        )

    with open(M3U_SRC, "w+", encoding="utf-8") as f:
        f.write(m3ustr.replace("\xa0", " "))

    if notify == "yes":
        Script.notify("JioTV", "Playlist updated.")


@Script.register
def epg_setup(plugin):
    Script.notify("Please wait", "Epg setup in progress")
    pDialog = DialogProgress()
    pDialog.create("Epg setup in progress")
    url = Settings.get_string("epgsource")
    if not url or (len(url) < 5):
        url = "https://raw.githubusercontent.com/mitthu786/tvepg/main/jiotv/epg.xml.gz"
    
    response = requests.request("GET", url, headers={}, data={})
    with open(EPG_PATH, "wb") as f:
        f.write(response.content)
    
    pDialog.update(20)
    with gzip.open(EPG_PATH, "rb") as f:
        data = f.read()
        xml_content = data.decode("utf-8")
        root = ET.fromstring(xml_content)
    
    pDialog.update(30)
    pDialog.update(35)
    pDialog.update(45)
    for program in root.iterfind(".//programme"):
        icon = program.find("icon")
        icon_src = icon.get("src")
        jpg_name = icon_src.rsplit("/", 1)[-1]
        catchup_id = os.path.splitext(jpg_name)[0]
        program.set("catchup-id", catchup_id)
        title = program.find("title")
        title.text = title.text.strip()
    
    pDialog.update(60)
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    doctype_declaration = '<!DOCTYPE tv SYSTEM "xmltv.dtd">\n'
    full_xml_bytes = (
        xml_declaration.encode("UTF-8")
        + doctype_declaration.encode("UTF-8")
        + ET.tostring(root, encoding="UTF-8")
    )
    gzip_bytes = gzip.compress(full_xml_bytes)
    pDialog.update(80)
    with open(EPG_PATH, "wb") as f:
        f.write(gzip_bytes)
    pDialog.update(100)
    pDialog.close()
    Script.notify("JioTV", "Epg generated")


@Script.register
def pvrsetup(plugin):
    executebuiltin("RunPlugin(plugin://plugin.kodi.jiotv/resources/lib/pvr/m3ugen/)")
    IDdoADDON = "pvr.iptvsimple"

    def set_setting(id, value):
        if Addon(IDdoADDON).getSetting(id) != value:
            Addon(IDdoADDON).setSetting(id, value)

    if check_addon(IDdoADDON):
        set_setting("m3uPathType", "0")
        set_setting("m3uPath", M3U_SRC)
        set_setting("epgPathType", "1")
        set_setting("epgUrl", EPG_SRC)
        set_setting("epgCache", "false")
        set_setting("useInputstreamAdaptiveforHls", "true")
        set_setting("catchupEnabled", "true")
        set_setting("catchupWatchEpgBeginBufferMins", "0")
        set_setting("catchupWatchEpgEndBufferMins", "0")
    _setup(M3U_SRC, EPG_SRC)


@Script.register
def cleanup(plugin):
    urlquick.cache_cleanup(-1)
    cleanLocalCache()
    Script.notify("Cache Cleaned", "")

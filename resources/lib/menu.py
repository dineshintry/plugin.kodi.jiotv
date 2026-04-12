# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import urlquick
from datetime import datetime, timedelta, date
from time import time
from codequick import Route, Listitem, Script
from codequick.script import Settings
from resources.lib.constants import (
    IMG_CATCHUP,
    IMG_CATCHUP_SHOWS,
    CATCHUP_SRC,
)
from resources.lib.utils import (
    getCachedChannels,
    getCachedDictionary,
    Monitor,
)

monitor = Monitor()

def get_play_callback():
    from resources.lib.player import play
    return play

def get_record_live_stream_callback():
    from resources.lib.recorder import record_live_stream
    return record_live_stream

@Route.register
def root(plugin):
    from xbmcaddon import Addon
    addon = Addon()
    if addon.getSetting("migrated_quality") != "true":
        addon.setSetting("quality", "Manual")
        addon.setSetting("migrated_quality", "true")
        
    yield Listitem.from_dict(
        **{
            "label": "Video on Demand",
            "art": {
                "thumb": IMG_CATCHUP_SHOWS + "cms/210528144026.jpg",
                "icon": IMG_CATCHUP_SHOWS + "cms/210528144026.jpg",
                "fanart": IMG_CATCHUP_SHOWS + "cms/210528144026.jpg",
            },
            "callback": Route.ref("/resources/lib/vod:show_vod"),
        }
    )
    for e in ["Genres", "Languages"]:
        yield Listitem.from_dict(
            **{
                "label": e,
                "callback": Route.ref("/resources/lib/menu:show_listby"),
                "params": {"by": e},
            }
        )


@Route.register
def show_listby(plugin, by):
    from resources.lib.constants import IMG_CONFIG
    dictionary = getCachedDictionary()
    if not dictionary:
        yield Listitem.from_dict(
            **{
                "label": "Error: Unable to load dictionary. Please clean cache and retry.",
                "callback": "",
            }
        )
        return

    GENRE_MAP = dictionary.get("channelCategoryMapping") or {}
    LANG_MAP = dictionary.get("languageIdMapping") or {}

    if not LANG_MAP or not GENRE_MAP:
        yield Listitem.from_dict(
            **{
                "label": "Error: Dictionary data incomplete. Please clean cache and retry.",
                "callback": "",
            }
        )
        return

    langValues = list(LANG_MAP.values())
    langValues.append("Extra")
    CONFIG = {
        "Genres": GENRE_MAP.values(),
        "Languages": langValues,
    }
    for each in CONFIG[by]:
        tvImg = IMG_CONFIG[by].get(each, {}).get("tvImg", "")
        promoImg = IMG_CONFIG[by].get(each, {}).get("promoImg", "")
        yield Listitem.from_dict(
            **{
                "label": each,
                "art": {"thumb": tvImg, "icon": tvImg, "fanart": promoImg},
                "callback": Route.ref("/resources/lib/menu:show_category"),
                "params": {"categoryOrLang": each, "by": by},
            }
        )


def is_lang_allowed(langId, langMap):
    if langId in langMap.keys():
        try:
            return Settings.get_boolean(langMap[langId])
        except Exception:
            return True  # If setting doesn't exist, show the channel
    else:
        try:
            return Settings.get_boolean("Extra")
        except Exception:
            return True


def is_genre_allowed(id, map):
    if id in map.keys():
        try:
            return Settings.get_boolean(map[id])
        except Exception:
            # Genres like 'Religious', 'Regional' have no settings toggle
            # Default to showing them rather than hiding
            return True
    else:
        # Unknown genre IDs should be shown, not silently hidden
        return True


def isPlayAbleLang(each, LANG_MAP):
    return not each.get("channelIdForRedirect") and is_lang_allowed(
        str(each.get("channelLanguageId")), LANG_MAP
    )


def isPlayAbleGenre(each, GENRE_MAP):
    return not each.get("channelIdForRedirect") and is_genre_allowed(
        str(each.get("channelCategoryId")), GENRE_MAP
    )


@Route.register
def show_category(plugin, categoryOrLang, by):
    play = get_play_callback()
    record_live_stream = get_record_live_stream_callback()
    resp = getCachedChannels()
    if not resp:
        yield Listitem.from_dict(
            **{
                "label": "Error: Unable to load channel list. Check your connection and try again.",
                "callback": "",
            }
        )
        return
        
    dictionary = getCachedDictionary()
    if not dictionary:
        yield Listitem.from_dict(
            **{
                "label": "Error: Unable to load channel dictionary.",
                "callback": "",
            }
        )
        return
        
    GENRE_MAP = dictionary.get("channelCategoryMapping") or {}
    LANG_MAP = dictionary.get("languageIdMapping") or {}

    def fltr(x):
        try:
            # Skip redirect channels always
            if x.get("channelIdForRedirect"):
                return False

            fby = by.lower()[:-1] if by.endswith("s") else by.lower()
            if fby == "genre":
                # Browsing by genre: match genre AND apply language filter
                genre_id = str(x.get("channelCategoryId", ""))
                genre_name = GENRE_MAP.get(genre_id, "")
                return genre_name == categoryOrLang and is_lang_allowed(
                    str(x.get("channelLanguageId", "")), LANG_MAP
                )
            else:
                # Browsing by language: match language only, show ALL genres
                lang_id = str(x.get("channelLanguageId", ""))
                if categoryOrLang == "Extra":
                    return lang_id not in LANG_MAP.keys()
                else:
                    return LANG_MAP.get(lang_id, "") == categoryOrLang
        except Exception:
            return False
    try:
        flist = list(filter(fltr, resp))
        if len(flist) < 1:
            yield Listitem.from_dict(
                **{
                    "label": "No Results Found, Go Back",
                    "callback": show_listby,
                    "params": {"by": by},
                }
            )
        else:
            for each in flist:
                try:
                    if Settings.get_boolean("number_toggle"):
                        channel_number = int(each.get("channel_order", 0)) + 1
                        channel_name = str(channel_number) + " " + each.get("channel_name", "Unknown")
                    else:
                        channel_name = each.get("channel_name", "Unknown")
                    
                    litm = Listitem.from_dict(
                        **{
                            "label": channel_name,
                            "art": {
                                "thumb": IMG_CATCHUP + each.get("logoUrl", ""),
                                "icon": IMG_CATCHUP + each.get("logoUrl", ""),
                                "fanart": IMG_CATCHUP + each.get("logoUrl", ""),
                                "clearlogo": IMG_CATCHUP + each.get("logoUrl", ""),
                                "clearart": IMG_CATCHUP + each.get("logoUrl", ""),
                            },
                            "callback": play,
                            "params": {
                                "channel_id": each.get("channel_id"),
                                "languageId": each.get("channelLanguageId")
                            },
                        }
                    )
                    
                    if each.get("isCatchupAvailable"):
                        # Proper CodeQuick context menu for Catchup and Recording
                        from urllib.parse import urlencode
                        
                        record_params = {"channel_id": each.get("channel_id"), "channel_name": each.get("channel_name", "Stream")}
                        record_action = f"RunPlugin(plugin://plugin.kodi.jiotv/resources/lib/main/record_live_stream/?{urlencode(record_params)})"
                        
                        catchup_params = {
                            "day": 0, 
                            "channel_id": each.get("channel_id"),
                            "languageId": each.get("channelLanguageId")
                        }
                        catchup_url = f"plugin://plugin.kodi.jiotv/resources/lib/menu/show_epg/?{urlencode(catchup_params)}"
                        catchup_action = f"Container.Update({catchup_url})"
                        
                        litm.context.append(("Catchup", catchup_action))
                        litm.context.append(("Record Live Stream", record_action))
                    yield litm
                except Exception as loop_e:
                    Script.log(f"Error processing channel {each.get('channel_name')}: {loop_e}", lvl=Script.WARNING)
                    continue
    except Exception as e:
        Script.notify("Error loading category", e)
        return


@Route.register
def show_epg(plugin, day, channel_id, languageId=None):
    play = get_play_callback()
    resp = urlquick.get(
        CATCHUP_SRC.format(day, channel_id), max_age=1800, timeout=15
    ).json()
    epg = sorted(resp["epg"], key=lambda show: show["startEpoch"], reverse=False)
    livetext = "[COLOR red] [ LIVE ] [/COLOR]"
    for each in epg:
        current_epoch = int(time() * 1000)
        if not each["stbCatchupAvailable"] or each["startEpoch"] > current_epoch:
            continue
        islive = each["startEpoch"] < current_epoch and each["endEpoch"] > current_epoch
        start_time = datetime.fromtimestamp(int(each["startEpoch"] * 0.001))
        end_time = datetime.fromtimestamp(int(each["endEpoch"] * 0.001))
        showtime = (
            "[COLOR red][LIVE][/COLOR] "
            if islive
            else f"[{start_time.strftime('%I:%M %p')}] "
        )
        label = each["showname"] + " " + showtime
        yield Listitem.from_dict(
            **{
                "label": label,
                "art": {
                    "thumb": IMG_CATCHUP_SHOWS + each["episodePoster"],
                    "icon": IMG_CATCHUP_SHOWS + each["episodePoster"],
                    "fanart": IMG_CATCHUP_SHOWS + each["episodePoster"],
                },
                "callback": play,
                "info": {
                    "title": label,
                    "originaltitle": each["showname"],
                    "tvshowtitle": each["showname"],
                    "genre": each["showGenre"],
                    "plot": each["description"],
                    "episodeguide": each.get("episode_desc"),
                    "episode": 0 if each["episode_num"] == -1 else each["episode_num"],
                    "cast": each["starCast"].split(", "),
                    "director": each["director"],
                    "duration": each["duration"] * 60,
                    "tag": each["keywords"],
                    "mediatype": "episode",
                },
                "params": {
                    "channel_id": each.get("channel_id"),
                    "showtime": datetime.fromtimestamp(int(each.get("startEpoch", 0) * 0.001)).strftime("%H%M%S"),
                    "srno": datetime.fromtimestamp(int(each.get("startEpoch", 0) * 0.001)).strftime("%Y%m%d"),
                    "programId": each.get("showId") if each.get("showId") else f"CHN-{each.get('channel_id')}-PRG-{datetime.fromtimestamp(int(each.get('startEpoch', 0) * 0.001)).strftime('%Y%m%d%H%M')}",
                    "begin": datetime.utcfromtimestamp(
                        int(each.get("startEpoch", 0) * 0.001)
                    ).strftime("%Y%m%dT%H%M%S"),
                    "end": datetime.utcfromtimestamp(
                        int(each.get("endEpoch", 0) * 0.001)
                    ).strftime("%Y%m%dT%H%M%S"),
                    "languageId": languageId
                },
            }
        )
    if int(day) == 0:
        for i in range(-1, -7, -1):
            label = (
                "Yesterday"
                if i == -1
                else (date.today() + timedelta(days=i)).strftime("%A %d %B")
            )
            yield Listitem.from_dict(
                **{
                    "label": label,
                    "callback": Route.ref("/resources/lib/menu:show_epg"),
                    "params": {"day": i, "channel_id": channel_id, "languageId": languageId},
                }
            )

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
    GENRE_MAP = dictionary.get("channelCategoryMapping")
    LANG_MAP = dictionary.get("languageIdMapping")
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
        return Settings.get_boolean(langMap[langId])
    else:
        return Settings.get_boolean("Extra")


def is_genre_allowed(id, map):
    if id in map.keys():
        return Settings.get_boolean(map[id])
    else:
        return False


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
        
    GENRE_MAP = dictionary.get("channelCategoryMapping")
    LANG_MAP = dictionary.get("languageIdMapping")

    def fltr(x):
        fby = by.lower()[:-1] if by.endswith("s") else by.lower()
        if fby == "genre":
            return GENRE_MAP[
                str(x.get("channelCategoryId"))
            ] == categoryOrLang and isPlayAbleLang(x, LANG_MAP)
        else:
            if categoryOrLang == "Extra":
                return str(
                    x.get("channelLanguageId")
                ) not in LANG_MAP.keys() and isPlayAbleGenre(x, GENRE_MAP)
            else:
                if str(x.get("channelLanguageId")) not in LANG_MAP.keys():
                    return False
                return LANG_MAP[
                    str(x.get("channelLanguageId"))
                ] == categoryOrLang and isPlayAbleGenre(x, GENRE_MAP)

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
                if Settings.get_boolean("number_toggle"):
                    channel_number = int(each.get("channel_order")) + 1
                    channel_name = str(channel_number) + " " + each.get("channel_name")
                else:
                    channel_name = each.get("channel_name")
                litm = Listitem.from_dict(
                    **{
                        "label": channel_name,
                        "art": {
                            "thumb": IMG_CATCHUP + each.get("logoUrl"),
                            "icon": IMG_CATCHUP + each.get("logoUrl"),
                            "fanart": IMG_CATCHUP + each.get("logoUrl"),
                            "clearlogo": IMG_CATCHUP + each.get("logoUrl"),
                            "clearart": IMG_CATCHUP + each.get("logoUrl"),
                        },
                        "callback": play,
                        "params": {"channel_id": each.get("channel_id")},
                    }
                )
                if each.get("isCatchupAvailable"):
                    start_time = datetime.fromtimestamp(int(each.get("startEpoch", 0) * 0.001))
                    
                    litm.context.container(
                        show_epg, "Catchup", 0, each.get("channel_id")
                    )
                    params = {"channel_id": each.get("channel_id"), "channel_name": each.get("channel_name")}
                    from urllib.parse import urlencode
                    action = f"RunPlugin(plugin://plugin.kodi.jiotv/resources/lib/main/record_live_stream/?{urlencode(params)})"
                    litm.context.menu([("Record Live Stream", action)])
                yield litm
    except Exception as e:
        Script.notify("Error", e)
        monitor.waitForAbort(1)
        return


@Route.register
def show_epg(plugin, day, channel_id):
    play = get_play_callback()
    resp = urlquick.get(
        CATCHUP_SRC.format(day, channel_id), max_age=-1
    ).json()
    epg = sorted(resp["epg"], key=lambda show: show["startEpoch"], reverse=False)
    livetext = "[COLOR red] [ LIVE ] [/COLOR]"
    for each in epg:
        current_epoch = int(time() * 1000)
        if not each["stbCatchupAvailable"] or each["startEpoch"] > current_epoch:
            continue
        islive = each["startEpoch"] < current_epoch and each["endEpoch"] > current_epoch
        showtime = (
            "   " + livetext
            if islive
            else datetime.fromtimestamp(int(each["startEpoch"] * 0.001)).strftime(
                "    [ %I:%M %p -"
            )
            + datetime.fromtimestamp(int(each["endEpoch"] * 0.001)).strftime(
                " %I:%M %p ]   %a"
            )
        )
        yield Listitem.from_dict(
            **{
                "label": each["showname"] + showtime,
                "art": {
                    "thumb": IMG_CATCHUP_SHOWS + each["episodePoster"],
                    "icon": IMG_CATCHUP_SHOWS + each["episodePoster"],
                    "fanart": IMG_CATCHUP_SHOWS + each["episodePoster"],
                },
                "callback": play,
                "info": {
                    "title": each["showname"] + showtime,
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
                    "params": {"day": i, "channel_id": channel_id},
                }
            )

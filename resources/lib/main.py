# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# xbmc imports
from xbmcaddon import Addon
from xbmc import executebuiltin, log, LOGINFO
from xbmcgui import Dialog, DialogProgress

# codequick imports
from codequick import Route, run, Listitem, Resolver, Script
from codequick.utils import keyboard
from codequick.script import Settings
from codequick.storage import PersistentDict
import xbmc
import time
import xbmcplugin
import xbmcgui
import sys

# add-on imports
from resources.lib.utils import (
    getTokenParams,
    getHeaders,
    isLoggedIn,
    login as ULogin,
    logout as ULogout,
    check_addon,
    sendOTPV2,
    get_local_ip,
    getChannelHeaders,
    getSonyHeaders,
    getZeeHeaders,
    zeeCookie,
    getChannelHeadersWithHost,
    quality_to_enum,
    _setup,
    kodi_rpc,
    Monitor,
    getCachedChannels,
    getCachedDictionary,
    cleanLocalCache,
    getFeatured,
    getVODContent,
    getVODChannels,
    getChannelVODContent,
)
from resources.lib.constants import (
    GET_CHANNEL_URL,
    IMG_CATCHUP,
    PLAY_URL,
    IMG_CATCHUP_SHOWS,
    CATCHUP_SRC,
    M3U_SRC,
    EPG_SRC,
    M3U_CHANNEL,
    IMG_CONFIG,
    EPG_PATH,
    ADDON,
    ADDON_ID,
    VOD_SRC,
    VOD_CHANNELS_SRC,
)

# additional imports
import urlquick
from uuid import uuid4
from urllib.parse import urlencode
import inputstreamhelper
from time import time, sleep
from datetime import datetime, timedelta, date
import m3u8
import requests
import gzip
import xml.etree.ElementTree as ET
import os
import json

# Root path of plugin

monitor = Monitor()


@Route.register
def root(plugin):
    yield Listitem.from_dict(
        **{
            "label": "Video on Demand/Catchup TV",
            "art": {
                "thumb": IMG_CATCHUP_SHOWS + "cms/210528144026.jpg",
                "icon": IMG_CATCHUP_SHOWS + "cms/210528144026.jpg",
                "fanart": IMG_CATCHUP_SHOWS + "cms/210528144026.jpg",
            },
            "callback": Route.ref("/resources/lib/main:show_vod"),
        }
    )
    for e in ["Genres", "Languages"]:
        yield Listitem.from_dict(
            **{
                "label": e,
                # "art": {
                #     "thumb": CONFIG[e][0].get("tvImg"),
                #     "icon": CONFIG[e][0].get("tvImg"),
                #     "fanart": CONFIG[e][0].get("promoImg"),
                # },
                "callback": Route.ref("/resources/lib/main:show_listby"),
                "params": {"by": e},
            }
        )


# Shows Featured Content
@Route.register
def show_featured(plugin, id=None):
    for each in getFeatured():
        if id:
            if int(each.get("id", 0)) == int(id):
                data = each.get("data", [])
                for child in data:
                    info_dict = {
                        "art": {
                            "thumb": IMG_CATCHUP_SHOWS + child.get("episodePoster", ""),
                            "icon": IMG_CATCHUP_SHOWS + child.get("episodePoster", ""),
                            "fanart": IMG_CATCHUP_SHOWS
                            + child.get("episodePoster", ""),
                            "clearart": IMG_CATCHUP + child.get("logoUrl", ""),
                            "clearlogo": IMG_CATCHUP + child.get("logoUrl", ""),
                        },
                        "info": {
                            "originaltitle": child.get("showname"),
                            "tvshowtitle": child.get("showname"),
                            "genre": child.get("showGenre"),
                            "plot": child.get("description"),
                            "episodeguide": child.get("episode_desc"),
                            "episode": 0
                            if child.get("episode_num") == -1
                            else child.get("episode_num"),
                            "cast": child.get("starCast", "").split(", "),
                            "director": child.get("director"),
                            "duration": child.get("duration") * 60,
                            "tag": child.get("keywords"),
                            "mediatype": "movie"
                            if child.get("channel_category_name") == "Movies"
                            else "episode",
                        },
                    }
                    if child.get("showStatus") == "Now":
                        info_dict["label"] = info_dict["info"]["title"] = (
                            child.get("showname", "") + " [COLOR red] [ LIVE ] [/COLOR]"
                        )
                        info_dict["callback"] = play
                        info_dict["params"] = {"channel_id": child.get("channel_id")}
                        yield Listitem.from_dict(**info_dict)
                    elif child.get("showStatus") == "future":
                        timetext = datetime.fromtimestamp(
                            int(child.get("startEpoch", 0) * 0.001)
                        ).strftime("    [ %I:%M %p -") + datetime.fromtimestamp(
                            int(child.get("endEpoch", 0) * 0.001)
                        ).strftime(
                            " %I:%M %p ]   %a"
                        )
                        info_dict["label"] = info_dict["info"]["title"] = child.get(
                            "showname", ""
                        ) + (" [COLOR green]%s[/COLOR]" % timetext)
                        info_dict["callback"] = ""
                        yield Listitem.from_dict(**info_dict)
                    elif child.get("showStatus") == "catchup":
                        timetext = datetime.fromtimestamp(
                            int(child.get("startEpoch", 0) * 0.001)
                        ).strftime("    [ %I:%M %p -") + datetime.fromtimestamp(
                            int(child.get("endEpoch", 0) * 0.001)
                        ).strftime(
                            " %I:%M %p ]   %a"
                        )
                        info_dict["label"] = info_dict["info"]["title"] = child.get(
                            "showname", ""
                        ) + (" [COLOR yellow]%s[/COLOR]" % timetext)
                        info_dict["callback"] = play
                        info_dict["params"] = {
                            "channel_id": child.get("channel_id"),
                            "showtime": datetime.fromtimestamp(int(child.get("startEpoch", 0) * 0.001)).strftime("%H%M%S"),  # Generate from startEpoch
                            "srno": datetime.fromtimestamp(int(child.get("startEpoch", 0) * 0.001)).strftime("%Y%m%d"),  # Use date as srno
                            "programId": child.get("showId") if child.get("showId") else f"CHN-{child.get('channel_id')}-PRG-{datetime.fromtimestamp(int(child.get('startEpoch', 0) * 0.001)).strftime('%Y%m%d%H%M')}",  # Generate unique programId
                            "begin": datetime.utcfromtimestamp(
                                int(child.get("startEpoch", 0) * 0.001)
                            ).strftime("%Y%m%dT%H%M%S"),
                            "end": datetime.utcfromtimestamp(
                                int(child.get("endEpoch", 0) * 0.001)
                            ).strftime("%Y%m%dT%H%M%S"),
                        }
                        yield Listitem.from_dict(**info_dict)
        else:
            yield Listitem.from_dict(
                **{
                    "label": each.get("name"),
                    "art": {
                        "thumb": IMG_CATCHUP_SHOWS
                        + each.get("data", [{}])[0].get("episodePoster"),
                        "icon": IMG_CATCHUP_SHOWS
                        + each.get("data", [{}])[0].get("episodePoster"),
                        "fanart": IMG_CATCHUP_SHOWS
                        + each.get("data", [{}])[0].get("episodePoster"),
                    },
                    "callback": Route.ref("/resources/lib/main:show_featured"),
                    "params": {"id": each.get("id")},
                }
            )


# Shows VOD Content
@Route.register
def show_vod(plugin, category=None):
    vod_content = getVODContent()
    vod_channels = getVODChannels()
    
    if not vod_content and not vod_channels:
        yield Listitem.from_dict(
            **{
                "label": "No VOD content available",
                "callback": "",
            }
        )
        return
    
    # Show VOD channels by language if available
    if vod_channels:
        dictionary = getCachedDictionary()
        LANG_MAP = dictionary.get("languageIdMapping")
        
        # Group VOD channels by language for better accessibility
        vod_by_language = {}
        for channel in vod_channels:
            lang_id = str(channel.get("channelLanguageId", ""))
            if lang_id in LANG_MAP:
                lang_name = LANG_MAP[lang_id]
                if lang_name not in vod_by_language:
                    vod_by_language[lang_name] = []
                vod_by_language[lang_name].append(channel)
            else:
                # Uncategorized
                if "Other" not in vod_by_language:
                    vod_by_language["Other"] = []
                vod_by_language["Other"].append(channel)
        
        # Add language categories
        for lang_name, channels in sorted(vod_by_language.items()):
            if channels:  # Only show languages that have channels
                yield Listitem.from_dict(
                    **{
                        "label": f"{lang_name} [COLOR cyan][VOD][/COLOR]",
                        "art": {
                            "thumb": IMG_CONFIG["Languages"].get(lang_name, {}).get("tvImg", ""),
                            "icon": IMG_CONFIG["Languages"].get(lang_name, {}).get("tvImg", ""),
                            "fanart": IMG_CONFIG["Languages"].get(lang_name, {}).get("promoImg", ""),
                        },
                        "callback": Route.ref("/resources/lib/main:show_vod_channels_by_language"),
                        "params": {"language": lang_name},
                    }
                )
        
        # Add uncategorized channels if any
        if "Other" in vod_by_language and vod_by_language["Other"]:
            yield Listitem.from_dict(
                **{
                    "label": f"Other [COLOR cyan][VOD][/COLOR]",
                    "art": {
                        "thumb": IMG_CONFIG["Genres"].get("Other", {}).get("tvImg", ""),
                        "icon": IMG_CONFIG["Genres"].get("Other", {}).get("tvImg", ""),
                        "fanart": IMG_CONFIG["Genres"].get("Other", {}).get("promoImg", ""),
                    },
                    "callback": Route.ref("/resources/lib/main:show_vod_channels_by_language"),
                    "params": {"language": "Other"},
                }
            )
    
    # Show VOD content by category
    if vod_content:
        # Group content by category if categories exist
        categories = {}
        for item in vod_content:
            cat = item.get("category", "General")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)
        
        for cat_name, items in categories.items():
            yield Listitem.from_dict(
                **{
                    "label": cat_name,
                    "art": {
                        "thumb": IMG_CATCHUP_SHOWS + items[0].get("episodePoster", "cms/210528144026.jpg"),
                        "icon": IMG_CATCHUP_SHOWS + items[0].get("episodePoster", "cms/210528144026.jpg"),
                        "fanart": IMG_CATCHUP_SHOWS + items[0].get("episodePoster", "cms/210528144026.jpg"),
                    },
                    "callback": Route.ref("/resources/lib/main:show_vod_category"),
                    "params": {"category": cat_name},
                }
            )


# Shows VOD content by category
@Route.register
def show_vod_category(plugin, category):
    vod_content = getVODContent()
    
    # Filter by category if specified
    if category != "All":
        vod_content = [item for item in vod_content if item.get("_vodCategory") == category]
    
    if not vod_content:
        yield Listitem.from_dict(
            **{
                "label": f"No VOD content in {category}",
                "callback": "",
            }
        )
        return
    
    for item in vod_content:
        # For featured content that acts as VOD, we need to handle it differently
        # Since it's not true VOD, we'll try to find the channel and use catchup
        channel_id = item.get("channel_id")
        
        info_dict = {
            "art": {
                "thumb": IMG_CATCHUP_SHOWS + item.get("episodePoster", ""),
                "icon": IMG_CATCHUP_SHOWS + item.get("episodePoster", ""),
                "fanart": IMG_CATCHUP_SHOWS + item.get("episodePoster", ""),
                "clearart": IMG_CATCHUP + item.get("logoUrl", ""),
                "clearlogo": IMG_CATCHUP + item.get("logoUrl", ""),
            },
            "info": {
                "title": item.get("showname", ""),
                "originaltitle": item.get("showname", ""),
                "tvshowtitle": item.get("showname", ""),
                "genre": item.get("showGenre", ""),
                "plot": item.get("description", ""),
                "episodeguide": item.get("episode_desc", ""),
                "episode": 0 if item.get("episode_num") == -1 else item.get("episode_num", 0),
                "season": item.get("season_num", 1),
                "cast": item.get("starCast", "").split(", ") if item.get("starCast") else [],
                "director": item.get("director", ""),
                "duration": item.get("duration", 0) * 60 if item.get("duration") else 0,
                "tag": item.get("keywords", ""),
                "mediatype": "movie" if item.get("channel_category_name") == "Movies" else "episode",
                "year": int(item.get("year", 0)) if item.get("year") and item.get("year").isdigit() else 0,
            },
            "label": item.get("showname", ""),
        }
        
        if channel_id:
            # If we have a channel_id, try to play it as catchup
            info_dict["callback"] = play
            info_dict["params"] = {
                "channel_id": channel_id,
                "showtime": datetime.fromtimestamp(int(item.get("startEpoch", 0)) // 1000).strftime("%H%M%S"),  # Generate from startEpoch
                "srno": datetime.fromtimestamp(int(item.get("startEpoch", 0)) // 1000).strftime("%Y%m%d"),  # Use date as srno
                "programId": item.get("showId") if item.get("showId") else f"CHN-{channel_id}-PRG-{datetime.fromtimestamp(int(item.get('startEpoch', 0)) // 1000).strftime('%Y%m%d%H%M')}",  # Generate unique programId
                "begin": datetime.utcfromtimestamp(int(item.get("startEpoch", 0)) // 1000).strftime("%Y%m%dT%H%M%S"),
                "end": datetime.utcfromtimestamp(int(item.get("endEpoch", 0)) // 1000).strftime("%Y%m%dT%H%M%S"),
            }
        else:
            # No channel_id, show as info only
            info_dict["callback"] = ""
            info_dict["label"] += " [No channel info]"
        
        yield Listitem.from_dict(**info_dict)





# Shows VOD channels by language
@Route.register
def show_vod_channels_by_language(plugin, language):
    vod_channels = getVODChannels()
    dictionary = getCachedDictionary()
    LANG_MAP = dictionary.get("languageIdMapping")
    
    for channel in vod_channels:
        lang_id = str(channel.get("channelLanguageId", ""))
        if lang_id in LANG_MAP and LANG_MAP[lang_id] == language:
            if Settings.get_boolean("number_toggle"):
                channel_number = int(channel.get("channel_order", 0)) + 1
                channel_name = str(channel_number) + " " + channel.get("channel_name", "")
            else:
                channel_name = channel.get("channel_name", "")
                
            yield Listitem.from_dict(
                **{
                    "label": channel_name + " [COLOR cyan][VOD][/COLOR]",
                    "art": {
                        "thumb": IMG_CATCHUP + channel.get("logoUrl", ""),
                        "icon": IMG_CATCHUP + channel.get("logoUrl", ""),
                        "fanart": IMG_CATCHUP + channel.get("logoUrl", ""),
                        "clearlogo": IMG_CATCHUP + channel.get("logoUrl", ""),
                        "clearart": IMG_CATCHUP + channel.get("logoUrl", ""),
                    },
                    "callback": Route.ref("/resources/lib/main:show_vod_channel_content"),
                    "params": {"channel_id": channel.get("channel_id", "")},
                }
            )

# Shows VOD content for a specific channel
@Route.register
def show_vod_channel_content(plugin, channel_id, offset_days=None):
    # If offset_days is specified, show content for that specific day
    if offset_days is not None:
        # Show VOD content for the specific day
        vod_content = getChannelVODContent(channel_id, offset_days)
        
        if not vod_content:
            yield Listitem.from_dict(
                **{
                    "label": f"No VOD content available for this channel ({offset_days if offset_days > 0 else 'today'})",
                    "callback": "",
                }
            )
            return
        
        # Display VOD content sorted by most recent first
        for item in vod_content:
            # Format the time display with start and end times
            start_epoch = item.get("startEpoch", 0)
            end_epoch = item.get("endEpoch", 0)
            
            # Skip items with invalid timestamps
            if not start_epoch or not end_epoch or start_epoch <= 0 or end_epoch <= 0:
                Script.log(f"[VOD-DEBUG] Skipping item with invalid timestamps: start={start_epoch}, end={end_epoch}", lvl=Script.WARNING)
                continue
            
            try:
                start_time = datetime.fromtimestamp(int(start_epoch) // 1000)
                end_time = datetime.fromtimestamp(int(end_epoch) // 1000)
                timetext = f"  [{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}]"
            except (ValueError, OSError) as e:
                Script.log(f"[VOD-DEBUG] Error parsing timestamps for '{item.get('showname', '')}': {e}", lvl=Script.ERROR)
                # Fallback to no timestamp display
                timetext = ""
            
            # Add relative time for better UX
            current_time = datetime.now()
            time_diff = current_time - start_time
            
            if time_diff.days == 0:
                if time_diff.seconds < 3600:
                    time_ago = f"{time_diff.seconds // 60} minutes ago"
                else:
                    time_ago = f"{time_diff.seconds // 3600} hours ago"
            else:
                time_ago = f"{time_diff.days} days ago"
            
            # Final label format - debug what's being shown
            if timetext.strip():
                label = f"{item.get('showname', '')} [{time_ago}]{timetext}"
            else:
                label = f"{item.get('showname', '')} [{time_ago}] [NO TIME INFO]"
            
            info_dict = {
                "art": {
                    "thumb": IMG_CATCHUP_SHOWS + item.get("episodePoster", ""),
                    "icon": IMG_CATCHUP_SHOWS + item.get("episodePoster", ""),
                    "fanart": IMG_CATCHUP_SHOWS + item.get("episodePoster", ""),
                    "clearart": IMG_CATCHUP + item.get("logoUrl", ""),
                    "clearlogo": IMG_CATCHUP + item.get("logoUrl", ""),
                },
                "info": {
                    "title": item.get("showname", ""),
                    "originaltitle": item.get("showname", ""),
                    "tvshowtitle": item.get("showname", ""),
                    "genre": item.get("showGenre", ""),
                    "plot": item.get("description", ""),
                    "episodeguide": item.get("episode_desc", ""),
                    "episode": 0 if item.get("episode_num") == -1 else item.get("episode_num", 0),
                    "season": item.get("season_num", 1),
                    "cast": item.get("starCast", "").split(", ") if item.get("starCast") else [],
                    "director": item.get("director", ""),
                    "duration": item.get("duration", 0) * 60 if item.get("duration") else 0,
                    "tag": item.get("keywords", ""),
                    "mediatype": "episode",
                    "year": int(item.get("year", 0)) if item.get("year") and item.get("year").isdigit() else 0,
                    "date": start_time.strftime("%d.%m.%Y"),
                },
                "label": label,
                "callback": play,
                "params": {
                    "channel_id": channel_id,
                    "showtime": datetime.fromtimestamp(int(item.get("startEpoch", 0)) // 1000).strftime("%H%M%S"),  # Generate from startEpoch
                    "srno": datetime.fromtimestamp(int(item.get("startEpoch", 0)) // 1000).strftime("%Y%m%d"),  # Use date as srno
                    "programId": item.get("showId") if item.get("showId") else f"CHN-{channel_id}-PRG-{datetime.fromtimestamp(int(item.get('startEpoch', 0)) // 1000).strftime('%Y%m%d%H%M')}",  # Generate unique programId
                    "begin": datetime.utcfromtimestamp(int(item.get("startEpoch", 0)) // 1000).strftime("%Y%m%dT%H%M%S"),
                    "end": datetime.utcfromtimestamp(int(item.get("endEpoch", 0)) // 1000).strftime("%Y%m%dT%H%M%S"),
                },
            }
            Script.log(f"[VOD-DEBUG] Generated VOD params for '{item.get('showname', '')}': channel_id={channel_id}, showtime={info_dict['params']['showtime']}, srno={info_dict['params']['srno']}, programId={info_dict['params']['programId'][:50]}...", lvl=Script.INFO)
            Script.log(f"[VOD-DEBUG] Generated VOD params for '{item.get('showname', '')}': channel_id={channel_id}, showtime={info_dict['params']['showtime']}, srno={info_dict['params']['srno']}, programId={info_dict['params']['programId'][:50]}...", lvl=Script.INFO)

            yield Listitem.from_dict(**info_dict)
    
    else:
        # Show day selection folders (0-7 days ago) - initial call
        for days_ago in range(8):  # Today + 7 days back
            if days_ago == 0:
                label = "Today"
                description = "VOD content from today"
            elif days_ago == 1:
                label = "1 Day Ago"
                description = "VOD content from yesterday"
            else:
                label = f"{days_ago} Days Ago"
                description = f"VOD content from {days_ago} days ago"
            
            yield Listitem.from_dict(
                **{
                    "label": label,
                    "info": {
                        "plot": description,
                    },
                    "callback": Route.ref("/resources/lib/main:show_vod_channel_content"),
                    "params": {"channel_id": channel_id, "offset_days": days_ago},
                }
            )


# Shows Filter options
@Route.register
def show_listby(plugin, by):
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
                "callback": Route.ref("/resources/lib/main:show_category"),
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


# Shows channels by selected filter/category


@Route.register
def show_category(plugin, categoryOrLang, by):
    resp = getCachedChannels()
    if not resp:
        # Channel list failed to load
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
                    # Generate proper VOD parameters from EPG data
                    start_time = datetime.fromtimestamp(int(each.get("startEpoch", 0) * 0.001))
                    catchup_params = {
                        "channel_id": each.get("channel_id"),
                        "showtime": start_time.strftime("%H%M%S"),  # Generate from startEpoch
                        "srno": start_time.strftime("%Y%m%d"),  # Use date as srno
                        "programId": each.get("showId") if each.get("showId") else f"CHN-{each.get('channel_id')}-PRG-{start_time.strftime('%Y%m%d%H%M')}",  # Generate unique programId
                        "begin": datetime.utcfromtimestamp(int(each.get("startEpoch", 0) * 0.001)).strftime("%Y%m%dT%H%M%S"),
                        "end": datetime.utcfromtimestamp(int(each.get("endEpoch", 0) * 0.001)).strftime("%Y%m%dT%H%M%S"),
                    }
                    Script.log(f"EPG catchup params: {catchup_params}", lvl=Script.INFO)
                    
                    litm.context.container(
                        show_epg, "Catchup", 0, each.get("channel_id")
                    )
                yield litm
    except Exception as e:
        Script.notify("Error", e)
        monitor.waitForAbort(1)
        return


# Shows EPG container from Context menu


@Route.register
def show_epg(plugin, day, channel_id):
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
                    "showtime": datetime.fromtimestamp(int(each.get("startEpoch", 0) * 0.001)).strftime("%H%M%S"),  # Generate from startEpoch
                    "srno": datetime.fromtimestamp(int(each.get("startEpoch", 0) * 0.001)).strftime("%Y%m%d"),  # Use date as srno
                    "programId": each.get("showId") if each.get("showId") else f"CHN-{each.get('channel_id')}-PRG-{datetime.fromtimestamp(int(each.get('startEpoch', 0) * 0.001)).strftime('%Y%m%d%H%M')}",  # Generate unique programId
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
                    "callback": Route.ref("/resources/lib/main:show_epg"),
                    "params": {"day": i, "channel_id": channel_id},
                }
            )


# Play live stream/ catchup according to params.
# Also insures that user is logged in.
@Resolver.register
@isLoggedIn
def play(plugin, channel_id, showtime=None, srno=None, programId=None, begin=None, end=None):
    Script.log(f"[VOD-DEBUG] PLAY function called with: channel_id={channel_id}, showtime={showtime}, srno={srno}, programId={programId}, begin={begin}, end={end}", lvl=Script.INFO)

    # import web_pdb; web_pdb.set_trace()
    headerssony = getSonyHeaders()  # sony headers
    sony_headers = getSonyHeaders()
    try:
        is_helper = inputstreamhelper.Helper("mpd", drm="com.widevine.alpha")
        hasIs = is_helper.check_inputstream()
        if not hasIs:
            Script.log("[VOD-DEBUG] InputStream helper check failed", lvl=Script.ERROR)
            return

        channel_id_str = str(channel_id)

        stream_type = "Seek"
        rjson = {"channel_id": int(channel_id), "stream_type": stream_type}
        isCatchup = False

        # Determine if this is a VOD/catchup request
        if showtime and srno:
            isCatchup = True
            rjson["showtime"] = showtime
            rjson["srno"] = srno
            rjson["stream_type"] = "Catchup"
            rjson["programId"] = programId
            rjson["begin"] = begin
            rjson["end"] = end
            
            # For VOD content, use different headers that might be more stable
            headers = getHeaders()
            headers["channelid"] = str(channel_id)
            # Use a fresh token for VOD requests to avoid 403 errors
            headers["srno"] = rjson["srno"]  # Use the actual srno from VOD params
            headers["showtime"] = rjson["showtime"]  # Include showtime in headers
            
            Script.log(f"[VOD-DEBUG] VOD REQUEST DETECTED: stream_type=Catchup, params={rjson}", lvl=Script.INFO)
            Script.log(f"[VOD-DEBUG] VOD HEADERS: srno={headers.get('srno')}, showtime={headers.get('showtime')}", lvl=Script.INFO)
        else:
            Script.log(f"[VOD-DEBUG] LIVE STREAM REQUEST: stream_type=Seek (no VOD params provided)", lvl=Script.INFO)

            headers = getHeaders()
            headers["channelid"] = str(channel_id)
            # Use actual srno from VOD parameters, not random UUID
            headers["srno"] = rjson["srno"] if isCatchup else str(uuid4())
            enableHost = Settings.get_boolean("enablehost")

        # blindly setting zee channel id for test
        zee_channels = {
            "5016": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105525/ZeeAnmolCinemaELE/master.m3u8",
            "5017": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105527/ZeeActionELE/master.m3u8",
            "5023": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105261/ZEECHITRAMANDIRELE/master.m3u8",
            "5024": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105526/ZeeAnmolELE/master.m3u8",
            "5025": "https://z5live-cf.zee5.com/out/v1/ZEE5_Live_Channels/Zee-Ganga-Zee-Anmol-Cinema-2-SD/master/master.m3u8",
            "5026": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105176/BigMagicELE/master.m3u8",
        }

        sony_headers = getSonyHeaders()

        if channel_id in zee_channels:
            if channel_id == "5016":
                zee_channelid = "0-9-zeeanmolcinema"
                host = "z5ak-cmaflive.zee5.com"
            elif channel_id == "5017":
                zee_channelid = "0-9-zeeaction"
                host = "z5ak-cmaflive.zee5.com"
            elif channel_id == "5023":
                zee_channelid = "0-9-394"
                host = "z5ak-cmaflive.zee5.com"
            elif channel_id == "5024":
                zee_channelid = "0-9-zeeanmol"
                host = "z5ak-cmaflive.zee5.com"
            elif channel_id == "5025":
                zee_channelid = "0-9-bigganga"
                host = "z5live-cf.zee5.com"
            elif channel_id == "5026":
                zee_channelid = "0-9-bigmagic_1786965389"
                host = "z5ak-cmaflive.zee5.com"
            else:
                zee_channelid = None

            cook = zeeCookie(zee_channelid)
            headerszee = getZeeHeaders(host)
            print("cookie zee: ", cook)
            base_url = zee_channels[channel_id]
            onlyUrl = f"{base_url}{cook}"
            url = onlyUrl
            print(cook)
            print(url)

        else:
            chan = str(channel_id)
            
            # Fetch Cached Channels to find Language ID
            langId = ""
            try:
                channels = getCachedChannels()
                if channels:
                    for c in channels:
                        if str(c.get("channel_id")) == chan:
                            langId = str(c.get("channelLanguageId", ""))
                            break
            except Exception as e:
                Script.log(f"Error fetching language ID: {e}", lvl=Script.ERROR)

            sony_headers = getSonyHeaders(channel_id=chan, languageId=langId)
            
            # Build API data with all necessary parameters
            api_data = f"stream_type={rjson['stream_type']}&channel_id={chan}"
            
            # Add VOD/catchup specific parameters
            if isCatchup:
                api_data += f"&srno={rjson.get('srno', '')}"
                api_data += f"&programId={rjson.get('programId', '')}"
                api_data += f"&begin={rjson.get('begin', '')}"
                api_data += f"&end={rjson.get('end', '')}"
                api_data += f"&showtime={rjson.get('showtime', '')}"
            
            Script.log(f"API call data: {api_data}", lvl=Script.INFO)
            
            res = urlquick.post(
                "https://jiotvapi.media.jio.com/playback/apis/v1.1/geturl",
                data=api_data,
                verify=False,
                headers=sony_headers,
                max_age=-1,
            )  # 471 sab

            print(res)
            Script.log(f"API response: {res.json()}", lvl=Script.INFO)

            # Analyze API response for VOD vs Live detection
            api_response = res.json()
            result_url = api_response.get("result", "")
            Script.log(f"[VOD-DEBUG] API result URL: {result_url}", lvl=Script.INFO)

            # Check if this is actually a VOD URL or live URL
            if isCatchup:
                if "catchup" in result_url.lower() or "vod" in result_url.lower():
                    Script.log("[VOD-DEBUG] SUCCESS: API returned VOD URL for catchup request", lvl=Script.INFO)
                elif "live" in result_url.lower() or "seek" in result_url.lower():
                    Script.log("[VOD-DEBUG] FAILURE: API returned LIVE URL for catchup request - FALLBACK DETECTED!", lvl=Script.ERROR)
                else:
                    Script.log(f"[VOD-DEBUG] UNKNOWN: API returned URL type for catchup: {result_url}", lvl=Script.WARNING)
            else:
                if "live" in result_url.lower() or "seek" in result_url.lower():
                    Script.log("[VOD-DEBUG] SUCCESS: API returned live URL for live request", lvl=Script.INFO)
                else:
                    Script.log(f"[VOD-DEBUG] UNEXPECTED: API returned non-live URL for live request: {result_url}", lvl=Script.WARNING)

            sonyheaders = sony_headers
            sonyheaders["cookie"] = "__hdnea__" + res.json().get("result", "").split("__hdnea__")[-1]
            sonyheaders.setdefault("user-agent", "jiotv")
            sonyheaders = {k: str(v) for k, v in sonyheaders.items() if v}
            print("printing sony headers and cookie")
            print(sonyheaders)

        # Common logic after the if/else
        if channel_id not in [
            "5000", "5001", "5002", "5003", "5004", "5005", "5006", "5007", "5008", "5009",
            "5010", "5011", "5012", "5013", "5014", "5015", "5016", "5017", "5018", "5019",
            "5020", "5021", "5022", "5023", "5024", "5025", "5026",
        ]:
            resp = res.json()
        else:
            pass

        # Final stream analysis before playback
        final_url = ""
        if channel_id in ["5016", "5017", "5023", "5024", "5025", "5026"]:
            final_url = url
            Script.log(f"[VOD-DEBUG] ZEE CHANNEL: Using hardcoded URL: {final_url}", lvl=Script.INFO)
        else:
            final_url = resp.get("result", "") if 'resp' in locals() else ""
            Script.log(f"[VOD-DEBUG] JIO CHANNEL: API result URL: {final_url}", lvl=Script.INFO)

        # Determine if this is actually VOD or live content
        if isCatchup:
            if "catchup" in final_url.lower() or "vod" in final_url.lower() or ("begin=" in final_url and "end=" in final_url):
                Script.log("[VOD-DEBUG] FINAL RESULT: SUCCESS - Playing VOD content", lvl=Script.INFO)
            elif "live" in final_url.lower() or "seek" in final_url.lower():
                Script.log("[VOD-DEBUG] FINAL RESULT: FAILURE - FELL BACK TO LIVE despite VOD request!", lvl=Script.ERROR)
            else:
                Script.log(f"[VOD-DEBUG] FINAL RESULT: UNKNOWN stream type: {final_url}", lvl=Script.WARNING)
        else:
            Script.log("[VOD-DEBUG] FINAL RESULT: Playing live stream as requested", lvl=Script.INFO)

        art = {}
        if channel_id not in [
            "5000", "5001", "5002", "5003", "5004", "5005", "5006", "5007", "5008", "5009",
            "5010", "5011", "5012", "5013", "5014", "5015", "5016", "5017", "5018", "5019",
            "5020", "5021", "5022", "5023", "5024", "5025", "5026",
        ]:
            onlyUrl = resp.get("result", "").split("?")[0].split("/")[-1]
        else:
            pass

        art["thumb"] = art["icon"] = IMG_CATCHUP + onlyUrl.replace(".m3u8", ".png")

        if channel_id in ["5016", "5017", "5023", "5024", "5025", "5026"]:
            cookie = url.split("?")[1] if "?hdntl=" in url else ""
            uriToUse = onlyUrl
        else:
            cookie = "__hdnea__" + resp.get("result", "").split("__hdnea__")[-1]
            uriToUse = resp.get("result", "")

        headers["cookie"] = cookie
        qltyopt = Settings.get_string("quality")
        selectionType = "adaptive"
        
        mpd_data = resp.get("mpd")
        isMpd = isinstance(mpd_data, dict) and mpd_data.get("result")
        cookie_str = ""

        if isMpd:
            uriToUse = mpd_data.get("result", "")
            if Settings.get_boolean("mpdnotice"):
                # Script.notify("Notice!", "Using MPD Stream", icon=Script.NOTIFY_INFO)
                pass
            
            # Fetch Cookies from MPD for License Request
            try:
                 mpd_resp = urlquick.head(uriToUse, headers={"User-Agent": "okhttp/4.2.2"}, verify=False, max_age=-1)
                 c_dict = mpd_resp.cookies.get_dict()
                 cookie_str = "; ".join([f"{k}={v}" for k, v in c_dict.items()])
                 Script.log(f"Fetched MPD Cookies: {cookie_str}", lvl=Script.INFO)
            except Exception as e:
                Script.log(f"Cookie fetch failed: {e}", lvl=Script.ERROR)

            license_headers = headers.copy()
            license_headers.update({
                "User-Agent": "PlayTV/1.0",
                "appName": "RJIL_JioTV",
                "x-platform": "android",
                "os": "android",
                "devicetype": "phone",
                "osVersion": "13",
                "srno": str(uuid4()),
                "channelid": str(channel_id),
                "usergroup": "tvYR7NSNn7rymo3F",
                "versionCode": "389",
                "Accept-Encoding": "gzip, deflate",
                "Content-Type": "application/octet-stream",
                "Accept": "*/*",
            })
            if "cookie" in license_headers:
                cookie_base = license_headers.pop("cookie")
                license_headers["Cookie"] = cookie_base + (f"; {cookie_str}" if cookie_str else "")
            elif cookie_str:
                license_headers["Cookie"] = cookie_str

            license_config = {
                "license_server_url": mpd_data.get("key", ""),
                "headers": urlencode(license_headers),
                "post_data": "H{SSM}",
                "response_data": "",
            }

        if qltyopt == "Ask-me":
            selectionType = "ask-quality"
        if qltyopt == "Manual":
            selectionType = "manual-osd"

        if not isMpd and not qltyopt == "Manual":
            m3u8Headers = {
                "user-agent": headers.get("user-agent", "jiotv"),
                "cookie": headers["cookie"],
                "content-type": "application/vnd.apple.mpegurl",
                "Accesstoken": headerssony["Accesstoken"],
            }
            if channel_id in [
                "5000", "5001", "5002", "5003", "5004", "5005", "5006", "5007", "5008", "5009",
                "5010", "5011", "5012", "5013", "5014", "5015", "5016", "5017", "5018", "5019",
                "5020", "5021", "5022", "5023", "5024", "5025", "5026",
            ]:
                m3u8Res = urlquick.get(
                    uriToUse, headers=headerszee, verify=False, max_age=-1, raise_for_status=True
                )
            else:
                m3u8Res = urlquick.get(
                    uriToUse, headers=m3u8Headers, verify=False, max_age=-1, raise_for_status=True
                )

            m3u8Headers = {k: str(v) for k, v in m3u8Headers.items() if v}
            m3u8String = m3u8Res.text
            variant_m3u8 = m3u8.loads(m3u8String)
            if variant_m3u8.is_variant and (variant_m3u8.version is None or variant_m3u8.version < 7):
                quality = quality_to_enum(qltyopt, len(variant_m3u8.playlists))
                tmpurl = variant_m3u8.playlists[quality].uri
                # For VOD content, allow adaptive streaming when Best quality is selected
                if isCatchup and qltyopt == "Best":
                    # Use adaptive streaming instead of selecting specific quality
                    pass  # Keep the master playlist for adaptive streaming
                else:
                    if "?" in tmpurl:
                        uriToUse = uriToUse.split("?")[0].replace(onlyUrl, tmpurl)
                    else:
                        uriToUse = uriToUse.replace(onlyUrl, tmpurl.split("?")[0])

        Script.log(uriToUse, lvl=Script.INFO)

        if channel_id in [
            "471", "154", "181", "182", "183", "289", "291", "483",
            "5000", "5001", "5002", "5003", "5004", "5005", "5006", "5007",
            "5008", "5009", "5010", "5011", "5012", "5013", "5014", "5015",
            "5016", "5017", "5018", "5019", "5020", "5021", "5022",
            "5023", "5024", "5025", "5026",
        ]:
            dialog = xbmcgui.DialogProgress()
            dialog.create("Loading Stream", "Please wait... buffering...")
            xbmc.sleep(5000)
            dialog.close()

            listitem = xbmcgui.ListItem(path=uriToUse)
            listitem.setProperty("IsPlayable", "true")
            listitem.setProperty("inputstream", "inputstream.adaptive")
            listitem.setProperty("inputstream.adaptive.manifest_type", "hls")

            if channel_id in [
                "5000", "5001", "5002", "5003", "5004", "5005", "5006", "5007", "5008", "5009",
                "5010", "5011", "5012", "5013", "5014", "5015", "5016", "5017", "5018", "5019",
                "5020", "5021", "5022", "5023", "5024", "5025", "5026",
            ]:
                listitem.setProperty("inputstream.adaptive.stream_headers", urlencode(headerszee))
                listitem.setProperty("inputstream.adaptive.manifest_headers", urlencode(headerszee))
            else:
                listitem.setProperty("inputstream.adaptive.stream_headers", urlencode(m3u8Headers))
                listitem.setProperty("inputstream.adaptive.manifest_headers", urlencode(m3u8Headers))

            listitem.setMimeType("application/vnd.apple.mpegurl")
            xbmcplugin.setResolvedUrl(handle=int(sys.argv[1]), succeeded=True, listitem=listitem)
            listitem.setContentLookup(False)

            sony_channels = [
                "154", "289", "291", "5001", "5002", "5003", "5004", "5005", "5006", "5007",
                "5008", "5009", "5010", "5011", "5012", "5013", "5014", "5015", "5016", "5017",
                "5018", "5019", "5020", "5021", "5022", "5023", "5024", "5025", "5026",
            ]
            callback_value = uriToUse if channel_id in sony_channels else None
            xbmc.Player().play(uriToUse, listitem)

            return Listitem().from_dict(
                **{"label": "Sony", "art": art, "callback": callback_value, "properties": {}}
            )
        else:
            pass

        props = {
            "IsPlayable": True,
            "inputstream": "inputstream.adaptive",
            "inputstream.adaptive.stream_selection_type": selectionType,
            "inputstream.adaptive.chooser_resolution_secure_max": "4k",
            "inputstream.adaptive.manifest_type": "mpd" if isMpd else "hls",
        }

        if isMpd:
            props["inputstream.adaptive.license_type"] = "com.widevine.alpha"
            props["inputstream.adaptive.license_key"] = (
                license_config.get("license_server_url", "") +
                "|" + urlencode(license_headers) + "|R{SSM}|"
            )
            
            # Headers for segment requests
            stream_headers = headers.copy()
            stream_headers["User-Agent"] = "okhttp/4.2.2"
            if "cookie" in stream_headers:
                cookie_base = stream_headers.pop("cookie")
                stream_headers["Cookie"] = cookie_base + (f"; {cookie_str}" if cookie_str else "")
            elif cookie_str:
                stream_headers["Cookie"] = cookie_str
            
            props["inputstream.adaptive.stream_headers"] = urlencode(stream_headers)
            props["inputstream.adaptive.manifest_headers"] = urlencode(stream_headers)
        else:
            props["inputstream.adaptive.stream_headers"] = urlencode(headers)
            props["inputstream.adaptive.manifest_headers"] = urlencode(headers)

        return Listitem().from_dict(
            **{
                "label": plugin._title,
                "art": art,
                "callback": uriToUse + "|verifypeer=false",
                "properties": props
            }
        )
    except Exception as e:
        Script.notify("headers - Error while playback , Check connection", e)
        return False


# Login `route` to access from Settings


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


# Logout `route` to access from Settings


@Script.register
def logout(plugin):
    ULogout()


# M3u Generate `route`
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
            continue  # 💡 Skip ZEE range from default block, handle separately below

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

    # ✅ Hardcoded ZEE channels JSON (you can import or load from file as needed)
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
            f'plugin://plugin.kodi.jiotv/resources/lib/main/play/?channel_id={cid}\n'
        )

    with open(M3U_SRC, "w+", encoding="utf-8") as f:
        f.write(m3ustr.replace("\xa0", " "))

    if notify == "yes":
        Script.notify("JioTV", "Playlist updated.")



# EPG Generate `route`
@Script.register
def epg_setup(plugin):
    Script.notify("Please wait", "Epg setup in progress")
    pDialog = DialogProgress()
    pDialog.create("Epg setup in progress")
    # Download EPG XML file
    url = Settings.get_string("epgurl")
    if not url or (len(url) < 5):
        url = "https://example.com/epg.xml.gz"
    payload = {}
    headers = {}
    response = requests.request("GET", url, headers=headers, data=payload)
    # source_tree = ET.parse(CHANNELS_XML)
    # source_root = source_tree.getroot()
    with open(EPG_PATH, "wb") as f:
        f.write(response.content)
        # for chunk in response.iter_content(chunk_size=1024):
        #     if chunk:
        #         f.write(chunk)
    # Extract and parse the XML file
    pDialog.update(20)
    with gzip.open(EPG_PATH, "rb") as f:
        data = f.read()
        xml_content = data.decode("utf-8")
        root = ET.fromstring(xml_content)
    # Modify all the programs in the EPG
    # programs = root.findall('./programme')
    pDialog.update(30)
    # for channel in root.iterfind("channel"):
    #     root.remove(channel)
    pDialog.update(35)
    # Example: Modify the program and add catchupid
    # for channel in source_root.iterfind('channel'):
    #     new_channel = ET.Element(channel.tag, channel.attrib)
    #     for child in channel:
    #         new_child = ET.Element(child.tag, child.attrib)
    #         new_child.text = child.text
    #         new_channel.append(new_child)
    #     root.append(new_channel)
    pDialog.update(45)
    for program in root.iterfind(".//programme"):
        # Example: Modify the program and add catchupid
        icon = program.find("icon")
        icon_src = icon.get("src")
        jpg_name = icon_src.rsplit("/", 1)[-1]
        catchup_id = os.path.splitext(jpg_name)[0]
        program.set("catchup-id", catchup_id)
        title = program.find("title")
        title.text = title.text.strip()
    pDialog.update(60)
    # create the XML declaration and add it to the top of the file
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'

    # create the doctype declaration
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


# PVR Setup `route` to access from Settings
@Script.register
def pvrsetup(plugin):
    executebuiltin("RunPlugin(plugin://plugin.kodi.jiotv/resources/lib/main/m3ugen/)")
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


# Cache cleanup
@Script.register
def cleanup(plugin):
    urlquick.cache_cleanup(-1)
    cleanLocalCache()
    Script.notify("Cache Cleaned", "")

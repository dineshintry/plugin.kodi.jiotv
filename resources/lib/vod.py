# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import datetime
from codequick import Route, Listitem, Script
from codequick.script import Settings
from resources.lib.constants import (
    IMG_CATCHUP,
    IMG_CATCHUP_SHOWS,
    IMG_CONFIG,
)
from resources.lib.utils import (
    getFeatured,
    getVODContent,
    getVODChannels,
    getChannelVODContent,
    getCachedDictionary,
)

# Delayed imports to avoid circular dependencies
def get_play_callback():
    from resources.lib.player import play
    return play

def get_download_vod_callback():
    from resources.lib.recorder import download_vod
    return download_vod

@Route.register
def show_featured(plugin, id=None):
    play = get_play_callback()
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
                    "callback": Route.ref("/resources/lib/vod:show_featured"),
                    "params": {"id": each.get("id")},
                }
            )


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
    
    # Show VOD channels if available
    if vod_channels:
        yield Listitem.from_dict(
            **{
                "label": "VOD Channels",
                "art": {
                    "thumb": IMG_CATCHUP_SHOWS + "cms/210528144026.jpg",
                    "icon": IMG_CATCHUP_SHOWS + "cms/210528144026.jpg",
                    "fanart": IMG_CATCHUP_SHOWS + "cms/210528144026.jpg",
                },
                "callback": Route.ref("/resources/lib/vod:show_vod_channels"),
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
                    "callback": Route.ref("/resources/lib/vod:show_vod_category"),
                    "params": {"category": cat_name},
                }
            )


@Route.register
def show_vod_category(plugin, category):
    play = get_play_callback()
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
            info_dict["callback"] = play
            info_dict["params"] = {
                "channel_id": channel_id,
                "showtime": datetime.fromtimestamp(int(item.get("startEpoch", 0)) // 1000).strftime("%H%M%S"),
                "srno": datetime.fromtimestamp(int(item.get("startEpoch", 0)) // 1000).strftime("%Y%m%d"),
                "programId": item.get("showId") if item.get("showId") else f"CHN-{channel_id}-PRG-{datetime.fromtimestamp(int(item.get('startEpoch', 0)) // 1000).strftime('%Y%m%d%H%M')}",
                "begin": datetime.utcfromtimestamp(int(item.get("startEpoch", 0)) // 1000).strftime("%Y%m%dT%H%M%S"),
                "end": datetime.utcfromtimestamp(int(item.get("endEpoch", 0)) // 1000).strftime("%Y%m%dT%H%M%S"),
            }
        else:
            info_dict["callback"] = ""
            info_dict["label"] += " [No channel info]"
        
        yield Listitem.from_dict(**info_dict)


@Route.register
def show_vod_channels(plugin):
    vod_channels = getVODChannels()
    dictionary = getCachedDictionary()
    LANG_MAP = dictionary.get("languageIdMapping")
    
    vod_by_language = {}
    for channel in vod_channels:
        lang_id = str(channel.get("channelLanguageId", ""))
        if lang_id in LANG_MAP:
            lang_name = LANG_MAP[lang_id]
            if lang_name not in vod_by_language:
                vod_by_language[lang_name] = []
            vod_by_language[lang_name].append(channel)
        else:
            if "Other" not in vod_by_language:
                vod_by_language["Other"] = []
            vod_by_language["Other"].append(channel)
    
    for lang_name, channels in sorted(vod_by_language.items()):
        if channels:
            yield Listitem.from_dict(
                **{
                    "label": f"{lang_name} [COLOR cyan][VOD][/COLOR]",
                    "art": {
                        "thumb": IMG_CONFIG["Languages"].get(lang_name, {}).get("tvImg", ""),
                        "icon": IMG_CONFIG["Languages"].get(lang_name, {}).get("tvImg", ""),
                        "fanart": IMG_CONFIG["Languages"].get(lang_name, {}).get("promoImg", ""),
                    },
                    "callback": Route.ref("/resources/lib/vod:show_vod_channels_by_language"),
                    "params": {"language": lang_name},
                }
            )
    
    if "Other" in vod_by_language and vod_by_language["Other"]:
        yield Listitem.from_dict(
            **{
                "label": f"Other [COLOR cyan][VOD][/COLOR]",
                "art": {
                    "thumb": IMG_CONFIG["Genres"].get("Other", {}).get("tvImg", ""),
                    "icon": IMG_CONFIG["Genres"].get("Other", {}).get("tvImg", ""),
                    "fanart": IMG_CONFIG["Genres"].get("Other", {}).get("promoImg", ""),
                },
                "callback": Route.ref("/resources/lib/vod:show_vod_channels_by_language"),
                "params": {"language": "Other"},
            }
        )


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
                    "callback": Route.ref("/resources/lib/vod:show_vod_channel_content"),
                    "params": {"channel_id": channel.get("channel_id", "")},
                }
            )


@Route.register
def show_vod_channel_content(plugin, channel_id, offset_days=None):
    play = get_play_callback()
    download_vod = get_download_vod_callback()
    if offset_days is not None:
        vod_content = getChannelVODContent(channel_id, offset_days)
        
        if not vod_content:
            yield Listitem.from_dict(
                **{
                    "label": f"No VOD content available for this channel ({offset_days if offset_days > 0 else 'today'})",
                    "callback": "",
                }
            )
            return
        
        for item in vod_content:
            start_epoch = item.get("startEpoch", 0)
            end_epoch = item.get("endEpoch", 0)
            
            if not start_epoch or not end_epoch or start_epoch <= 0 or end_epoch <= 0:
                continue
            
            try:
                start_time = datetime.fromtimestamp(int(start_epoch) // 1000)
                end_time = datetime.fromtimestamp(int(end_epoch) // 1000)
                timetext = f"  [{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}]"
            except (ValueError, OSError):
                timetext = ""
            
            current_time = datetime.now()
            time_diff = current_time - start_time
            
            if time_diff.days == 0:
                if time_diff.seconds < 3600:
                    time_ago = f"{time_diff.seconds // 60} minutes ago"
                else:
                    time_ago = f"{time_diff.seconds // 3600} hours ago"
            else:
                time_ago = f"{time_diff.days} days ago"
            
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
                    "showtime": datetime.fromtimestamp(int(item.get("startEpoch", 0)) // 1000).strftime("%H%M%S"),
                    "srno": datetime.fromtimestamp(int(item.get("startEpoch", 0)) // 1000).strftime("%Y%m%d"),
                    "programId": item.get("showId") if item.get("showId") else f"CHN-{channel_id}-PRG-{datetime.fromtimestamp(int(item.get('startEpoch', 0)) // 1000).strftime('%Y%m%d%H%M')}",
                    "begin": datetime.utcfromtimestamp(int(item.get("startEpoch", 0)) // 1000).strftime("%Y%m%dT%H%M%S"),
                    "end": datetime.utcfromtimestamp(int(item.get("endEpoch", 0)) // 1000).strftime("%Y%m%dT%H%M%S"),
                },
            }

            vod_item = Listitem.from_dict(**info_dict)
            params = {
                "channel_id": str(channel_id),
                "showtime": info_dict['params']['showtime'],
                "srno": info_dict['params']['srno'],
                "programId": info_dict['params']['programId'],
                "begin": info_dict['params']['begin'],
                "end": info_dict['params']['end'],
                "title": item.get("showname", "VOD Content")
            }
            # Standard Kodi context menu item: (label, action)
            # action = RunPlugin(plugin://plugin.kodi.jiotv/resources/lib/main/download_vod/?...)
            from urllib.parse import urlencode
            action = f"RunPlugin(plugin://plugin.kodi.jiotv/resources/lib/main/download_vod/?{urlencode(params)})"
            vod_item.context.append(("Download VOD", action))

            yield vod_item
    
    else:
        for days_ago in range(8):
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
                    "callback": Route.ref("/resources/lib/vod:show_vod_channel_content"),
                    "params": {"channel_id": channel_id, "offset_days": days_ago},
                }
            )

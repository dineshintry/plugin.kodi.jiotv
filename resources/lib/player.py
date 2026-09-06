# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sys
import m3u8
import xbmc
import xbmcgui
import xbmcplugin
import urlquick
import requests
import inputstreamhelper
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode, quote
from resources.lib import proxy
from codequick import Resolver, Script
from codequick.script import Settings
from resources.lib.constants import IMG_CATCHUP
from resources.lib.utils import (
    getHeaders,
    isLoggedIn,
    getSonyHeaders,
    getZeeHeaders,
    zeeCookie,
    quality_to_enum,
    getCachedChannels,
    get_session,
)

def probe_and_log_audio_streams(channel_id, channel_name, uri, manifest_type, manifest_text, headers=None):
    try:
        Script.log(f"==================== [AUDIO-PROBE START] Channel ID: {channel_id} | Name: {channel_name} | Type: {manifest_type} ====================", lvl=Script.INFO)
        Script.log(f"[AUDIO-PROBE] Manifest URL: {uri}", lvl=Script.INFO)

        if manifest_type.lower() == "hls":
            try:
                import m3u8
                parsed = m3u8.loads(manifest_text)
                
                Script.log("[AUDIO-PROBE][HLS] --- Raw Master Playlist ---", lvl=Script.INFO)
                for line in manifest_text.splitlines():
                    if line.strip():
                        Script.log(f"[AUDIO-PROBE][HLS][RAW] {line}", lvl=Script.INFO)

                audio_media = [m for m in parsed.media if m.type == "AUDIO"]
                Script.log(f"[AUDIO-PROBE][HLS] --- Audio Media Tracks Count: {len(audio_media)} ---", lvl=Script.INFO)
                if audio_media:
                    for i, m in enumerate(audio_media):
                        Script.log(
                            f"[AUDIO-PROBE][HLS][AUDIO-TRACK {i+1}] GroupID: {getattr(m, 'group_id', None)} | Name: {getattr(m, 'name', None)} | Language: {getattr(m, 'language', None)} | Default: {getattr(m, 'default', None)} | AutoSelect: {getattr(m, 'autoselect', None)} | Channels: {getattr(m, 'channels', None)} | URI: {getattr(m, 'uri', None)}",
                            lvl=Script.INFO
                        )
                        if getattr(m, 'uri', None):
                            audio_sub_uri = m.uri
                            if not audio_sub_uri.startswith("http"):
                                base_dir = uri.rsplit('/', 1)[0]
                                audio_sub_uri = f"{base_dir}/{audio_sub_uri}"
                            try:
                                sub_resp = get_session().get(audio_sub_uri, headers=headers, timeout=(3, 5))
                                if sub_resp.status_code == 200:
                                    Script.log(f"[AUDIO-PROBE][HLS][AUDIO-TRACK {i+1}-SUBPLAYLIST] Raw Content:", lvl=Script.INFO)
                                    for sub_line in sub_resp.text.splitlines():
                                        if sub_line.strip():
                                            Script.log(f"[AUDIO-PROBE][HLS][AUDIO-TRACK {i+1}-SUB] {sub_line}", lvl=Script.INFO)
                            except Exception as sub_err:
                                Script.log(f"[AUDIO-PROBE][HLS][AUDIO-TRACK {i+1}-SUBPLAYLIST] Fetch failed: {sub_err}", lvl=Script.INFO)
                else:
                    Script.log("[AUDIO-PROBE][HLS] No explicit #EXT-X-MEDIA:TYPE=AUDIO tracks found in master playlist.", lvl=Script.INFO)

                Script.log(f"[AUDIO-PROBE][HLS] --- Variant Playlists Count: {len(parsed.playlists)} ---", lvl=Script.INFO)
                for i, pl in enumerate(parsed.playlists):
                    stream_info = pl.stream_info
                    bw = getattr(stream_info, 'bandwidth', None)
                    res = getattr(stream_info, 'resolution', None)
                    codecs = getattr(stream_info, 'codecs', None)
                    audio_grp = getattr(stream_info, 'audio', None)
                    Script.log(
                        f"[AUDIO-PROBE][HLS][VARIANT {i+1}] Bandwidth: {bw} | Resolution: {res} | Codecs: {codecs} | AudioGroup: {audio_grp} | URI: {pl.uri}",
                        lvl=Script.INFO
                    )
            except Exception as e:
                Script.log(f"[AUDIO-PROBE][HLS] Error parsing HLS M3U8: {e}", lvl=Script.ERROR)

        elif manifest_type.lower() == "mpd":
            try:
                import xml.etree.ElementTree as ET
                Script.log("[AUDIO-PROBE][MPD] --- Raw MPD XML ---", lvl=Script.INFO)
                for line in manifest_text.splitlines():
                    if line.strip():
                        Script.log(f"[AUDIO-PROBE][MPD][RAW] {line}", lvl=Script.INFO)

                root_elem = ET.fromstring(manifest_text)
                adapt_sets = root_elem.findall(".//{*}AdaptationSet")
                Script.log(f"[AUDIO-PROBE][MPD] --- Total AdaptationSets found: {len(adapt_sets)} ---", lvl=Script.INFO)

                audio_set_count = 0
                for idx, aset in enumerate(adapt_sets):
                    content_type = aset.attrib.get("contentType", "")
                    mime_type = aset.attrib.get("mimeType", "")
                    lang = aset.attrib.get("lang", "")
                    group = aset.attrib.get("group", "")

                    reps = aset.findall(".//{*}Representation")
                    is_audio = ("audio" in content_type.lower()) or ("audio" in mime_type.lower())
                    if not is_audio:
                        for r in reps:
                            r_mime = r.attrib.get("mimeType", "").lower()
                            r_codecs = r.attrib.get("codecs", "").lower()
                            if "audio" in r_mime or r_codecs.startswith(("mp4a", "ac-3", "ec-3", "opus")):
                                is_audio = True
                                break

                    if is_audio:
                        audio_set_count += 1
                        Script.log(
                            f"[AUDIO-PROBE][MPD][AUDIO-ADAPTATION-SET {audio_set_count}] XML-Idx: {idx} | Group: {group} | Lang: {lang} | MimeType: {mime_type} | ContentType: {content_type}",
                            lvl=Script.INFO
                        )
                        for r_idx, r in enumerate(reps):
                            rep_id = r.attrib.get("id", "N/A")
                            bw = r.attrib.get("bandwidth", "N/A")
                            codecs = r.attrib.get("codecs", "N/A")
                            rate = r.attrib.get("audioSamplingRate", "N/A")
                            mime = r.attrib.get("mimeType", mime_type)

                            acc = r.find(".//{*}AudioChannelConfiguration")
                            channels_val = acc.attrib.get("value", "N/A") if acc is not None else "N/A"

                            Script.log(
                                f"   -> [AUDIO-PROBE][MPD][AUDIO-REP {r_idx+1}] ID: {rep_id} | Bandwidth: {bw} bps ({int(bw)//1000 if str(bw).isdigit() else 'N/A'} kbps) | Codecs: {codecs} | Mime: {mime} | SampleRate: {rate} Hz | Channels: {channels_val}",
                                lvl=Script.INFO
                            )

                if audio_set_count == 0:
                    Script.log("[AUDIO-PROBE][MPD] No dedicated Audio AdaptationSets detected in MPD XML.", lvl=Script.INFO)

            except Exception as e:
                Script.log(f"[AUDIO-PROBE][MPD] Error parsing MPD XML: {e}", lvl=Script.ERROR)

        Script.log(f"==================== [AUDIO-PROBE END] Channel ID: {channel_id} ====================", lvl=Script.INFO)
    except Exception as general_err:
        Script.log(f"[AUDIO-PROBE] General logging error: {general_err}", lvl=Script.ERROR)


@Resolver.register
@isLoggedIn
def play(plugin, channel_id, showtime=None, srno=None, programId=None, begin=None, end=None, languageId=None, is_extra=None, utc=None, utcend=None, **kwargs):
    channel_id = str(channel_id)
    Script.log(f"[VOD-DEBUG] PLAY function called with: channel_id={channel_id}, showtime={showtime}, srno={srno}, programId={programId}, begin={begin}, end={end}, is_extra={is_extra}, utc={utc}, utcend={utcend}, kwargs={kwargs}", lvl=Script.INFO)
    
    if is_extra == "true" or is_extra is True:
        from resources.lib.utils import getExtraChannels
        extra_channels = getExtraChannels()
        chan_data = None
        for c in extra_channels:
            if str(c.get("channel_id")) == str(channel_id):
                chan_data = c
                break
                
        if not chan_data:
            Script.notify("Play Error", "Extra channel not found.")
            return False
            
        uriToUse = chan_data.get("stream_url")
        logoUrl = chan_data.get("logoUrl", "")
        
        art = {
            "thumb": logoUrl,
            "icon": logoUrl,
            "fanart": logoUrl,
            "clearlogo": logoUrl,
            "clearart": logoUrl,
        }
        
        isMpd = uriToUse.split("?")[0].endswith(".mpd")
        
        props = {
            "IsPlayable": True,
            "inputstream": "inputstream.adaptive",
            "inputstream.adaptive.manifest_type": "mpd" if isMpd else "hls",
        }
        
        # Load custom KODIPROPs with automatic standard mappings for fallbacks
        custom_props = chan_data.get("properties", {})
        for pk, pv in custom_props.items():
            if pk == "inputstream.adaptive.license_type" and pv == "com.clearkey.alpha":
                props[pk] = "org.w3.clearkey"
            else:
                props[pk] = pv
        
        # Load custom headers
        custom_headers = chan_data.get("headers", {})
        if custom_headers:
            props["inputstream.adaptive.stream_headers"] = urlencode(custom_headers)
            props["inputstream.adaptive.manifest_headers"] = urlencode(custom_headers)

        if uriToUse and uriToUse.startswith("http"):
            try:
                ex_resp = get_session().get(uriToUse, headers=custom_headers, timeout=(5, 10))
                if ex_resp.status_code == 200:
                    probe_and_log_audio_streams(channel_id, chan_data.get("channel_name", "Extra Channel"), uriToUse, "mpd" if isMpd else "hls", ex_resp.text, headers=custom_headers)
            except Exception as ex_err:
                Script.log(f"[AUDIO-PROBE] Extra channel manifest fetch failed: {ex_err}", lvl=Script.WARNING)
            
        Script.log(f"[AUDIO-PROBE][PROPS] Extra Channel {channel_id} Properties: {props}", lvl=Script.INFO)
        from codequick import Listitem as CQListitem
        return CQListitem().from_dict(
            **{
                "label": plugin._title or chan_data.get("channel_name", "Extra Channel"),
                "art": art,
                "callback": uriToUse,
                "properties": props
            }
        )

    sony_headers = getSonyHeaders()
    try:
        is_helper = inputstreamhelper.Helper("mpd", drm="com.widevine.alpha")
        hasIs = is_helper.check_inputstream()
        if not hasIs:
            Script.log("[VOD-DEBUG] InputStream helper check failed", lvl=Script.ERROR)
            return

        channel_id_str = str(channel_id)

        now_utc = datetime.now(timezone.utc)
        ist_tz = timezone(timedelta(hours=5, minutes=30))

        start_dt = None
        end_dt = None

        # 1. Parse utc/utcend timestamps if provided by IPTV Simple
        if utc and str(utc).isdigit():
            try:
                start_dt = datetime.fromtimestamp(int(utc), tz=timezone.utc)
                if utcend and str(utcend).isdigit():
                    end_dt = datetime.fromtimestamp(int(utcend), tz=timezone.utc)
            except Exception as e:
                Script.log(f"[VOD] Error parsing utc/utcend timestamps: {e}", lvl=Script.WARNING)

        # 2. Parse begin/end if provided as ISO strings
        if not start_dt and begin and isinstance(begin, str) and len(begin) >= 15:
            try:
                start_dt = datetime.strptime(begin[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
            except Exception:
                pass
        if not end_dt and end and isinstance(end, str) and len(end) >= 15:
            try:
                end_dt = datetime.strptime(end[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
            except Exception:
                pass

        # 3. Derive start/end datetimes from srno + showtime if still missing
        if (not start_dt or not end_dt) and showtime and srno:
            try:
                showtime_clean = str(showtime).replace(":", "")[:6].zfill(6)
                srno_str = str(srno)
                if srno_str.startswith("20") and len(srno_str) >= 8 and srno_str[:8].isdigit():
                    date_part = srno_str[:8]
                elif len(srno_str) >= 6 and srno_str[:6].isdigit():
                    date_part = "20" + srno_str[:6]
                else:
                    date_part = now_utc.astimezone(ist_tz).strftime("%Y%m%d")

                start_ist = datetime.strptime(f"{date_part}{showtime_clean}", "%Y%m%d%H%M%S").replace(tzinfo=ist_tz)
                if not start_dt:
                    start_dt = start_ist.astimezone(timezone.utc)
                if not end_dt:
                    # Default duration 30 minutes if end time is unknown
                    end_dt = start_dt + timedelta(minutes=30)
            except Exception as e:
                Script.log(f"[VOD] Error deriving times from srno/showtime: {e}", lvl=Script.WARNING)

        # Ensure begin & end strings are populated if datetimes are available
        if start_dt and not begin:
            begin = start_dt.strftime("%Y%m%dT%H%M%S")
        if end_dt and not end:
            end = end_dt.strftime("%Y%m%dT%H%M%S")

        # Determine if programme is currently on air (live) or in the future
        is_currently_live = False
        if end_dt and end_dt > now_utc:
            is_currently_live = True
        elif start_dt and start_dt <= now_utc and (now_utc - start_dt).total_seconds() < 1800:
            # Started recently within 30 mins
            is_currently_live = True

        stream_type = "Seek"
        rjson = {"channel_id": int(channel_id), "stream_type": stream_type}
        isCatchup = False

        if showtime and srno and not is_currently_live:
            isCatchup = True
            rjson["showtime"] = str(showtime).replace(":", "")[:6]
            rjson["srno"] = str(srno)
            rjson["stream_type"] = "Catchup"
            # Ensure programId is a valid non-empty string for JioTV API
            clean_program_id = programId
            if not clean_program_id or clean_program_id == "{catchup-id}":
                clean_program_id = f"PROG-{channel_id}-{rjson['srno']}"
            rjson["programId"] = clean_program_id
            rjson["begin"] = begin
            rjson["end"] = end

            headers = getHeaders()
            headers["channelid"] = str(channel_id)
            headers["srno"] = rjson["srno"]
            headers["showtime"] = rjson["showtime"]

            Script.log(f"[VOD-DEBUG] VOD REQUEST DETECTED: stream_type=Catchup, params={rjson}", lvl=Script.INFO)
        else:
            if is_currently_live:
                Script.log(f"[VOD-DEBUG] CURRENT PROGRAMME ON AIR (end_dt={end_dt}, now={now_utc}): Switching to live stream (stream_type=Seek)", lvl=Script.INFO)
            else:
                Script.log(f"[VOD-DEBUG] LIVE STREAM REQUEST: stream_type=Seek (no VOD params provided)", lvl=Script.INFO)

            headers = getHeaders()
            headers["channelid"] = str(channel_id)
            headers["srno"] = str(uuid4())

        zee_channels = {
            "5016": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105525/ZeeAnmolCinemaELE/master.m3u8",
            "5017": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105527/ZeeActionELE/master.m3u8",
            "5023": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105261/ZEECHITRAMANDIRELE/master.m3u8",
            "5024": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105526/ZeeAnmolELE/master.m3u8",
            "5025": "https://z5live-cf.zee5.com/out/v1/ZEE5_Live_Channels/Zee-Ganga-Zee-Anmol-Cinema-2-SD/master/master.m3u8",
            "5026": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105176/BigMagicELE/master.m3u8",
        }


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
            base_url = zee_channels[channel_id]
            onlyUrl = f"{base_url}{cook}"
            url = onlyUrl

        else:
            chan = str(channel_id)
            langId = str(languageId) if languageId else ""
            if not langId:
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
            
            api_params = {
                "stream_type": rjson['stream_type'],
                "channel_id": chan
            }
            if isCatchup:
                api_params.update({
                    "srno": rjson.get('srno', ''),
                    "programId": rjson.get('programId', '') or "",
                    "begin": rjson.get('begin', ''),
                    "end": rjson.get('end', ''),
                    "showtime": rjson.get('showtime', '')
                })

            # Use a hard thread-level timeout for the API call.
            # On Android TV via hotspot, socket-level timeouts don't work —
            # TCP connects but TLS/HTTP hangs indefinitely. A thread timeout
            # ensures we always get a result within the deadline.
            import threading
            import time as _time

            _api_url = "https://jiotvapi.media.jio.com/playback/apis/v1.1/geturl"
            _api_result = [None]  # mutable container for thread result
            _api_error = [None]

            def _do_api_call(session_to_use):
                try:
                    _api_result[0] = session_to_use.post(
                        _api_url, data=api_params, headers=sony_headers,
                        timeout=(10, 15)
                    )
                except Exception as e:
                    _api_error[0] = e

            # Attempt 1: use persistent session (fast if TLS is cached)
            t_start = _time.time()
            Script.log(f"[PLAY] API call starting (attempt 1)...", lvl=Script.INFO)
            api_thread = threading.Thread(target=_do_api_call, args=(get_session(),))
            api_thread.daemon = True
            api_thread.start()
            api_thread.join(timeout=20)  # Hard 20s deadline

            if api_thread.is_alive() or _api_result[0] is None:
                elapsed = _time.time() - t_start
                Script.log(f"[PLAY] API call attempt 1 failed/timed out after {elapsed:.1f}s, retrying with fresh session...", lvl=Script.ERROR)

                # Attempt 2: fresh session (new TLS connection)
                _api_result[0] = None
                _api_error[0] = None
                fresh_session = requests.Session()
                fresh_session.verify = False
                t_start = _time.time()
                api_thread2 = threading.Thread(target=_do_api_call, args=(fresh_session,))
                api_thread2.daemon = True
                api_thread2.start()
                api_thread2.join(timeout=25)  # 25s for fresh connection

                if api_thread2.is_alive() or _api_result[0] is None:
                    elapsed = _time.time() - t_start
                    err_msg = str(_api_error[0]) if _api_error[0] else "Connection timed out"
                    Script.log(f"[PLAY] API call attempt 2 also failed after {elapsed:.1f}s: {err_msg}", lvl=Script.ERROR)
                    Script.notify("Connection Failed", "JioTV API unreachable. Try WiFi or retry.")
                    return False

            if _api_error[0]:
                Script.log(f"[PLAY] API error: {_api_error[0]}", lvl=Script.ERROR)
                Script.notify("Connection Error", str(_api_error[0])[:100])
                return False

            res = _api_result[0]
            elapsed = _time.time() - t_start
            Script.log(f"[PLAY] API call completed in {elapsed:.1f}s, status={res.status_code}", lvl=Script.INFO)

            if res.status_code != 200:
                Script.log(f"VOD API Error: {res.status_code} - {res.text}", lvl=Script.ERROR)
                # If Catchup request failed with 400 Bad Request, automatically fall back to live Seek stream
                if isCatchup and res.status_code == 400:
                    Script.log(f"[PLAY] Catchup API returned 400 for channel {chan}. Automatically falling back to live stream (Seek)...", lvl=Script.WARNING)
                    isCatchup = False
                    rjson["stream_type"] = "Seek"
                    api_params = {
                        "stream_type": "Seek",
                        "channel_id": chan
                    }
                    _api_result[0] = None
                    _api_error[0] = None
                    _do_api_call(get_session())
                    if _api_result[0] is not None and _api_result[0].status_code == 200:
                        res = _api_result[0]
                        Script.log("[PLAY] Fallback to live stream succeeded (status=200)", lvl=Script.INFO)

                if res.status_code != 200:
                    if res.status_code in (401, 419):
                        raise Exception(f"HTTP Error {res.status_code}: Token expired or unauthorized")
                    err_msg = ""
                    try:
                        err_msg = res.json().get("message", "")
                    except Exception:
                        pass
                    if "Sony Srno data is not mapped" in err_msg:
                        Script.notify("Catchup Unavailable", "SET catchup is unmapped on JioTV (exclusive to SonyLIV).")
                    elif err_msg:
                        Script.notify("Playback Error", err_msg)
                    else:
                        Script.notify("Playback Error", f"API returned {res.status_code}")
                    return False

            api_response = res.json()
            result_url = api_response.get("result", "")

            sonyheaders = sony_headers
            sonyheaders["cookie"] = "__hdnea__" + res.json().get("result", "").split("__hdnea__")[-1]
            sonyheaders.setdefault("user-agent", "jiotv")
            sonyheaders = {k: str(v) for k, v in sonyheaders.items() if v}

        if channel_id not in [
            "5000", "5001", "5002", "5003", "5004", "5005", "5006", "5007", "5008", "5009",
            "5010", "5011", "5012", "5013", "5014", "5015", "5016", "5017", "5018", "5019",
            "5020", "5021", "5022", "5023", "5024", "5025", "5026",
        ]:
            resp = res.json()
        
        final_url = ""
        if channel_id in ["5016", "5017", "5023", "5024", "5025", "5026"]:
            final_url = url
        else:
            final_url = resp.get("result", "") if 'resp' in locals() else ""

        art = {}
        if channel_id not in [
            "5000", "5001", "5002", "5003", "5004", "5005", "5006", "5007", "5008", "5009",
            "5010", "5011", "5012", "5013", "5014", "5015", "5016", "5017", "5018", "5019",
            "5020", "5021", "5022", "5023", "5024", "5025", "5026",
        ]:
            onlyUrl = resp.get("result", "").split("?")[0].split("/")[-1]
        else:
            onlyUrl = final_url.split("?")[0].split("/")[-1]

        art["thumb"] = art["icon"] = IMG_CATCHUP + onlyUrl.replace(".m3u8", ".png")

        if channel_id in ["5016", "5017", "5023", "5024", "5025", "5026"]:
            cookie = url.split("?")[1] if "?hdntl=" in url else ""
            uriToUse = final_url
        else:
            cookie = "__hdnea__" + resp.get("result", "").split("__hdnea__")[-1]
            uriToUse = resp.get("result", "")

        if "paywall" in uriToUse.lower():
            Script.log(f"[PLAY] Subscription paywall detected in URL: {uriToUse}", lvl=Script.ERROR)
            xbmcgui.Dialog().ok(
                "Subscription Required",
                "This channel requires an active JioTV subscription. Please recharge to a valid JioTV subscription plan (e.g., JioTV Pro pack or OTT pass) to get this content loading."
            )
            return False

        headers["cookie"] = cookie
        qltyopt = Settings.get_string("quality")
        selectionType = "adaptive"
        
        mpd_data = resp.get("mpd") if 'resp' in locals() else None
        isMpd = isinstance(mpd_data, dict) and mpd_data.get("result")
        
        hls_channels = [
            "5000", "5001", "5002", "5003", "5004", "5005", "5006", "5007",
            "5008", "5009", "5010", "5011", "5012", "5013", "5014", "5015",
            "5016", "5017", "5018", "5019", "5020", "5021", "5022",
            "5023", "5024", "5025", "5026",
        ]
        if channel_id in hls_channels:
            isMpd = False

        cookie_str = ""

        if isMpd:
            uriToUse = mpd_data.get("result", "")
            try:
                # Clear persistent session cookies for the CDN domain to force a fresh cookie response,
                # ensuring connection reuse (TCP/TLS) remains active while preventing empty responses on subsequent plays.
                get_session().cookies.clear()

                # Fetch cookies directly on the main thread using GET stream=True.
                # This is highly robust, prevents race conditions, and works across all CDNs.
                mpd_resp = get_session().get(
                    uriToUse,
                    headers={"User-Agent": "plaYtv/7.1.5 (Linux;Android 9) ExoPlayerLib/2.11.7"},
                    timeout=(10, 15),
                    stream=True,
                    allow_redirects=True
                )
                if mpd_resp.status_code == 404:
                    mpd_resp.close()
                    Script.log(f"[PLAY] MPD manifest returned 404 Not Found from CDN: {uriToUse}", lvl=Script.ERROR)
                    if isCatchup:
                        Script.notify("Catchup Unavailable", "This program is not available in JioTV archive.")
                    else:
                        Script.notify("Playback Error", "Stream manifest not found (404).")
                    return False
                elif mpd_resp.status_code >= 400:
                    mpd_resp.close()
                    Script.log(f"[PLAY] MPD manifest returned HTTP {mpd_resp.status_code} from CDN: {uriToUse}", lvl=Script.ERROR)
                    Script.notify("Playback Error", f"CDN returned HTTP {mpd_resp.status_code}")
                    return False

                mpd_text = mpd_resp.text
                c_dict = {}
                c_dict.update(get_session().cookies.get_dict())
                c_dict.update(mpd_resp.cookies.get_dict())
                cookie_str = "; ".join([f"{k}={v}" for k, v in c_dict.items()])
                mpd_resp.close()
                Script.log(f"[MPD] Cookies fetched: {cookie_str}", lvl=Script.INFO)
                probe_and_log_audio_streams(channel_id, plugin._title or f"Channel {channel_id}", uriToUse, "mpd", mpd_text)
            except Exception as e:
                Script.log(f"Cookie fetch failed: {e}", lvl=Script.ERROR)

            # Construct license headers
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
            if cookie_str:
                license_headers["Cookie"] = cookie_str
            elif "__hdnea__" in uriToUse:
                token = "__hdnea__" + uriToUse.split("__hdnea__")[-1]
                license_headers["Cookie"] = token

            license_config = {
                "license_server_url": mpd_data.get("key", ""),
                "headers": urlencode(license_headers),
                "post_data": "H{SSM}",
            }

        if qltyopt == "Ask-me":
            selectionType = "ask-quality"
        if qltyopt == "Manual":
            selectionType = "manual-osd"

        if not isMpd:
            m3u8Headers = {
                "user-agent": headers.get("user-agent", "jiotv"),
                "cookie": headers["cookie"],
                "content-type": "application/vnd.apple.mpegurl",
                "Accesstoken": sony_headers.get("Accesstoken", ""),
            }

        if not isMpd and not qltyopt == "Manual":

            # Thread-timed M3U8 fetch — urlquick hangs on Android hotspot
            _m3u8_result = [None]
            _m3u8_error = [None]
            def _fetch_m3u8():
                try:
                    if channel_id in [
                        "5000", "5001", "5002", "5003", "5004", "5005", "5006", "5007", "5008", "5009",
                        "5010", "5011", "5012", "5013", "5014", "5015", "5016", "5017", "5018", "5019",
                        "5020", "5021", "5022", "5023", "5024", "5025", "5026",
                    ]:
                        _m3u8_result[0] = get_session().get(
                            uriToUse, headers=headerszee, timeout=(5, 15)
                        )
                    else:
                        _m3u8_result[0] = get_session().get(
                            uriToUse, headers=m3u8Headers, timeout=(5, 15)
                        )
                except Exception as e:
                    _m3u8_error[0] = e

            m3u8_thread = threading.Thread(target=_fetch_m3u8)
            m3u8_thread.daemon = True
            m3u8_thread.start()
            m3u8_thread.join(timeout=20)

            if m3u8_thread.is_alive() or _m3u8_result[0] is None:
                err = str(_m3u8_error[0]) if _m3u8_error[0] else "Timed out"
                Script.log(f"[PLAY] M3U8 fetch failed: {err}", lvl=Script.ERROR)
                Script.notify("Stream Error", "CDN unreachable. Try WiFi or retry.")
                return False

            m3u8Res = _m3u8_result[0]
            if m3u8Res.status_code == 404:
                Script.log(f"[PLAY] M3U8 manifest returned 404 Not Found from CDN: {uriToUse}", lvl=Script.ERROR)
                if isCatchup:
                    Script.notify("Catchup Unavailable", "This program is not available in JioTV archive.")
                else:
                    Script.notify("Playback Error", "Stream manifest not found (404).")
                return False
            m3u8Res.raise_for_status()

            m3u8Headers = {k: str(v) for k, v in m3u8Headers.items() if v}
            m3u8String = m3u8Res.text
            probe_and_log_audio_streams(channel_id, plugin._title or f"Channel {channel_id}", uriToUse, "hls", m3u8String, headers=m3u8Headers)
            variant_m3u8 = m3u8.loads(m3u8String)
            if variant_m3u8.is_variant and (variant_m3u8.version is None or variant_m3u8.version < 7):
                quality = quality_to_enum(qltyopt, len(variant_m3u8.playlists))
                tmpurl = variant_m3u8.playlists[quality].uri
                if isCatchup and qltyopt == "Best":
                    pass
                else:
                    if "?" in tmpurl:
                        uriToUse = uriToUse.split("?")[0].replace(onlyUrl, tmpurl)
                    else:
                        uriToUse = uriToUse.replace(onlyUrl, tmpurl.split("?")[0])

        if channel_id in hls_channels:
            props = {
                "IsPlayable": True,
                "inputstream": "inputstream.adaptive",
                "inputstream.adaptive.manifest_type": "hls",
            }

            if channel_id in [
                "5000", "5001", "5002", "5003", "5004", "5005", "5006", "5007", "5008", "5009",
                "5010", "5011", "5012", "5013", "5014", "5015", "5016", "5017", "5018", "5019",
                "5020", "5021", "5022", "5023", "5024", "5025", "5026",
            ]:
                props["inputstream.adaptive.stream_headers"] = urlencode(headerszee)
                props["inputstream.adaptive.manifest_headers"] = urlencode(headerszee)
            else:
                props["inputstream.adaptive.stream_headers"] = urlencode(m3u8Headers)
                props["inputstream.adaptive.manifest_headers"] = urlencode(m3u8Headers)

            Script.log(f"[AUDIO-PROBE][PROPS] Channel {channel_id} (HLS) Properties: {props}", lvl=Script.INFO)
            from codequick import Listitem as CQListitem
            return CQListitem().from_dict(
                **{
                    "label": plugin._title,
                    "art": art,
                    "callback": uriToUse,
                    "properties": props
                }
            )
        else:
            pass

        props = {
            "IsPlayable": True,
            "inputstream": "inputstream.adaptive",
            "inputstream.adaptive.stream_selection_type": selectionType,
            "inputstream.adaptive.max_resolution": "1080",
            "inputstream.adaptive.manifest_type": "mpd" if isMpd else "hls",
        }

        if isMpd:
            props["inputstream.adaptive.license_type"] = "com.widevine.alpha"
            props["inputstream.adaptive.license_key"] = (
                license_config.get("license_server_url", "") +
                "|" + urlencode(license_headers) + "|R{SSM}|"
            )
            
            stream_headers = {
                    "User-Agent": "plaYtv/7.1.5 (Linux;Android 9) ExoPlayerLib/2.11.7"
            }
            if cookie_str:
                stream_headers["Cookie"] = cookie_str
            elif "__hdnea__" in uriToUse:
                token = "__hdnea__" + uriToUse.split("__hdnea__")[-1]
                stream_headers["Cookie"] = token
            
            # Set mimetype property to bypass CCurlFile::Stat metadata/size sniff checks
            props["mimetype"] = "application/dash+xml"
            
            sh = urlencode(stream_headers)
            mh = urlencode(stream_headers)
        else:
            sh = urlencode(headers)
            mh = urlencode(headers)

        props["inputstream.adaptive.stream_headers"] = sh
        props["inputstream.adaptive.manifest_headers"] = mh

        callback_uri = uriToUse
        if isMpd:
            proxy_port = getattr(proxy, 'PROXY_PORT', 48996)
            proxy_mpd_url = f"http://127.0.0.1:{proxy_port}/manifest.mpd?url={quote(uriToUse)}"
            if cookie_str:
                proxy_mpd_url += f"&cookie={quote(cookie_str)}"
            callback_uri = proxy_mpd_url
            Script.log(f"[PLAY] Using proxy manifest URL for DASH: {callback_uri}", lvl=Script.INFO)

        from codequick import Listitem as CQListitem
            
        return CQListitem().from_dict(
            **{
                "label": plugin._title,
                "art": art,
                "callback": callback_uri,
                "properties": props
            }
        )
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        Script.log(f"[PLAY] Network timeout/connection error: {e}", lvl=Script.ERROR)
        Script.notify("Connection Timeout", "Network too slow or JioTV blocked. Try without hotspot.")
        return False
    except Exception as e:
        if "419" in str(e) or "401" in str(e):
            raise e
        Script.log(f"[PLAY] Playback error: {e}", lvl=Script.ERROR)
        Script.notify("Playback Error", str(e)[:100])
        return False

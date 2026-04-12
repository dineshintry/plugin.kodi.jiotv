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
from urllib.parse import urlencode
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

@Resolver.register
@isLoggedIn
def play(plugin, channel_id, showtime=None, srno=None, programId=None, begin=None, end=None, languageId=None):
    Script.log(f"[VOD-DEBUG] PLAY function called with: channel_id={channel_id}, showtime={showtime}, srno={srno}, programId={programId}, begin={begin}, end={end}", lvl=Script.INFO)
    Script.log("[VOD-DEBUG] Please enable Kodi debug logging manually for VOD playback analysis", lvl=Script.INFO)

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

        if showtime and srno:
            isCatchup = True
            rjson["showtime"] = showtime
            rjson["srno"] = srno
            rjson["stream_type"] = "Catchup"
            rjson["programId"] = programId
            rjson["begin"] = begin
            rjson["end"] = end
            
            headers = getHeaders()
            headers["channelid"] = str(channel_id)
            headers["srno"] = rjson["srno"]
            headers["showtime"] = rjson["showtime"]
            
            Script.log(f"[VOD-DEBUG] VOD REQUEST DETECTED: stream_type=Catchup, params={rjson}", lvl=Script.INFO)
        else:
            Script.log(f"[VOD-DEBUG] LIVE STREAM REQUEST: stream_type=Seek (no VOD params provided)", lvl=Script.INFO)

            headers = getHeaders()
            headers["channelid"] = str(channel_id)
            headers["srno"] = rjson["srno"] if isCatchup else str(uuid4())

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

        headers["cookie"] = cookie
        qltyopt = Settings.get_string("quality")
        selectionType = "adaptive"
        
        mpd_data = resp.get("mpd") if 'resp' in locals() else None
        isMpd = isinstance(mpd_data, dict) and mpd_data.get("result")
        cookie_str = ""

        if isMpd:
            uriToUse = mpd_data.get("result", "")
            try:
                # Use thread-timed request — urlquick.head() hangs forever
                # on Android hotspot because CDN domain is unreachable
                _mpd_result = [None]
                _mpd_error = [None]
                def _fetch_mpd_cookies():
                    try:
                        _mpd_result[0] = get_session().head(
                            uriToUse,
                            headers={"User-Agent": "plaYtv/7.1.5 (Linux;Android 9) ExoPlayerLib/2.11.7"},
                            timeout=(5, 10),
                            allow_redirects=True
                        )
                    except Exception as e:
                        _mpd_error[0] = e

                mpd_thread = threading.Thread(target=_fetch_mpd_cookies)
                mpd_thread.daemon = True
                mpd_thread.start()
                mpd_thread.join(timeout=15)

                if mpd_thread.is_alive() or _mpd_result[0] is None:
                    err = str(_mpd_error[0]) if _mpd_error[0] else "Timed out"
                    raise Exception(f"CDN unreachable ({err})")

                mpd_resp = _mpd_result[0]
                c_dict = mpd_resp.cookies.get_dict()
                cookie_str = "; ".join([f"{k}={v}" for k, v in c_dict.items()])
                Script.log(f"[MPD] Cookies fetched: {cookie_str}", lvl=Script.INFO)
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
            if cookie_str:
                license_headers["Cookie"] = cookie_str

            license_config = {
                "license_server_url": mpd_data.get("key", ""),
                "headers": urlencode(license_headers),
                "post_data": "H{SSM}",
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
                "Accesstoken": sony_headers.get("Accesstoken", ""),
            }

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
            m3u8Res.raise_for_status()

            m3u8Headers = {k: str(v) for k, v in m3u8Headers.items() if v}
            m3u8String = m3u8Res.text
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

        if channel_id in [
            "471", "154", "181", "182", "183", "289", "291", "483",
            "5000", "5001", "5002", "5003", "5004", "5005", "5006", "5007",
            "5008", "5009", "5010", "5011", "5012", "5013", "5014", "5015",
            "5016", "5017", "5018", "5019", "5020", "5021", "5022",
            "5023", "5024", "5025", "5026",
        ]:
            # Removed forced 5s buffering sleep to improve loading speed

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

            xbmc.Player().play(uriToUse, listitem)
            return True
        else:
            pass

        props = {
            "IsPlayable": True,
            "inputstream": "inputstream.adaptive",
            "inputstream.adaptive.stream_selection_type": selectionType,
            "inputstream.adaptive.chooser_resolution_secure_max": "1080",
            "inputstream.adaptive.max_resolution": "1080",
            "inputstream.adaptive.manifest_type": "mpd" if isMpd else "hls",
        }

        if isMpd:
            props["inputstream.adaptive.license_type"] = "com.widevine.alpha"
            props["inputstream.adaptive.license_key"] = (
                license_config.get("license_server_url", "") +
                "|" + urlencode(license_headers) + "|R{SSM}|"
            )
            
            stream_headers = headers.copy()
            stream_headers["User-Agent"] = "plaYtv/7.1.5 (Linux;Android 9) ExoPlayerLib/2.11.7"
            if cookie_str:
                stream_headers["Cookie"] = cookie_str
            
            # Ensure __hdnea__ token is present in headers if extracted from URL
            if "__hdnea__" in uriToUse:
                token = "__hdnea__" + uriToUse.split("__hdnea__")[-1]
                if cookie_str:
                    stream_headers["Cookie"] = f"{cookie_str}; {token}"
                else:
                    stream_headers["Cookie"] = token
            
            sh = urlencode(stream_headers)
            mh = urlencode(stream_headers)
        else:
            sh = urlencode(headers)
            mh = urlencode(headers)

        props["inputstream.adaptive.stream_headers"] = sh
        props["inputstream.adaptive.manifest_headers"] = mh

        from codequick import Listitem as CQListitem
            
        return CQListitem().from_dict(
            **{
                "label": plugin._title,
                "art": art,
                "callback": uriToUse,
                "properties": props
            }
        )
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        Script.log(f"[PLAY] Network timeout/connection error: {e}", lvl=Script.ERROR)
        Script.notify("Connection Timeout", "Network too slow or JioTV blocked. Try without hotspot.")
        return False
    except Exception as e:
        Script.log(f"[PLAY] Playback error: {e}", lvl=Script.ERROR)
        Script.notify("Playback Error", str(e)[:100])
        return False

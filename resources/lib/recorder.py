# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import subprocess
import threading
import time
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlencode, urljoin, urlparse, parse_qs, urlunparse
from uuid import uuid4

import inputstreamhelper
import m3u8
import requests
import urlquick
import xbmc
import xbmcgui
import xbmcvfs
from codequick import Script
from codequick.utils import keyboard
from xbmcgui import Dialog

from resources.lib.constants import (
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
)
from resources.lib.utils import (
    getHeaders,
    isLoggedIn,
    login as ULogin,
    logout as ULogout,
    check_addon,
    sendOTPV2,
    get_local_ip,
    getSonyHeaders,
    getZeeHeaders,
    zeeCookie,
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

def resolve_and_merge_query(base_url, relative_url):
    """
    Resolve a relative URL against a base URL and merge their query parameters.
    Ensures that parameters from the base URL (like tokens) are preserved
    even if the relative URL has its own parameters.
    """
    parsed_base = urlparse(base_url)
    # Resolve the path relative to the base URL
    full_resolved_url = urljoin(base_url, relative_url)
    parsed_resolved = urlparse(full_resolved_url)
    
    # Merge queries: base params + relative params
    base_query = parse_qs(parsed_base.query)
    rel_query = parse_qs(parsed_resolved.query)
    
    # Start with base query params
    merged_query = base_query.copy()
    # Update with relative query params (relative wins on conflict)
    merged_query.update(rel_query)
    
    # Use safe='=/*~+@:' to prevent urlencode from corrupting the __hdnea__ CDN tokens
    # which contain these characters in their values and fail validation if encoded.
    new_query_str = urlencode(merged_query, doseq=True, safe='=/*~+@:')
    
    return urlunparse((
        parsed_resolved.scheme,
        parsed_resolved.netloc,
        parsed_resolved.path,
        parsed_resolved.params,
        new_query_str,
        parsed_resolved.fragment
    ))


def get_stream_url_for_recording(channel_id, showtime=None, srno=None, programId=None, begin=None, end=None):
    """
    Get stream URL for recording purposes without starting playback.
    Returns the final stream URL that can be used for ffmpeg recording.
    """
    Script.log(f"[RECORDING] Getting stream URL for channel_id={channel_id}, showtime={showtime}", lvl=Script.INFO)

    # Reuse the same logic as play function but return URL instead of playing
    headerssony = getSonyHeaders()
    sony_headers = getSonyHeaders()
    try:
        is_helper = inputstreamhelper.Helper("mpd", drm="com.widevine.alpha")
        hasIs = is_helper.check_inputstream()
        if not hasIs:
            Script.log("[RECORDING] InputStream helper check failed", lvl=Script.ERROR)
            return None

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

            headers = getHeaders()
            headers["channelid"] = str(channel_id)
            headers["srno"] = rjson["srno"]
            headers["showtime"] = rjson["showtime"]
        else:
            headers = getHeaders()
            headers["channelid"] = str(channel_id)
            headers["srno"] = rjson["srno"] if isCatchup else str(uuid4())

        # Handle ZEE channels
        zee_channels = {
            "5016": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105525/ZeeAnmolCinemaELE/master.m3u8",
            "5017": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105527/ZeeActionELE/master.m3u8",
            "5023": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105261/ZEECHITRAMANDIRELE/master.m3u8",
            "5024": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105526/ZeeAnmolELE/master.m3u8",
            "5025": "https://z5live-cf.zee5.com/out/v1/ZEE5_Live_Channels/Zee-Ganga-Zee-Anmol-Cinema-2-SD/master/master.m3u8",
            "5026": "https://z5ak-cmaflive.zee5.com/cmaf/live/2105176/BigMagicELE/master.m3u8",
        }

        sony_headers = getSonyHeaders()

        if channel_id_str in zee_channels:
            if channel_id_str == "5016":
                zee_channelid = "0-9-zeeanmolcinema"
                host = "z5ak-cmaflive.zee5.com"
            elif channel_id_str == "5017":
                zee_channelid = "0-9-zeeaction"
                host = "z5ak-cmaflive.zee5.com"
            elif channel_id_str == "5023":
                zee_channelid = "0-9-394"
                host = "z5ak-cmaflive.zee5.com"
            elif channel_id_str == "5024":
                zee_channelid = "0-9-zeeanmol"
                host = "z5ak-cmaflive.zee5.com"
            elif channel_id_str == "5025":
                zee_channelid = "0-9-bigganga"
                host = "z5live-cf.zee5.com"
            elif channel_id_str == "5026":
                zee_channelid = "0-9-bigmagic_1786965389"
                host = "z5ak-cmaflive.zee5.com"
            else:
                zee_channelid = None

            cook = zeeCookie(zee_channelid)
            headerszee = getZeeHeaders(host)
            headerszee.pop("Host", None)
            base_url = zee_channels[channel_id_str]
            onlyUrl = f"{base_url}{cook}"
            return onlyUrl, headerszee

        else:
            # Get language ID for Sony channels
            langId = ""
            try:
                channels = getCachedChannels()
                if channels:
                    for c in channels:
                        if str(c.get("channel_id")) == str(channel_id):
                            langId = str(c.get("channelLanguageId", ""))
                            break
            except Exception as e:
                Script.log(f"[RECORDING] Error fetching language ID: {e}", lvl=Script.ERROR)

            sony_headers = getSonyHeaders(channel_id=str(channel_id), languageId=langId)

            api_data = f"stream_type={rjson['stream_type']}&channel_id={str(channel_id)}"

            if isCatchup:
                api_data += f"&srno={rjson.get('srno', '')}"
                api_data += f"&programId={rjson.get('programId', '')}"
                api_data += f"&begin={rjson.get('begin', '')}"
                api_data += f"&end={rjson.get('end', '')}"
                api_data += f"&showtime={rjson.get('showtime', '')}"

            Script.log(f"[RECORDING] API call data: {api_data}", lvl=Script.INFO)

            res = urlquick.post(
                "https://jiotvapi.media.jio.com/playback/apis/v1.1/geturl",
                data=api_data,
                verify=False,
                headers=sony_headers,
                max_age=-1,
            )

            api_response = res.json()
            result_url = api_response.get("result", "")
            Script.log(f"[RECORDING] API result URL: {result_url}", lvl=Script.INFO)

            # Get the final URL
            final_url = api_response.get("result", "")
            
            # Extract cookie for Sony
            if "__hdnea__" in final_url:
                sony_headers["cookie"] = "__hdnea__" + final_url.split("__hdnea__")[-1]
            
            sony_headers.setdefault("user-agent", "jiotv")
            sony_headers.pop("Host", None)
            sony_headers.pop("Content-Type", None)
            sony_headers.pop("Content-Length", None)

            # Parse M3U8 if needed
            if final_url and not isCatchup:
                try:
                    m3u8Headers = sony_headers.copy()
                    m3u8Headers.update({
                        "content-type": "application/vnd.apple.mpegurl",
                    })

                    m3u8Res = urlquick.get(
                        final_url, headers=m3u8Headers, verify=False, max_age=-1, raise_for_status=True
                    )

                    m3u8String = m3u8Res.text
                    variant_m3u8 = m3u8.loads(m3u8String)
                    if variant_m3u8.is_variant:
                        # Use best quality for recording
                        best_playlist = variant_m3u8.playlists[-1]
                        final_url = resolve_and_merge_query(final_url, best_playlist.uri)
                except Exception as e:
                    Script.log(f"[RECORDING] Error parsing M3U8: {e}", lvl=Script.WARNING)

            Script.log(f"[RECORDING] Final stream URL: {final_url}", lvl=Script.INFO)
            return final_url, sony_headers

    except Exception as e:
        Script.log(f"[RECORDING] Error getting stream URL: {e}", lvl=Script.ERROR)
        return None, None


def record_stream(stream_url, output_path, duration=None, headers=None):
    """
    Record a stream using ffmpeg and save as MP4.
    duration: recording duration in seconds (None for VOD/full download)
    headers: dict of headers to pass to ffmpeg
    """
    try:
        # Build ffmpeg command
        cmd = ['ffmpeg', '-y']  # -y to overwrite output file

        # Add headers if provided
        if headers:
            header_str = ""
            for key, value in headers.items():
                header_str += f"{key}: {value}\r\n"
            cmd.extend(['-headers', header_str])


        # Add timeout to prevent hanging (in microseconds, 30s = 30000000)
        cmd.extend(['-timeout', '30000000'])

        # Input stream
        cmd.extend(['-i', stream_url])

        # Copy codecs (no re-encoding for speed and compatibility)
        cmd.extend(['-c', 'copy'])

        # Set duration if specified
        if duration:
            cmd.extend(['-t', str(duration)])

        # Output file
        cmd.append(output_path)

        Script.log(f"[RECORDING] Starting ffmpeg with command: {' '.join(cmd)}", lvl=Script.INFO)

        # Run ffmpeg
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        # Monitor progress in a separate thread
        def monitor_progress():
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    Script.log(f"[RECORDING] ffmpeg: {output.strip()}", lvl=Script.DEBUG)

        monitor_thread = threading.Thread(target=monitor_progress)
        monitor_thread.daemon = True
        monitor_thread.start()

        # Wait for completion
        process.wait()

        if process.returncode == 0:
            Script.log(f"[RECORDING] Successfully recorded to: {output_path}", lvl=Script.INFO)
            return True
        else:
            Script.log(f"[RECORDING] ffmpeg failed with return code: {process.returncode}", lvl=Script.ERROR)
            return False

    except Exception as e:
        Script.log(f"[RECORDING] Error during recording: {e}", lvl=Script.ERROR)
        return False


def download_segment(session, url, headers, segment_index, temp_dir):
    """
    Download a specific M3U8 segment using a persistent session.
    """
    try:
        start_time = time.time()
        response = session.get(url, headers=headers, stream=True, timeout=20)
        response.raise_for_status()
        
        segment_file = os.path.join(temp_dir, f'segment_{segment_index:04d}.ts')
        total_bytes = 0
        with open(segment_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=32768):
                if chunk:
                    f.write(chunk)
                    total_bytes += len(chunk)
        
        duration = time.time() - start_time
        speed = (total_bytes / 1024) / duration if duration > 0 else 0
        Script.log(f"[DOWNLOAD] Seg {segment_index} done: {total_bytes/1024:.1f}KB in {duration:.2f}s ({speed:.1f} KB/s)", lvl=Script.DEBUG)
        return segment_file
    except Exception as e:
        Script.log(f"[DOWNLOAD] Error downloading segment {segment_index}: {e}", lvl=Script.ERROR)
        raise


def dash_widevine_download(url, output_path, headers=None, num_threads=16):
    """
    Download DASH stream with Widevine DRM decryption.
    Extracts PSSH from MPD, fetches license, and decrypts segments.
    """
    try:
        if headers is None:
            headers = {}

        # Import required modules
        import base64
        import struct
        import xml.etree.ElementTree as ET
        
        Script.log("[DASH] Starting DASH Widevine download", lvl=Script.INFO)

        # Fetch MPD manifest
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        mpd_content = response.text

        # Parse MPD to extract PSSH and content info
        root = ET.fromstring(mpd_content)
        
        # Extract content_id from URL parameters or MPD
        from urllib.parse import parse_qs, urlparse
        parsed_url = urlparse(url)
        url_params = parse_qs(parsed_url.query)
        content_id = url_params.get('content_id', [None])[0]
        
        if not content_id:
            # Try to extract from MPD
            for elem in root.iter():
                if 'content_id' in elem.attrib:
                    content_id = elem.attrib['content_id']
                    break

        if not content_id:
            Script.log("[DASH] Could not extract content_id", lvl=Script.ERROR)
            return False

        # Extract PSSH from MPD
        pssh_data = None
        for elem in root.iter():
            if elem.tag.endswith('ContentProtection') and elem.attrib.get('schemeIdUri') == 'urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed':
                pssh_elem = elem.find('{urn:mpeg:cenc:2013}pssh')
                if pssh_elem is not None and pssh_elem.text:
                    pssh_data = pssh_elem.text
                    break

        if not pssh_data:
            Script.log("[DASH] No PSSH found in MPD", lvl=Script.ERROR)
            return False

        # Get license URL and headers
        license_url, license_headers = get_widevine_license_info(
            channel_id=headers.get('channelid', ''),
            showtime=headers.get('showtime', ''),
            srno=headers.get('srno', ''),
            programId=content_id
        )

        if not license_url:
            Script.log("[DASH] Could not get license URL", lvl=Script.ERROR)
            return False

        # Fetch Widevine license
        Script.log(f"[DASH] Fetching license from: {license_url}", lvl=Script.INFO)
        license_response = requests.post(
            license_url,
            headers=license_headers,
            data=base64.b64decode(pssh_data),
            timeout=10
        )
        license_response.raise_for_status()
        
        # Extract content keys from license response
        # Note: This requires Widevine CDM or pywidevine library
        # For now, save license for external processing
        license_file = output_path.replace('.mp4', '.license')
        with open(license_file, 'wb') as f:
            f.write(license_response.content)
        
        Script.log(f"[DASH] License saved to: {license_file}", lvl=Script.INFO)
        Script.log("[DASH] Note: Actual decryption requires Widevine CDM - saved for external processing", lvl=Script.WARNING)

        # Download audio and video segments (encrypted)
        # This is a simplified version - full implementation would parse MPD properly
        segments_dir = output_path.replace('.mp4', '_segments')
        os.makedirs(segments_dir, exist_ok=True)

        # Find segment URLs in MPD
        segment_urls = []
        for elem in root.iter():
            if elem.tag.endswith('Representation'):
                for media_elem in elem.iter():
                    if media_elem.tag.endswith('BaseURL') or media_elem.tag.endswith('SegmentURL'):
                        seg_url = media_elem.attrib.get('media', media_elem.attrib.get('href', ''))
                        if seg_url:
                            if not seg_url.startswith('http'):
                                base_url = url.rsplit('/', 1)[0]
                                seg_url = f"{base_url}/{seg_url}"
                            segment_urls.append(seg_url)

        if not segment_urls:
            Script.log("[DASH] No segments found in MPD", lvl=Script.ERROR)
            return False

        Script.log(f"[DASH] Found {len(segment_urls)} segments", lvl=Script.INFO)

        # Download segments
        downloaded_segments = []
        for i, seg_url in enumerate(segment_urls):
            try:
                seg_response = requests.get(seg_url, headers=headers, timeout=20)
                seg_response.raise_for_status()
                
                seg_file = os.path.join(segments_dir, f'segment_{i:04d}.mp4')
                with open(seg_file, 'wb') as f:
                    f.write(seg_response.content)
                downloaded_segments.append(seg_file)
                
                Script.log(f"[DASH] Downloaded segment {i+1}/{len(segment_urls)}", lvl=Script.DEBUG)
            except Exception as e:
                Script.log(f"[DASH] Failed to download segment {i}: {e}", lvl=Script.ERROR)

        Script.log(f"[DASH] Downloaded {len(downloaded_segments)} encrypted segments to: {segments_dir}", lvl=Script.INFO)
        Script.log(f"[DASH] Use external tool with license file to decrypt and combine", lvl=Script.INFO)
        
        return True

    except Exception as e:
        Script.log(f"[DASH] Error in Widevine download: {e}", lvl=Script.ERROR)
        return False


def hls_segment_download(url, output_path, headers=None, num_threads=16):
    """
    Download an HLS (M3U8) stream by downloading segments in parallel.
    Also downloads the AES-128 encryption key and saves a local M3U8 playlist.
    Segments are saved to a persistent folder for manual processing if ffmpeg fails.
    Works on all platforms (Windows, Linux, macOS, Android).
    """
    try:
        if headers is None:
            headers = {}

        # Create a persistent folder for this VOD's segments
        # Use the output filename (without extension) as the folder name
        base_name = os.path.splitext(os.path.basename(output_path))[0]
        segments_dir = os.path.join(os.path.dirname(output_path), base_name + '_segments')
        os.makedirs(segments_dir, exist_ok=True)
        Script.log(f"[DOWNLOAD] Segments folder: {segments_dir}", lvl=Script.INFO)

        # Fetch the M3U8 playlist
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        content = response.text

        playlist = m3u8.loads(content)

        # If it's a master/variant playlist, pick the best quality
        if playlist.is_variant:
            Script.log("[DOWNLOAD] Master playlist detected, picking best variant", lvl=Script.INFO)
            best_playlist = playlist.playlists[-1]  # Highest quality
            variant_url = resolve_and_merge_query(url, best_playlist.uri)
            Script.log(f"[DOWNLOAD] Best variant URL: {variant_url[:100]}...", lvl=Script.INFO)

            # Fetch the media playlist
            response = requests.get(variant_url, headers=headers, timeout=10)
            response.raise_for_status()
            content = response.text
            playlist = m3u8.loads(content)
            url = variant_url  # Update base URL for segment resolution

        if not playlist.segments:
            Script.log("[DOWNLOAD] No segments in M3U8 playlist", lvl=Script.ERROR)
            return False

        total_segments = len(playlist.segments)
        Script.log(f"[DOWNLOAD] Found {total_segments} segments to download", lvl=Script.INFO)

        # Download encryption key(s) if present
        # Extract __hdnea__ token for cookie-based auth (this is how Kodi's InputStream.Adaptive works)
        hdnea_cookie = ""
        if '?' in url:
            try:
                url_parsed = urlparse(url)
                url_qs = parse_qs(url_parsed.query)
                if '__hdnea__' in url_qs:
                    hdnea_cookie = "__hdnea__=" + url_qs['__hdnea__'][0]
                elif '__hdnea__' in url:
                    hdnea_cookie = "__hdnea__" + url.split("__hdnea__")[-1].split("&")[0]
            except Exception:
                if '__hdnea__' in url:
                    hdnea_cookie = "__hdnea__" + url.split("__hdnea__")[-1].split("&")[0]

        if hdnea_cookie:
            Script.log(f"[DOWNLOAD] Extracted __hdnea__ cookie for key auth ({len(hdnea_cookie)} chars)", lvl=Script.INFO)

        key_files = {}  # Maps original key URI -> local filename
        for key in playlist.keys:
            if key and key.uri and key.uri not in key_files:
                # Build multiple candidate key URLs to try
                key_urls_to_try = []

                # Determine the original absolute key URL
                if key.uri.startswith('http'):
                    original_key_url = key.uri
                else:
                    original_key_url = urljoin(url, key.uri)

                # Strategy 1: Original key URI with NO extra query params
                # (InputStream.Adaptive uses cookie auth, not URL params)
                key_parsed = urlparse(original_key_url)
                clean_key_url = urlunparse((key_parsed.scheme, key_parsed.netloc, key_parsed.path, '', '', ''))
                if clean_key_url != original_key_url:
                    key_urls_to_try.append(("Clean URL (no query)", clean_key_url))

                # Strategy 2: Rewrite fallback host to CDN host with ONLY __hdnea__ token (no vbegin/vend)
                if 'tv.media.jio.com/fallback' in original_key_url or 'tv.media.jio.com' in original_key_url:
                    try:
                        base_parsed = urlparse(url)
                        key_p = urlparse(original_key_url)
                        # Strip /fallback from path
                        clean_path = key_p.path.replace('/fallback', '')
                        # Only include __hdnea__ from base URL, skip vbegin/vend
                        base_qs = parse_qs(base_parsed.query)
                        filtered_params = {}
                        for k, v in base_qs.items():
                            if k in ('__hdnea__',):
                                filtered_params[k] = v[0]
                        if filtered_params:
                            qs = urlencode(filtered_params, safe='=/*~+@:')
                            cdn_key_url = f"{base_parsed.scheme}://{base_parsed.netloc}{clean_path}?{qs}"
                        else:
                            cdn_key_url = f"{base_parsed.scheme}://{base_parsed.netloc}{clean_path}"
                        key_urls_to_try.append(("CDN rewrite (hdnea only)", cdn_key_url))
                        Script.log(f"[DOWNLOAD] Rewrote fallback key to CDN URL with auth tokens", lvl=Script.INFO)
                    except Exception as e:
                        Script.log(f"[DOWNLOAD] Warning: Failed to rewrite key URL: {e}", lvl=Script.WARNING)

                # Strategy 3: CDN host with full query params from stream URL
                if 'tv.media.jio.com' in original_key_url:
                    try:
                        base_parsed = urlparse(url)
                        key_p = urlparse(original_key_url)
                        clean_path = key_p.path.replace('/fallback', '')
                        cdn_full_url = f"{base_parsed.scheme}://{base_parsed.netloc}{clean_path}?{base_parsed.query}"
                        key_urls_to_try.append(("CDN rewrite (full query)", cdn_full_url))
                    except Exception:
                        pass

                # Strategy 4: Original key URL as-is (maybe with merged query from resolve)
                merged_key_url = resolve_and_merge_query(url, key.uri)
                if merged_key_url not in [u for _, u in key_urls_to_try]:
                    key_urls_to_try.append(("Merged query URL", merged_key_url))

                # Strategy 5: Original key URL exactly as in M3U8
                if original_key_url not in [u for _, u in key_urls_to_try]:
                    key_urls_to_try.append(("Original URL", original_key_url))

                Script.log(f"[DOWNLOAD] Will try {len(key_urls_to_try)} key URL strategies", lvl=Script.INFO)

                # Build header sets to try for each URL
                # Cookie-based auth (matching how InputStream.Adaptive/Kodi player works)
                cookie_headers = {
                    "user-agent": "jiotv",
                    "cookie": hdnea_cookie or headers.get("cookie", ""),
                }
                cookie_headers = {k: v for k, v in cookie_headers.items() if v}

                player_headers = {
                    "user-agent": headers.get("user-agent", "jiotv"),
                    "cookie": hdnea_cookie or headers.get("cookie", ""),
                    "content-type": "application/vnd.apple.mpegurl",
                    "Accesstoken": headers.get("Accesstoken", "")
                }
                player_headers = {k: v for k, v in player_headers.items() if v}

                header_sets = [
                    ("Cookie auth", cookie_headers),
                    ("Player headers", player_headers),
                    ("Full headers", headers),
                    ("JioTV API headers", getHeaders()),
                    ("Minimal headers", {"user-agent": "jiotv"}),
                ]

                key_downloaded = False
                for url_name, try_key_url in key_urls_to_try:
                    if key_downloaded:
                        break
                    for header_name, try_headers in header_sets:
                        if key_downloaded:
                            break
                        try:
                            if not try_headers:
                                continue
                            Script.log(f"[DOWNLOAD] Trying key: {url_name} + {header_name} -> {try_key_url[:100]}...", lvl=Script.INFO)
                            key_response = requests.get(try_key_url, headers=try_headers, timeout=10, verify=False)
                            key_response.raise_for_status()
                            if len(key_response.content) == 16:  # AES-128 key is exactly 16 bytes
                                key_filename = f"key_{len(key_files)}.key"
                                key_path = os.path.join(segments_dir, key_filename)
                                with open(key_path, 'wb') as f:
                                    f.write(key_response.content)
                                key_files[key.uri] = key_filename
                                Script.log(f"[DOWNLOAD] SUCCESS: Saved key to {key_path} (16 bytes) via {url_name} + {header_name}", lvl=Script.INFO)
                                key_downloaded = True
                            else:
                                Script.log(f"[DOWNLOAD] Key response unexpected size: {len(key_response.content)} bytes (expected 16) via {url_name} + {header_name}", lvl=Script.WARNING)
                        except Exception as e:
                            Script.log(f"[DOWNLOAD] Key failed: {url_name} + {header_name}: {e}", lvl=Script.WARNING)

                if not key_downloaded:
                    Script.log(f"[DOWNLOAD] Could not download encryption key after all strategies", lvl=Script.ERROR)
                    Script.log("[DOWNLOAD] Will save segments anyway - encrypted but preserved", lvl=Script.WARNING)

        # Build segment URLs
        segments = []
        for i, segment in enumerate(playlist.segments):
            seg_url = resolve_and_merge_query(url, segment.uri)
            segments.append((seg_url, i))

        # Download segments in parallel with progress reporting
        pDialog = xbmcgui.DialogProgress()
        pDialog.create("Downloading VOD", "Preparing segments...")

        completed_segments = 0
        segment_files = [None] * total_segments
        failed_segments = []

        # Use a session for better performance
        session = requests.Session()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            future_to_idx = {
                executor.submit(download_segment, session, seg_url, headers, idx, segments_dir): idx
                for seg_url, idx in segments
            }

            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    segment_files[idx] = future.result()
                    completed_segments += 1
                    percent = int((completed_segments / total_segments) * 100)
                    pDialog.update(percent, f"Downloaded {completed_segments}/{total_segments} segments")

                    if pDialog.iscanceled():
                        Script.log("[DOWNLOAD] Download canceled by user", lvl=Script.INFO)
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                except Exception as e:
                    failed_segments.append(idx)
                    Script.log(f"[DOWNLOAD] Segment {idx} failed: {e}", lvl=Script.ERROR)

        pDialog.close()

        if pDialog.iscanceled():
            Script.notify("Download Canceled", f"Partial segments saved to: {segments_dir}")
            return False

        if failed_segments:
            Script.log(f"[DOWNLOAD] {len(failed_segments)} segments failed to download", lvl=Script.ERROR)

        actual_segments = [f for f in segment_files if f is not None]
        Script.log(f"[DOWNLOAD] Downloaded {len(actual_segments)}/{total_segments} segments", lvl=Script.INFO)

        if not actual_segments:
            Script.log("[DOWNLOAD] No segments were downloaded", lvl=Script.ERROR)
            return False

        # Save a local M3U8 playlist pointing to local files
        local_m3u8_path = os.path.join(segments_dir, 'playlist.m3u8')
        try:
            with open(local_m3u8_path, 'w', newline='\n') as f:
                f.write('#EXTM3U\n')
                f.write('#EXT-X-VERSION:3\n')
                if playlist.target_duration:
                    f.write(f'#EXT-X-TARGETDURATION:{playlist.target_duration}\n')

                last_key_uri = None  # Track to avoid writing duplicate key tags

                for i, segment in enumerate(playlist.segments):
                    if segment_files[i] is None:
                        continue

                    # Write key tag when the key changes (key rotation)
                    if segment.key and segment.key.uri and segment.key.uri != last_key_uri:
                        last_key_uri = segment.key.uri
                        local_key = key_files.get(segment.key.uri, '')
                        if local_key:
                            # Key was downloaded - reference local file
                            iv_str = f',IV={segment.key.iv}' if segment.key.iv else ''
                            f.write(f'#EXT-X-KEY:METHOD={segment.key.method},URI="{local_key}"{iv_str}\n')
                        else:
                            # Key download failed - skip the key tag to treat as unencrypted
                            Script.log(f"[DOWNLOAD] Key not available, skipping EXT-X-KEY tag - treating segments as unencrypted", lvl=Script.WARNING)

                    # Write segment info
                    if segment.duration:
                        f.write(f'#EXTINF:{segment.duration},\n')
                    else:
                        f.write('#EXTINF:6.0,\n')

                    # Use just the filename (relative path)
                    seg_filename = os.path.basename(segment_files[i])
                    f.write(f'{seg_filename}\n')

                f.write('#EXT-X-ENDLIST\n')

            Script.log(f"[DOWNLOAD] Saved local M3U8 playlist to: {local_m3u8_path}", lvl=Script.INFO)
        except Exception as e:
            Script.log(f"[DOWNLOAD] Error saving local M3U8: {e}", lvl=Script.WARNING)

        # Also save the original M3U8 for reference
        try:
            original_m3u8_path = os.path.join(segments_dir, 'original_playlist.m3u8')
            with open(original_m3u8_path, 'w', newline='\n') as f:
                f.write(content)
            Script.log(f"[DOWNLOAD] Saved original M3U8 to: {original_m3u8_path}", lvl=Script.INFO)
        except Exception as e:
            Script.log(f"[DOWNLOAD] Error saving original M3U8: {e}", lvl=Script.WARNING)

        # Try ffmpeg with the local M3U8 (which has local key references)
        Script.log("[DOWNLOAD] Attempting ffmpeg mux using local M3U8 playlist...", lvl=Script.INFO)
        try:
            # Use forward slashes for ffmpeg compatibility on all platforms
            safe_m3u8 = local_m3u8_path.replace('\\', '/')
            safe_output = output_path.replace('\\', '/')

            cmd = [
                'ffmpeg', '-y',
                '-protocol_whitelist', 'file,http,https,tcp,tls,crypto',
                '-allowed_extensions', 'ALL',
                '-i', safe_m3u8,
                '-c', 'copy',
                '-bsf:a', 'aac_adtstoasc',
                safe_output
            ]

            Script.log(f"[DOWNLOAD] ffmpeg command: {' '.join(cmd)}", lvl=Script.INFO)

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                cwd=segments_dir  # Set working dir so relative paths in M3U8 work
            )
            stdout, stderr = process.communicate(timeout=300)  # 5 min timeout for muxing

            if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                Script.log(f"[DOWNLOAD] Successfully created MP4: {output_path} ({file_size_mb:.1f} MB)", lvl=Script.INFO)

                # Clean up segments folder on success
                import shutil
                shutil.rmtree(segments_dir, ignore_errors=True)
                return True
            else:
                Script.log(f"[DOWNLOAD] ffmpeg local mux failed (code {process.returncode})", lvl=Script.ERROR)
                if stderr:
                    Script.log(f"[DOWNLOAD] ffmpeg stderr: {stderr[-500:]}", lvl=Script.ERROR)

                # FALLBACK: Try ffmpeg directly with the remote URL + cookie auth
                # ffmpeg's HTTP client can handle AES-128 key downloads with cookies
                Script.log("[DOWNLOAD] Trying ffmpeg direct download from remote URL with cookie auth...", lvl=Script.INFO)
                try:
                    direct_cmd = ['ffmpeg', '-y']

                    # Build header string with cookie for key auth
                    ffmpeg_headers = ""
                    if hdnea_cookie:
                        ffmpeg_headers += f"Cookie: {hdnea_cookie}\r\n"
                    ffmpeg_headers += "User-Agent: jiotv\r\n"
                    if headers.get("Accesstoken"):
                        ffmpeg_headers += f"Accesstoken: {headers['Accesstoken']}\r\n"

                    if ffmpeg_headers:
                        direct_cmd.extend(['-headers', ffmpeg_headers])

                    direct_cmd.extend([
                        '-i', url,
                        '-c', 'copy',
                        '-bsf:a', 'aac_adtstoasc',
                        safe_output
                    ])

                    Script.log(f"[DOWNLOAD] ffmpeg direct command: {' '.join(direct_cmd[:6])}... {safe_output}", lvl=Script.INFO)

                    direct_process = subprocess.Popen(
                        direct_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                    )
                    d_stdout, d_stderr = direct_process.communicate(timeout=600)  # 10 min for remote download

                    if direct_process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                        Script.log(f"[DOWNLOAD] ffmpeg direct download SUCCESS: {output_path} ({file_size_mb:.1f} MB)", lvl=Script.INFO)
                        import shutil
                        shutil.rmtree(segments_dir, ignore_errors=True)
                        return True
                    else:
                        Script.log(f"[DOWNLOAD] ffmpeg direct download also failed (code {direct_process.returncode})", lvl=Script.ERROR)
                        if d_stderr:
                            Script.log(f"[DOWNLOAD] ffmpeg direct stderr: {d_stderr[-500:]}", lvl=Script.ERROR)
                except subprocess.TimeoutExpired:
                    direct_process.kill()
                    Script.log("[DOWNLOAD] ffmpeg direct download timed out", lvl=Script.ERROR)
                except Exception as e2:
                    Script.log(f"[DOWNLOAD] ffmpeg direct download error: {e2}", lvl=Script.ERROR)

                # DON'T clean up - keep segments for manual processing
                Script.log(f"[DOWNLOAD] Segments preserved at: {segments_dir}", lvl=Script.INFO)
                Script.log(f"[DOWNLOAD] Local M3U8 playlist: {local_m3u8_path}", lvl=Script.INFO)
                Script.log("[DOWNLOAD] You can manually process these with: ffmpeg -i playlist.m3u8 -c copy output.mp4", lvl=Script.INFO)
                Script.notify("Download", f"Segments saved to: {segments_dir}\nUse ffmpeg manually to convert.")
                return False

        except subprocess.TimeoutExpired:
            process.kill()
            Script.log("[DOWNLOAD] ffmpeg mux timed out", lvl=Script.ERROR)
            Script.log(f"[DOWNLOAD] Segments preserved at: {segments_dir}", lvl=Script.INFO)
            Script.notify("Download", f"ffmpeg timed out. Segments at: {segments_dir}")
            return False
        except Exception as e:
            Script.log(f"[DOWNLOAD] ffmpeg mux error: {e}", lvl=Script.ERROR)
            Script.log(f"[DOWNLOAD] Segments preserved at: {segments_dir}", lvl=Script.INFO)
            Script.notify("Download", f"Mux failed. Segments at: {segments_dir}")
            return False

    except Exception as e:
        Script.log(f"[DOWNLOAD] Error in HLS segment download: {e}", lvl=Script.ERROR)
        return False


def multi_threaded_download(url, output_path, headers=None, num_threads=16, channel_info=None):
    """
    Download file using the best available method.
    For M3U8/HLS streams: downloads segments in parallel, saves locally, then muxes with ffmpeg.
    For direct files: uses multi-threaded range-request download.
    """
    try:
        # Prepare headers
        if headers is None:
            headers = {}

        # Check if it's an M3U8 playlist
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            content = response.text

            if '#EXTM3U' in content:
                Script.log("[DOWNLOAD] Detected M3U8 playlist, using segment download approach", lvl=Script.INFO)
                return hls_segment_download(url, output_path, headers, num_threads)
            elif '<MPD' in content or 'mpegdash+xml' in response.headers.get('content-type', ''):
                Script.log("[DOWNLOAD] Detected DASH manifest, using Widevine download approach", lvl=Script.INFO)
                return dash_widevine_download(url, output_path, headers, num_threads)

        except Exception as e:
            Script.log(f"[DOWNLOAD] Error checking manifest type: {e}, trying direct download", lvl=Script.WARNING)

        # For non-M3U8 URLs: Try direct file download with range requests
        Script.log("[DOWNLOAD] Attempting direct file download with range requests", lvl=Script.INFO)

        # Check if server supports range requests
        head_response = requests.head(url, headers=headers, timeout=10)
        if 'Accept-Ranges' not in head_response.headers or head_response.headers['Accept-Ranges'] != 'bytes':
            Script.log("[DOWNLOAD] Server does not support range requests, falling back to single-threaded download", lvl=Script.WARNING)
            return single_threaded_download(url, output_path, headers)

        content_length = int(head_response.headers.get('Content-Length', 0))
        if content_length == 0:
            Script.log("[DOWNLOAD] Could not get content length, falling back to single-threaded download", lvl=Script.WARNING)
            return single_threaded_download(url, output_path, headers)

        Script.log(f"[DOWNLOAD] Starting multi-threaded download of {content_length} bytes using {num_threads} threads", lvl=Script.INFO)

        # Create temp directory for chunks
        temp_dir = output_path + '.temp_chunks'
        os.makedirs(temp_dir, exist_ok=True)

        # Calculate chunk sizes
        chunk_size = content_length // num_threads
        chunks = []
        for i in range(num_threads):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < num_threads - 1 else content_length - 1
            chunks.append((start, end, i))

        # Download chunks in parallel
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            def download_chunk(url, start, end, headers, idx, temp_dir):
                dl_headers = headers.copy()
                dl_headers['Range'] = f'bytes={start}-{end}'
                response = requests.get(url, headers=dl_headers, stream=True, timeout=20)
                response.raise_for_status()
                chunk_file = os.path.join(temp_dir, f'chunk_{idx:04d}.tmp')
                with open(chunk_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=32768):
                        if chunk:
                            f.write(chunk)
                return chunk_file

            futures = [executor.submit(download_chunk, url, start, end, headers, idx, temp_dir) for start, end, idx in chunks]

            # Wait for all downloads to complete
            chunk_files = []
            for future in futures:
                try:
                    chunk_files.append(future.result())
                except Exception as e:
                    Script.log(f"[DOWNLOAD] Chunk download failed: {e}", lvl=Script.ERROR)
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return False

        # Sort chunk files by index
        chunk_files.sort(key=lambda x: int(os.path.basename(x).split('_')[1]))

        # Combine chunks into final file
        with open(output_path, 'wb') as outfile:
            for chunk_file in chunk_files:
                with open(chunk_file, 'rb') as infile:
                    outfile.write(infile.read())

        # Clean up temp files
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

        Script.log(f"[DOWNLOAD] Successfully downloaded {content_length} bytes to {output_path}", lvl=Script.INFO)
        return True

    except Exception as e:
        Script.log(f"[DOWNLOAD] Error in multi-threaded download: {e}", lvl=Script.ERROR)
        # Clean up on error
        for temp in [output_path + '.temp_chunks']:
            if os.path.exists(temp):
                import shutil
                shutil.rmtree(temp, ignore_errors=True)
        return False


def single_threaded_download(url, output_path, headers=None):
    """
    Fallback single-threaded download using requests.
    """
    try:
        if headers is None:
            headers = {}
        
        response = requests.get(url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        Script.log(f"[DOWNLOAD] Single-threaded download completed to {output_path}", lvl=Script.INFO)
        return True
        
    except Exception as e:
        Script.log(f"[DOWNLOAD] Error in single-threaded download: {e}", lvl=Script.ERROR)
        return False


def check_ffmpeg_available():
    """
    Check if ffmpeg is available on the system.
    Returns True if available, False otherwise.
    """
    try:
        # Try to run ffmpeg -version to check if it's available
        process = subprocess.Popen(
            ['ffmpeg', '-version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        process.wait()
        return process.returncode == 0
    except (FileNotFoundError, OSError):
        # ffmpeg not found in PATH
        return False


def get_widevine_license_info(channel_id, showtime=None, srno=None, programId=None, begin=None, end=None):
    """
    Extract Widevine license URL and headers from the VOD playback logic.
    Returns license URL and headers for decryption.
    """
    try:
        from resources.lib.utils import getHeaders, getSonyHeaders
        from urllib.parse import urlencode
        from uuid import uuid4
        
        # Get the same headers as used in play function
        headers = getHeaders()
        headers["channelid"] = str(channel_id)
        
        if showtime and srno:
            headers["srno"] = srno
            headers["showtime"] = showtime
        
        # Get stream URL to extract MPD data
        stream_url, _ = get_stream_url_for_recording(channel_id, showtime, srno, programId, begin, end)
        if not stream_url or '.mpd' not in stream_url:
            return None, None
            
        # Get MPD response to extract license info
        import urlquick
        mpd_headers = headers.copy()
        mpd_headers.update({
            "user-agent": "okhttp/4.2.2",
            "content-type": "application/dash+xml",
        })
        
        mpd_res = urlquick.get(stream_url, headers=mpd_headers, verify=False, max_age=-1)
        mpd_content = mpd_res.text
        
        # Extract content_id from MPD or use programId
        content_id = programId
        if not content_id:
            # Try to extract from MPD content
            import re
            content_match = re.search(r'content_id["\s]*:\s*["\']([^"\']+)["\']', mpd_content)
            if content_match:
                content_id = content_match.group(1)
        
        if not content_id:
            Script.log("[WIDEVINE] Could not extract content_id for license", lvl=Script.ERROR)
            return None, None
            
        # Build license URL (same as used by InputStream Adaptive)
        license_url = f"https://tv.media.jio.com/catchupproxy?provider=reliance&content_id={content_id}"
        
        # Build license headers (same as player.py)
        license_headers = {
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
        }
        
        # Add authentication headers
        license_headers.update({
            "Accesstoken": headers.get("Accesstoken", ""),
            "cookie": headers.get("cookie", ""),
        })
        
        Script.log(f"[WIDEVINE] License URL: {license_url}", lvl=Script.INFO)
        Script.log(f"[WIDEVINE] License headers prepared", lvl=Script.DEBUG)
        
        return license_url, license_headers
        
    except Exception as e:
        Script.log(f"[WIDEVINE] Error getting license info: {e}", lvl=Script.ERROR)
        return None, None


def ensure_ffmpeg_available():
    """
    Ensure ffmpeg is available, showing installation instructions if not.
    Returns True if ffmpeg is available, False otherwise.
    """
    if check_ffmpeg_available():
        Script.log("[RECORDING] ffmpeg is already available", lvl=Script.INFO)
        return True

    Script.log("[RECORDING] ffmpeg not found, showing installation instructions", lvl=Script.INFO)

    # Show user instructions directly
    dialog = xbmcgui.Dialog()
    result = dialog.yesno(
        "ffmpeg Required",
        "ffmpeg is required for recording but is not available on your system.\n\nWould you like to see installation instructions?",
        "Cancel",
        "Show Instructions"
    )

    if result:  # User wants installation guide
        # Show installation instructions based on platform
        platform = xbmc.getCondVisibility("System.Platform.Windows") and "windows" or \
                  xbmc.getCondVisibility("System.Platform.Linux") and "linux" or \
                  xbmc.getCondVisibility("System.Platform.OSX") and "macos" or \
                  xbmc.getCondVisibility("System.Platform.Android") and "android" or "unknown"

        instructions = {
            "windows": "Download ffmpeg from https://ffmpeg.org/download.html#build-windows and add it to your system PATH, or install via Chocolatey: 'choco install ffmpeg'",
            "linux": "Install via package manager: 'sudo apt install ffmpeg' (Ubuntu/Debian) or 'sudo dnf install ffmpeg' (Fedora)",
            "macos": "Install via Homebrew: 'brew install ffmpeg'",
            "android": "ffmpeg should be available via your Android Kodi build, or install a compatible version",
            "unknown": "Please visit https://ffmpeg.org/download.html for installation instructions for your platform"
        }

        msg = instructions.get(platform, instructions["unknown"])
        dialog.textviewer("ffmpeg Installation Instructions", msg)

    return False


@Script.register
def record_live_stream(plugin, channel_id, channel_name="Unknown Channel"):
    """
    Record a live stream for user-specified duration.
    """
    try:
        # Check if ffmpeg is available, install if necessary
        if not ensure_ffmpeg_available():
            Script.notify("Recording Failed", "ffmpeg is required but could not be installed")
            return

        # Get recording duration from user
        duration_options = [
            ("5 minutes", "300"),
            ("10 minutes", "600"),
            ("15 minutes", "900"),
            ("30 minutes", "1800"),
            ("1 hour", "3600"),
            ("2 hours", "7200"),
        ]

        duration_labels = [opt[0] for opt in duration_options]
        duration_values = [opt[1] for opt in duration_options]

        duration_idx = Dialog().select("Select recording duration", duration_labels)
        if duration_idx == -1:
            return

        duration = int(duration_values[duration_idx])

        # Generate default filename: channel_name_date_time
        safe_channel_name = "".join(c for c in channel_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        default_filename = f"{safe_channel_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        
        # Get output filename from user, with default suggestion
        filename = keyboard("Enter filename (or leave empty for auto-generated)", default=default_filename)
        if not filename or filename.strip() == "":
            filename = default_filename
        elif not filename.endswith('.mp4'):
            filename += '.mp4'

        # Get save location (cross-platform compatible)
        save_path = xbmcvfs.translatePath("special://home/userdata/addon_data/plugin.kodi.jiotv/recordings/")
        if not xbmcvfs.exists(save_path):
            xbmcvfs.mkdirs(save_path)

        output_path = os.path.join(save_path, filename)

        # Get stream URL
        Script.notify("Recording", f"Getting stream URL for {channel_name}...")
        stream_url, headers = get_stream_url_for_recording(channel_id)
        if not stream_url:
            Script.notify("Recording Failed", "Could not get stream URL")
            return

        # Build headers for ffmpeg (cross-platform compatible)
        headers = getHeaders()
        headers["user-agent"] = "jiotv"

        # Start recording in background
        Script.notify("Recording", f"Starting {duration//60}min recording...")

        def do_recording():
            success = record_stream(stream_url, output_path, duration, headers)
            if success:
                Script.notify("Recording Complete", f"Saved to: {filename}")
            else:
                Script.notify("Recording Failed", "Check logs for details")

        recording_thread = threading.Thread(target=do_recording)
        recording_thread.daemon = True
        recording_thread.start()

    except Exception as e:
        Script.log(f"[RECORDING] Error in record_live_stream: {e}", lvl=Script.ERROR)
        Script.notify("Recording Failed", str(e))


@Script.register
def download_vod(plugin, *args, **kwargs):
    """
    Download VOD content.
    """
    try:
        # Debug: Log all received parameters
        Script.log(f"[RECORDING] download_vod called with args: {args} (len: {len(args)}), kwargs: {kwargs}", lvl=Script.INFO)

        # Handle different parameter formats
        if len(args) >= 7:
            # Parameters passed as positional args
            channel_id, showtime, srno, programId, begin, end = args[:6]
            title = args[6] if len(args) > 6 else kwargs.get('title', "VOD Content")
        elif kwargs:
            # Parameters passed as keyword args
            channel_id = kwargs.get('channel_id', '')
            showtime = kwargs.get('showtime', '')
            srno = kwargs.get('srno', '')
            programId = kwargs.get('programId', '')
            begin = kwargs.get('begin', '')
            end = kwargs.get('end', '')
            title = kwargs.get('title', "VOD Content")
        else:
            Script.log("[RECORDING] No valid parameters received", lvl=Script.ERROR)
            Script.notify("Download Failed", "Invalid parameters")
            return

        Script.log(f"[RECORDING] Extracted parameters: channel_id={channel_id}, showtime={showtime}, srno={srno}, programId={programId}, begin={begin}, end={end}, title={title}", lvl=Script.INFO)

        # Convert parameters to strings for consistency
        channel_id = str(channel_id)
        showtime = str(showtime) if showtime else ""
        srno = str(srno) if srno else ""
        programId = str(programId) if programId else ""
        begin = str(begin) if begin else ""
        end = str(end) if end else ""
        title = str(title) if title else "VOD Content"

        Script.log(f"[RECORDING] After conversion: channel_id={channel_id}, showtime={showtime}, srno={srno}", lvl=Script.INFO)

        # Check if ffmpeg is available, install if necessary
        if not ensure_ffmpeg_available():
            Script.notify("Download Failed", "ffmpeg is required but could not be installed")
            return

        # Generate default filename: VOD_program_name_date_time
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        default_filename = f"VOD_{safe_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        
        # Get output filename from user, with default suggestion
        filename = keyboard("Enter filename (or leave empty for auto-generated)", default=default_filename)
        if not filename or filename.strip() == "":
            filename = default_filename
        elif not filename.endswith('.mp4'):
            filename += '.mp4'

        # Get save location
        save_path = xbmcvfs.translatePath("special://home/userdata/addon_data/plugin.kodi.jiotv/downloads/")
        if not xbmcvfs.exists(save_path):
            xbmcvfs.mkdirs(save_path)

        output_path = os.path.join(save_path, filename)

        # Start download in background
        Script.notify("Download", f"Starting download: {title}")

        def do_download():
            # APPROACH 1: ffmpeg direct download (best approach for encrypted HLS)
            # Get a FRESH stream URL token and pass everything to ffmpeg immediately
            # ffmpeg handles key download, segment download, and muxing internally
            Script.log("[DOWNLOAD] === Trying ffmpeg direct download (primary method) ===", lvl=Script.INFO)
            
            try:
                # Get a fresh stream URL with a new 120-second token
                Script.log("[DOWNLOAD] Getting fresh stream URL for ffmpeg...", lvl=Script.INFO)
                stream_url, headers = get_stream_url_for_recording(channel_id, showtime, srno, programId, begin, end)
                
                if not stream_url:
                    Script.log("[DOWNLOAD] Could not get stream URL", lvl=Script.ERROR)
                    Script.notify("Download Failed", "Could not get stream URL")
                    return

                Script.log(f"[DOWNLOAD] Got stream URL, starting ffmpeg immediately...", lvl=Script.INFO)

                # Build ffmpeg command with auth headers matching Kodi's InputStream.Adaptive
                # During playback, InputStream.Adaptive uses getHeaders() for stream_headers/manifest_headers
                # which includes ssotoken, authtoken, channelid, srno, showtime, etc.
                # The key server at tv.media.jio.com validates these JioTV API headers
                safe_output = output_path.replace('\\', '/')
                
                cmd = ['ffmpeg', '-y']
                
                # Extract the __hdnea__ cookie from the URL
                hdnea_cookie = ""
                if '__hdnea__' in stream_url:
                    try:
                        from urllib.parse import urlparse, parse_qs
                        url_parsed = urlparse(stream_url)
                        url_qs = parse_qs(url_parsed.query)
                        if '__hdnea__' in url_qs:
                            hdnea_cookie = "__hdnea__=" + url_qs['__hdnea__'][0]
                    except Exception:
                        hdnea_cookie = "__hdnea__" + stream_url.split("__hdnea__")[-1].split("&")[0]

                # Build headers matching what player.py passes to InputStream.Adaptive
                # player.py lines 56-67, 180, 321: uses getHeaders() + cookie
                api_headers = getHeaders()
                if api_headers:
                    api_headers["channelid"] = str(channel_id)
                    if showtime and srno:
                        api_headers["srno"] = str(srno)
                        api_headers["showtime"] = str(showtime)
                    api_headers["cookie"] = hdnea_cookie or headers.get("cookie", "")
                    api_headers.setdefault("user-agent", "jiotv")
                else:
                    api_headers = headers

                # ffmpeg -headers format: each header on its own line terminated by \r\n
                ffmpeg_headers = ""
                for hk, hv in api_headers.items():
                    if hv and isinstance(hv, str):
                        ffmpeg_headers += f"{hk}: {hv}\r\n"
                
                if ffmpeg_headers:
                    cmd.extend(['-headers', ffmpeg_headers])
                
                cmd.extend([
                    '-i', stream_url,  # Use the master M3U8 URL directly
                    '-c', 'copy',
                    '-bsf:a', 'aac_adtstoasc',
                    safe_output
                ])
                
                Script.log(f"[DOWNLOAD] ffmpeg command (url truncated): ffmpeg -y -headers [auth headers] -i [stream_url] -c copy -bsf:a aac_adtstoasc {safe_output}", lvl=Script.INFO)
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
                
                # Monitor with timeout - VOD streams can be long
                stdout, stderr = process.communicate(timeout=1800)  # 30 min timeout
                
                if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                    Script.log(f"[DOWNLOAD] ffmpeg direct download SUCCESS: {output_path} ({file_size_mb:.1f} MB)", lvl=Script.INFO)
                    Script.notify("Download Complete", f"Saved: {output_path} ({file_size_mb:.1f} MB)")
                    return
                else:
                    Script.log(f"[DOWNLOAD] ffmpeg direct download failed (code {process.returncode})", lvl=Script.ERROR)
                    if stderr:
                        Script.log(f"[DOWNLOAD] ffmpeg stderr: {stderr[-500:]}", lvl=Script.ERROR)
                    
            except subprocess.TimeoutExpired:
                process.kill()
                Script.log("[DOWNLOAD] ffmpeg direct download timed out after 30 min", lvl=Script.ERROR)
            except Exception as e:
                Script.log(f"[DOWNLOAD] ffmpeg direct download error: {e}", lvl=Script.ERROR)
            
            # APPROACH 2: Segment-based download (fallback)
            # Downloads encrypted segments and saves them for manual processing
            Script.log("[DOWNLOAD] === Trying segment-based download (fallback method) ===", lvl=Script.INFO)
            try:
                # Get another fresh stream URL
                stream_url2, headers2 = get_stream_url_for_recording(channel_id, showtime, srno, programId, begin, end)
                if stream_url2:
                    success = multi_threaded_download(stream_url2, output_path, headers2)
                    if success:
                        Script.log(f"[DOWNLOAD] VOD saved to: {output_path}", lvl=Script.INFO)
                        Script.notify("Download Complete", f"Saved to: {output_path}")
                        return
            except Exception as e:
                Script.log(f"[DOWNLOAD] Segment download fallback error: {e}", lvl=Script.ERROR)
            
            Script.notify("Download Failed", "Check logs for details. Segments may be saved for manual processing.")

        download_thread = threading.Thread(target=do_download)
        download_thread.daemon = True
        download_thread.start()

    except Exception as e:
        Script.log(f"[RECORDING] Error in download_vod: {e}", lvl=Script.ERROR)
        Script.notify("Download Failed", str(e))


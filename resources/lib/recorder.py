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
        key_files = {}  # Maps original key URI -> local filename
        for key in playlist.keys:
            if key and key.uri and key.uri not in key_files:
                # Use absolute URL directly if it starts with http, otherwise resolve
                if key.uri.startswith('http'):
                    key_url = key.uri
                else:
                    key_url = resolve_and_merge_query(url, key.uri)
                
                # FIX 403 FORBIDDEN: Catchup streams serve from CDNs with url auth tokens (__hdnea__)
                # The M3U8 hardcodes the key to tv.media.jio.com/fallback/ which rejects the request
                # We need to rewrite the key URL to match the stream's CDN host and query params
                if 'tv.media.jio.com/fallback' in key_url and '?' in url:
                    try:
                        from urllib.parse import urlparse
                        base_parsed = urlparse(url)
                        key_parsed = urlparse(key_url)
                        
                        # Strip /fallback from the key path and append it to the stream's scheme+netloc
                        path_without_fallback = key_parsed.path.replace('/fallback', '')
                        # Also copy the auth token query parameters from the stream url!
                        key_url = f"{base_parsed.scheme}://{base_parsed.netloc}{path_without_fallback}?{base_parsed.query}"
                        Script.log(f"[DOWNLOAD] Rewrote fallback key to CDN URL with auth tokens", lvl=Script.INFO)
                    except Exception as e:
                        Script.log(f"[DOWNLOAD] Warning: Failed to rewrite key URL: {e}", lvl=Script.WARNING)

                Script.log(f"[DOWNLOAD] Downloading AES-128 key from: {key_url[:120]}...", lvl=Script.INFO)

                # Try multiple header sets - the key server may need different auth
                # It strips all the extra Jio API headers and only sends these four:
                player_headers = {
                    "user-agent": headers.get("user-agent", "jiotv"),
                    "cookie": headers.get("cookie", ""),
                    "content-type": "application/vnd.apple.mpegurl",
                    "Accesstoken": headers.get("Accesstoken", "")
                }
                
                # Make sure empty headers are removed
                player_headers = {k: v for k, v in player_headers.items() if v}

                header_sets = [
                    ("Player exactly (like Kodi)", player_headers),
                    ("CDN headers", headers),
                    ("JioTV API headers", getHeaders()),
                    ("Minimal headers", {"user-agent": "jiotv"}),
                ]

                key_downloaded = False
                for header_name, try_headers in header_sets:
                    try:
                        if not try_headers:
                            continue
                        Script.log(f"[DOWNLOAD] Trying key download with {header_name}...", lvl=Script.INFO)
                        key_response = requests.get(key_url, headers=try_headers, timeout=10, verify=False)
                        key_response.raise_for_status()
                        if len(key_response.content) == 16:  # AES-128 key is exactly 16 bytes
                            key_filename = f"key_{len(key_files)}.key"
                            key_path = os.path.join(segments_dir, key_filename)
                            with open(key_path, 'wb') as f:
                                f.write(key_response.content)
                            key_files[key.uri] = key_filename
                            Script.log(f"[DOWNLOAD] Saved encryption key to: {key_path} ({len(key_response.content)} bytes) using {header_name}", lvl=Script.INFO)
                            key_downloaded = True
                            break
                        else:
                            Script.log(f"[DOWNLOAD] Key response unexpected size: {len(key_response.content)} bytes (expected 16), trying next headers", lvl=Script.WARNING)
                    except Exception as e:
                        Script.log(f"[DOWNLOAD] Key download failed with {header_name}: {e}", lvl=Script.WARNING)

                if not key_downloaded:
                    Script.log(f"[DOWNLOAD] Could not download encryption key from: {key_url}", lvl=Script.ERROR)
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
                Script.log(f"[DOWNLOAD] ffmpeg mux failed (code {process.returncode})", lvl=Script.ERROR)
                if stderr:
                    Script.log(f"[DOWNLOAD] ffmpeg stderr: {stderr[-500:]}", lvl=Script.ERROR)
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

        except Exception as e:
            Script.log(f"[DOWNLOAD] Error checking M3U8: {e}, trying direct download", lvl=Script.WARNING)

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

        # Get stream URL
        Script.notify("Download", f"Getting stream URL for {title}...")
        stream_url, headers = get_stream_url_for_recording(channel_id, showtime, srno, programId, begin, end)
        
        if not stream_url:
            Script.notify("Download Failed", "Could not get stream URL")
            return

        # Start download in background
        Script.notify("Download", f"Starting download: {title}")

        def do_download():
            # Use multi-threaded download for VOD
            success = multi_threaded_download(stream_url, output_path, headers)
            if success:
                Script.log(f"[DOWNLOAD] VOD saved to: {output_path}", lvl=Script.INFO)
                Script.notify("Download Complete", f"Saved to: {output_path}")
            else:
                Script.notify("Download Failed", "Check logs for details")

        download_thread = threading.Thread(target=do_download)
        download_thread.daemon = True
        download_thread.start()

    except Exception as e:
        Script.log(f"[RECORDING] Error in download_vod: {e}", lvl=Script.ERROR)
        Script.notify("Download Failed", str(e))

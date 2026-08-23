# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# basic imports
from http.server import SimpleHTTPRequestHandler
import os
from urllib.parse import parse_qs, urlparse, unquote
from xbmcvfs import translatePath
import xbmcaddon
import xml.etree.ElementTree as ET
from resources.lib.utils import login, sendOTPV2, get_session

# codequick imports
from codequick import Script

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo("path")
PROXY_PORT = 48996


def optimize_mpd(mpd_xml_text, cdn_url):
    DASH_NS = "urn:mpeg:dash:schema:mpd:2011"
    ET.register_namespace('', DASH_NS)
    ET.register_namespace('cenc', "urn:mpeg:cenc:2013")
    ET.register_namespace('xsi', "http://www.w3.org/2001/XMLSchema-instance")
    
    root = ET.fromstring(mpd_xml_text)
    
    parsed = urlparse(cdn_url)
    cdn_dir = parsed.scheme + "://" + parsed.netloc + parsed.path.rsplit('/', 1)[0] + '/'
    
    for period in root.findall(".//{*}Period"):
        base_url_elem = period.find("{*}BaseURL")
        if base_url_elem is not None:
            rel_base = base_url_elem.text or ""
            if not rel_base.startswith("http"):
                if rel_base and not rel_base.endswith('/'):
                    rel_base += '/'
                base_url_elem.text = cdn_dir + rel_base
        else:
            new_base = ET.Element("{" + DASH_NS + "}BaseURL")
            new_base.text = cdn_dir
            period.insert(0, new_base)
            
    for period in root.findall(".//{*}Period"):
        audio_sets = []
        all_adapt_sets = list(period.findall("{*}AdaptationSet"))
        
        for aset in all_adapt_sets:
            content_type = aset.attrib.get("contentType", "")
            mime_type = aset.attrib.get("mimeType", "")
            reps = aset.findall("{*}Representation")
            
            is_audio = ("audio" in content_type.lower()) or ("audio" in mime_type.lower())
            if not is_audio:
                for r in reps:
                    r_mime = r.attrib.get("mimeType", "").lower()
                    r_codecs = r.attrib.get("codecs", "").lower()
                    if "audio" in r_mime or r_codecs.startswith(("mp4a", "ac-3", "ec-3", "opus")):
                        is_audio = True
                        break
            if is_audio:
                audio_sets.append(aset)
                
        def get_max_bw(aset):
            max_bw = 0
            for r in aset.findall("{*}Representation"):
                try:
                    bw = int(r.attrib.get("bandwidth", 0))
                    if bw > max_bw:
                        max_bw = bw
                except ValueError:
                    pass
            return max_bw
            
        # Sort audio AdaptationSets in descending order of maximum bitrate
        audio_sets.sort(key=get_max_bw, reverse=True)
        
        for aset in audio_sets:
            period.remove(aset)
            
            bw_bps = get_max_bw(aset)
            bw_kbps = round(bw_bps / 1000.0, 1) if bw_bps > 0 else 0
            kbps_str = f"{bw_kbps:g} kbps"
            
            lang = aset.attrib.get("lang", "")
            lang_upper = lang.upper() if lang else ""
            label_text = f"{lang_upper} - {kbps_str}" if lang_upper else kbps_str
            
            # Remove any existing Label elements
            for label in aset.findall("{*}Label"):
                aset.remove(label)
                
            label_elem = ET.Element("{" + DASH_NS + "}Label")
            label_elem.text = label_text
            aset.insert(0, label_elem)
            
            period.append(aset)
            
    return ET.tostring(root, encoding="utf-8").decode("utf-8")


class JioTVProxy(SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        if path == "/":
            self.send_response(200)

            html = os.path.join(translatePath(
                ADDON_PATH), "resources", "login.html")
            try:
                f = open(html, 'rb')
            except IOError:
                self.send_error(404, "File not found")
                return None

            self.send_header("Content-type", "text/html")
            fs = os.fstat(f.fileno())
            self.send_header("Content-Length", str(fs.st_size))
            self.end_headers()
            self.wfile.write(bytes(f.read()))
            f.close()
            return
        elif path == "/manifest.mpd":
            query = parse_qs(parsed_url.query)
            cdn_url = query.get("url", [None])[0]
            if not cdn_url:
                self.send_error(400, "Missing url parameter")
                return
            try:
                headers = {
                    "User-Agent": "plaYtv/7.1.5 (Linux;Android 9) ExoPlayerLib/2.11.7"
                }
                cookie = query.get("cookie", [None])[0]
                if cookie:
                    headers["Cookie"] = cookie
                elif self.headers.get("Cookie"):
                    headers["Cookie"] = self.headers.get("Cookie")

                session = get_session()
                resp = session.get(cdn_url, headers=headers, timeout=(10, 15))
                resp.raise_for_status()
                mpd_text = resp.text

                try:
                    optimized_xml = optimize_mpd(mpd_text, cdn_url)
                    content_bytes = optimized_xml.encode("utf-8")
                    Script.log(f"[PROXY] MPD audio optimization successful for {cdn_url}", lvl=Script.INFO)
                except Exception as opt_err:
                    Script.log(f"[PROXY] MPD optimization failed, serving raw: {opt_err}", lvl=Script.WARNING)
                    content_bytes = resp.content

                self.send_response(200)
                self.send_header("Content-Type", "application/dash+xml")
                self.send_header("Content-Length", str(len(content_bytes)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content_bytes)
                return
            except Exception as e:
                Script.log(f"[PROXY] Failed to proxy MPD {cdn_url}: {e}", lvl=Script.ERROR)
                self.send_error(500, str(e))
                return
        else:
            self.send_error(404, "File not found")

    def do_POST(self):
        if self.path == "/login":
            data_string = self.rfile.read(
                int(self.headers['Content-Length']))

            qs = parse_qs(data_string.decode('utf-8'))
            error = None
            Script.log(qs, lvl=Script.INFO)
            try:
                if qs.get("type")[0] == "password":
                    error = login(qs.get("username")[0], qs.get("password")[0])
                elif qs.get("type")[0] == "otp":
                    mobile = qs.get("mobile")[0]
                    if qs.get("otp"):
                        error = login(mobile, qs.get("otp")[0], mode="otp")
                    else:
                        error = sendOTPV2(mobile)
                else:
                    error = "Invalid Type"
            except Exception as e:
                Script.log(e, lvl=Script.ERROR)
                error = str(e)

            if error:
                location = "/?error="+str(error)
            elif qs.get("type")[0] == "otp" and qs.get("otp") is None:
                location = "/?otpsent=" + qs.get("mobile")[0]
            else:
                location = "/?success"
            self.send_response(302)
            self.send_header('Location', location)
            self.end_headers()
        else:
            self.send_error(404, "File not found")

# Frequently Asked Questions (FAQ)

> 🎉 **A Friendly Note to Users:** Before opening a new issue on GitHub or requesting support, please take a moment to read through this entire document and the FAQs below! Most questions regarding missing channels, video/audio streaming quality, error logs, and Catchup availability are intentionally managed by Kodi and already fully answered here.

---

**Q: I can't find certain channels like *Zee Studio / Zee Movies* in the addon. Can you add them?**  
**A:** The addon directly mirrors what is officially available and supported on the JioTV mobile application ecosystem. If a channel (like *Zee Studio*) is missing, geographically blocked, or restricted in the official JioTV mobile app, it cannot be spoofed or made available in this addon.

**Q: Why do some Zee channels (e.g., Zee Bangla HD) give an "API 403" Playback Error, while others work fine?**  
**A:** Due to shifting licensing contracts, many major network branches (like specific Zee Networks) are no longer officially broadcast via the JioTV mobile app. If you discover that certain unlisted streams (like a standard definition variant) still miraculously load here, please consider it a lucky bonus! We gently ask that you enjoy the extra functional channels while they last rather than reporting the ones returning 403 Errors. *(Repeatedly flagging these legally dead streams might unfortunately force us to just mass-remove the remaining functional ones to avoid confusion!)*

**Q: Why does playback fail, or why does it take 10-45 seconds to load channels?**  
**A:** JioTV Direct streams high-quality MPD (MPEG-DASH) feeds. These heavily DRM-protected, higher-bitrate streams are significantly heavier to process than older 360p alternatives. Expect a noticeable delay during channel initialization and switching. If you experience crashes and severely slow loading, it often means your hardware does not have sufficient processing power or memory. (A minimum of Android 9.0 is highly recommended).

**Q: I get "Playback Failed" and Widevine doesn't install on my older TV Box (e.g., Android 5/6, MXQ Pro). Why did older addons work?**  
**A:** This addon specifically pulls modern, high-definition channels from Jio wrapped in strict DRM encryption. To decode them, Kodi firmly requires **Widevine CDM**. Unfortunately, uncertified or legacy boxes running Android 5 or 6 lack the modern operating system tools necessary for Kodi's `inputstreamhelper` to safely extract and run these Widevine decryption keys. Older addons may have worked perfectly for you previously simply because they fetched unencrypted, vastly inferior `360p` feeds that bypassed DRM altogether! To enjoy these secure HD streams, we gently advise upgrading to a certified media streamer (like a Fire TV Stick, Chromecast, or Nvidia Shield) running Android 9.0+.

**Q: I updated the addon, but my old saved Favorites aren't playing anymore. What do I do?**  
**A:** Favorites saved from other JioTV addons (like `plugin.video.jiotv`), or from deeply outdated versions of this addon, point to different internal IDs and obsolete streaming protocols. To tap into the latest high-quality stream updates, you must manually delete those invalid favorites and **re-favorite your channels directly from within the updated JioTV Direct addon menus**.

**Q: Do I need to uninstall other JioTV addons before using JioTV Direct?**  
**A:** No. Installing JioTV Direct avoids conflict natively. Both addons can coexist on the same Kodi setup, but remember not to cross-contaminate their Favorite lists or settings.

**Q: Why do some channels not show a Catchup or Video on Demand (VOD) option?**  
**A:** Catchup/VOD support is populated dynamically based on Jio's licensing rights. If Jio did not secure catchup rights for a particular network (e.g., the majority of the Star Network), the option will intentionally not appear. It is only available for channels that officially broadcast `isCatchupAvailable` flags via Jio's servers.

**Q: Why do Star and Sony network channels show "Subscription Information" (e.g., 99 per month) or "Channel subscription coming soon" instead of the live stream?**  
**A:** This addon mirrors exactly what is available in the official JioTV mobile app. If Jio restricts a channel's live broadcast and replaces it with subscription messages—such as on **Vijay TV** or **Vijay Takkar** channels (which frequently display “Channel subscription coming soon” or subscription popups)—this addon is not responsible for that and cannot bypass those restrictions. We gently ask that you enjoy whichever extra channels work for you, and not to complain if certain "premium" channels are unavailable or restricted. We show what Jio provides; nothing more, nothing less.

**Q: Why do regional/local channels (e.g., DTamil or specific local streams) frequently buffer, freeze, or stop playing after a few minutes?**  
**A:** The live streaming feeds for local and certain regional channels (such as DTamil) are frequently unstable on the Jio server/CDN side, resulting in stream dropouts or periodic buffering. Since the addon simply relays Jio's official CDN streams, these server-side source dropouts are entirely out of the addon's control.

**Q: I am getting "Session Expired" or being asked to login again frequently.**  
**A:** Jio's security tokens for Mobile/OTP login are strictly valid for **10 days**. The addon is now optimized to match this window. If your session is invalidated early by Jio's servers, the addon will automatically prompt you to re-authenticate to restore your stream.

**Q: Why doesn't "Best" Video Quality load properly, causing constant buffering even on a high-speed (e.g. 200 Mbps) connection?**  
**A:** Setting stream quality to "Best" forces Kodi's player to statically lock on the highest available bitrate. Jio's CDNs heavily throttle and limit connections that lock on static high bitrates, causing constant buffering even on ultra-fast 200 Mbps internet connections. Since version `v1.1.5`, Stream Quality is forced to "**Manual**" by default during setup. Video feeds naturally scale organically via adaptive streaming mechanisms depending on your live internet connection. Please leave quality on **Manual** so adaptive streaming can manage and scale bitrates dynamically for you without buffering!

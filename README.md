<h2 align="center">
  <br>
  <img src="resources/icon.png" height="60" width="60">
  <br>
  JioTV Direct
  <br>
</h2>

<h4 align="center">Custom JioTV Kodi Add-on</h4>

<br>

## Description
This is a custom version of the JioTV Kodi add-on with improvements for video quality.
It uses a direct license key fetcher with cookies for better streaming performance.

This KODI addon loads channels that are available in jiotv mobile and not from jiotv+ or from any other source.

Kind request to users - please check jiotv mobile addon before raising any issue to add support for channels. I can help and add channels only when it loads in jiotv mobile application and not from other sources to the addon.

## Installation Instructions

1. **Open Kodi**: Launch Kodi on your device.
2. **Settings**: Go to **Settings** (gear icon) > **File Manager**.
3. **Add Source**:
   - Select **Add source**.
   - Enter the URL: `https://dineshintry.github.io/plugin.kodi.jiotv/`
   - Name it `JioTV Direct Repo`.
4. **Install from Zip**:
   - Go to **Settings** > **Add-ons**.
   - Select **Install from zip file**. (Enable "Unknown sources" if prompted)
   - Choose `JioTV Direct Repo`.
   - Select `repository.jiotvdirect-1.0.0.zip` to install.
5. **Install Addon from Repo**:
   - Go to **Install from repository**.
   - Select **JioTV Direct Repository**.
   - Go to **Video add-ons** and select **JioTV Direct**.
6. **Updates**: By installing via this repository, your add-on will now receive automatic updates whenever a new version is released.
7. **Configuration**: Once installed, open the add-on settings to log in with your Jio account.

### Alternative: Manual Installation (Via Zip)
If you prefer to install the addon manually without the repository:
1. **Download the Zip**: Go to the [Releases](https://github.com/dineshintry/plugin.kodi.jiotv/releases) page and download the `plugin.kodi.jiotv-x.x.x.zip` from the latest tag.
2. **Install in Kodi**:
   - Go to **Settings** > **Add-ons** > **Install from zip file**.
   - Locate and select the downloaded zip file.
   - Note: Manual installations **do not** receive automatic updates. You must repeat this process for every new version.

## Video Guides

- **Troubleshooting & Upgrade Guide**: [Watch Video](https://youtu.be/S2B6uM9G_zY)
- **Zip Installation Guide (GitHub Repo)**: [Watch Video](https://www.youtube.com/watch?v=_HSdOhaN3Uo)

### Troubleshooting Installation
If you encounter a failure while installing from the zip file:
1. **Quit/Close Kodi** completely.
2. **Re-launch Kodi**.
3. Go back to **Install from zip file** and try selecting the file again. This often resolves playback dependency or caching issues during the first install.

## ⚠️ Migration & Important Notices

### Upgrading from Manual Zip to Repository
If you previously installed the addon manually via a ZIP file and are now moving to the Repository source:
- **Favorites Loss**: Migrating to the repository route may remove some of your existing favorites.
- **Clean Install**: If prompted by Kodi to "remove settings" during the upgrade/reinstall to the repository source, **select "Yes"**. This ensures a clean configuration compatible with the repository's update system.

## 🛡️ Favourite & Account Management (v1.1.5+)

The addon now features a highly resilient backup system to manage your account and curated channels:
- **Resilient Account Backup**: Your login session is automatically backed up to a safe path that persists even if you uninstall or reinstall the addon.
- **Manage Favourites**: You can now securely backup your chosen favourite channels, restore them across different devices, or share your curated list with others.
- **Restore Shared Favourites**: Quickly import a friend's shared favourites list directly into your Kodi setup.


### Coexistence with other JioTV Addons
Installing **JioTV Direct** (`plugin.kodi.jiotv`) does **not** replace or overwrite any existing JioTV addons (like `plugin.video.jiotv`). Both can be installed on the same system simultaneously.

### Favorites & Stream Compatibility
If you have favorites saved from **older or different** JioTV addons, they will **not work** with JioTV Direct.
- Old favorites point to different internal IDs and may use outdated streaming formats.
- To use JioTV Direct's high-quality **MPD streams**, you must **manually re-favorite** your channels from within the JioTV Direct addon menus.
- Only favorites created directly within this addon will benefit from the latest stream updates and performance improvements.

## 🌐 Network Stability & Mobile Hotspot Support (v1.2.0+)

Historically, Android TV devices connected via Mobile Hotspots inherently suffered from dual-stack DNS mapping issues (broken IPv6 routes), which caused JioTV streams (both Live and Catchup VOD) to timeout indefinitely or freeze the Kodi UI.

This addon now contains a **Global Network Hotspot Optimizer**:
- **Automatic Auto-Patching**: Upon addon launch, it dynamically ensures Kodi's `advancedsettings.xml` instructs the internal C++ media players to bypass faulty Hotspot interfaces using IPv4.
- **Fail-Fast Mechanics**: The UI will no longer freeze if the network drops. Streams load seamlessly with heavily pooled non-blocking TLS sessions.
*(You will be notified to restart Kodi once the patch is applied on first launch)*

## Video On Demand (VOD) / Catch-up Feature (Supported after tag v1.0.1)

This add-on now supports Video On Demand (VOD) and catch-up TV functionality for compatible channels.

### VOD Support Details
- **Channel Availability**: Not all TV channels support VOD content. The add-on automatically detects and displays VOD-capable channels.
- **Channel Organization**: VOD-enabled channels are sorted and organized exclusively by language categories (not by genre or other groupings).
- **Content Organization**: After selecting a channel from the VOD menu, available programs are organized chronologically by date in folders (Today, 1 Day Ago, 2 Days Ago, etc.), with the most recent content displayed first within each date folder.
- **Empty Content Warning**: Some channels may appear VOD-capable but deliver no actual content, resulting in empty date folders. This is a limitation of the service provider's implementation.
- **Content Accuracy**: VOD content may not start and end at the exact timestamp of the intended program, as this is limited by the service provider's implementation.
- **Ad Handling**: The add-on actively blocks advertisements on VOD content and loads the main program content.
- **Video Quality**: VOD content may initially load in lower quality and doesn't always support adaptive streaming. If needed:
  - Manually select video quality in the add-on settings
  - Reopen VOD content multiple times until it loads in the desired quality

### Accessing VOD Content
1. Navigate to any VOD-capable channel
2. Select the channel to view available date folders (Today, 1 Day Ago, etc.)
3. Choose a date folder to see available VOD programs
4. Select a program to start playback

## 📅 EPG (Electronic Program Guide) Setup

If you are using the PVR functionality (via IPTV Simple Client) and the program guide is missing, follow these steps:

1. **Automatic Setup (Recommended)**: 
   - Open **JioTV Direct** addon.
   - Go to **Settings** > **Setup** category.
   - Click on **PVR Setup** (Label 33003). This will automatically configure `pvr.iptvsimple` with the latest EPG and playlist.
2. **Manual Configuration**:
   - If you want to use a custom EPG source, go to Addon **Settings** > **Setup** and find **EPG Source**.
   - You can paste any valid XMLTV URL (e.g., `https://raw.githubusercontent.com/mitthu786/tvepg/main/jiotv/epg.xml.gz`).
   - After changing the source, run **PVR Setup** again or restart Kodi.
3. **Troubleshooting**: If the guide still doesn't show up, ensure that "IPTV Simple Client" is enabled in your PVR addons and verify the "M3U Playlist Path" is pointing to the local file generated by this addon.

> The **TV Guide (EPG Grid)** option is primarily for viewing schedules and playing **Live Channels**. It cannot be used to browse or play the full **VOD/Catch-up** library. To play VOD programs or past broadcasts (Catch-up), please use the **"Video on Demand"** menu within the JioTV Direct addon.

## ❓ Frequently Asked Questions (FAQ)

> 🎉 **A Friendly Note to Users:** Before opening a new issue on GitHub or requesting support, please take a moment to read through this entire document and the FAQs below! Most questions regarding missing channels (like *Zee Studio*), video/audio streaming quality, error logs, and Catchup availability are intentionally managed by Kodi and already fully answered here. 

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

**Q: Why doesn't "Best" Video Quality and Audio Quality load properly?**
**A:** Since version `v1.1.5`, Quality is automatically forced to "**Manual**" during setup for all users. Video feeds naturally scale organically via adaptive streaming mechanisms depending on your live internet connection. Aggressively overriding this to "Best" forces Kodi to statically lock on bitrates, which is extremely resource-heavy and causes lagging since stream bitrates fluctuate heavily between channels. Leave it on Manual so adaptive streaming can manage it seamlessly for you!

## Best Practices for JioTV Direct Add-on

### Live TV Streaming
- **Video Quality**: Always select "Manual" quality from JioTV Direct Stream settings for optimal live TV results instead of relying on automatic detection.
- **Audio Quality**: Choose the best audio stream that suits your setup by manually selecting audio channels for each channel. Kodi remembers your selection for future playback.

### General Usage Tips
- Ensure stable internet connection for best streaming experience
- Close and reopen Kodi if you experience streaming issues
- Check add-on settings if video quality seems lower than expected

## Known Issues

### Streaming Issues
- **MPD Streaming**: Rarely crashes and exits current video playback
- **Service Interruptions**: Any interruptions from ISP or streaming service provider
- **Unexpected Errors**: Various streaming flow errors due to limited testing coverage

### Limitations
- **Service Changes**: Any modifications by the service provider to their JioTV streaming implementation may affect functionality
- **Channel Availability**: VOD support depends on individual channel capabilities
- **Quality Adaptation**: Some VOD content may not support adaptive bitrate streaming

### Troubleshooting
If you encounter issues:
1. Restart Kodi completely
2. Check your internet connection
3. Verify JioTV service status
4. Try reinstalling the add-on if problems persist

### How to share Error Logs (`kodi.log`)
If you need to report an ongoing issue, providing your `kodi.log` helps tremendously:
1. Open **JioTV Direct** settings.
2. Navigate to the **Developer Tools** category.
3. Click on **Copy kodi.log to Folder**.
4. You will be prompted to select a folder on your device. Choose an easily accessible folder (like `Downloads` or `Documents`).
5. Share the copied `kodi.log` file securely to help us understand the problem.

## Courtesy
Special thanks to the original creators and contributors:
- **Botallen**
- **kiranreddyrebel**
- **fatGrizzly**

## Disclaimer
This plugin is not officially commissioned/supported by Jio. The trademark "Jio" is registered by "Reliance Corporate IT Park Limited (RCITPL)".

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
   - Select the addon zip file to install.
5. **Updates**: By installing via this repository source, your add-on will now receive automatic updates whenever a new version is released.
6. **Configuration**: Once installed, open the add-on settings to log in with your Jio account.

### Troubleshooting Installation
If you encounter a failure while installing from the zip file:
1. **Quit/Close Kodi** completely.
2. **Re-launch Kodi**.
3. Go back to **Install from zip file** and try selecting the file again. This often resolves playback dependency or caching issues during the first install.

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

## Courtesy
Special thanks to the original creators and contributors:
- **Botallen**
- **kiranreddyrebel**
- **fatGrizzly**

## Disclaimer
This plugin is not officially commissioned/supported by Jio. The trademark "Jio" is registered by "Reliance Corporate IT Park Limited (RCITPL)".

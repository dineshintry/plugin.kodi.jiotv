# Best Practices, Troubleshooting & Known Issues

This guide compiles recommendations, known issues, troubleshooting guides, and logging procedures to ensure you get the absolute best performance from the **JioTV Direct** Kodi add-on.

---

## 💡 Best Practices

### Live TV Streaming
* **Video Quality**: Always select **Manual** quality from JioTV Direct Stream settings for optimal live TV results instead of relying on automatic detection.
* **Audio Quality**: Choose the best audio stream that suits your setup by manually selecting audio channels for each channel. Kodi remembers your selection for future playback.

### General Usage Tips
* Ensure a stable internet connection for the best streaming experience.
* Close and completely reopen Kodi if you experience unexpected streaming or navigation issues.
* Check add-on settings if video quality seems lower than expected.

---

## ⚠️ Known Issues

### Streaming Issues
* **MPD Streaming**: On very rare occasions, DASH streams might crash and unexpectedly exit current video playback. Re-opening the channel usually resolves this.
* **Service Interruptions**: Any interruptions from your ISP or JioTV's streaming service provider can result in playback failures.
* **Unexpected Errors**: Various streaming flow errors might occur due to limited testing coverage across all device variations.

### Limitations
* **Service Changes**: Any modifications or API updates by the service provider to their JioTV streaming implementation may affect add-on functionality.
* **Channel Availability**: Catchup/VOD support depends entirely on individual channel capabilities and provider licensing.
* **Quality Adaptation**: Some VOD/Catchup content might not support adaptive bitrate streaming.

---

## 🔧 Troubleshooting

If you encounter playback or other issues:
1. **Restart Kodi** completely (close the application and relaunch).
2. **Check your internet connection** and verify your network stability.
3. **Verify JioTV service status** on your mobile application to see if the service is undergoing maintenance.
4. **Try reinstalling the add-on** if problems persist.

---

## 📋 How to share Error Logs (`kodi.log`)

If you need to report an ongoing issue, providing your `kodi.log` helps tremendously:
1. Open **JioTV Direct** settings.
2. Navigate to the **Developer Tools** category.
3. Click on **Copy kodi.log to Folder**.
4. You will be prompted to select a folder on your device. Choose an easily accessible folder (like `Downloads` or `Documents`).
5. Share the copied `kodi.log` file securely to help us understand and resolve the problem.

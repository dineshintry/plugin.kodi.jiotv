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

---

## 📖 Add-on Documentation Guides

The documentation has been divided into focused guides to make it easier to read. Please click on the links below to view specific instructions and details:

* ### [🛡️ Add-on Features & Integration Guide](mds/features.md)
  Includes details on **Favourites & Account backups**, **Mobile Hotspot optimization**, **Video on Demand (VOD)/Catch-up** setup, **EPG (Electronic Program Guide)** configuration, and the **Extra Channels & M3U Integration** guide.

* ### [❓ Frequently Asked Questions (FAQ)](mds/FAQs.md)
  Includes answers for playback failures, restricted premium channels (Vijay TV/Sony/Star), billing information alerts, Widevine CDM issues, buffering, and early session expirations.

* ### [💡 Best Practices, Troubleshooting & Known Issues](mds/best_practices.md)
  Includes recommended streaming settings, known limitations, troubleshooting checklist, and instructions on how to export your `kodi.log` for developer support.

---

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

## Courtesy
Special thanks to the original creators and contributors:
- **Botallen**
- **kiranreddyrebel**
- **fatGrizzly**

## Disclaimer
This plugin is not officially commissioned/supported by Jio. The trademark "Jio" is registered by "Reliance Corporate IT Park Limited (RCITPL)".

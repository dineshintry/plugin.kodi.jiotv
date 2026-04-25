---
description: How to publish a new release and create tags
---
Follow these steps strictly to publish a new release of the addon:

1. Update `addon.xml` by incrementing the `version` attribute in the `<addon>` root element to the new version `vX.Y.Z`.
2. Add a new section for the new version to the `<news>` block in `addon.xml` detailing the latest changes.
3. Update `README.md` and release notes with the new features if needed.
4. Stage and commit these changes:
    *(WARNING: Do NOT use `git add .` as it might accidentally stage deleted vital directories like `repository.jiotvdirect/` which breaks the CI workflow! Only add the modified files).*
    // turbo
    git add addon.xml README.md
    // turbo
    git commit -m "Release vX.Y.Z: <brief description>"
5. Push the commit to the `master` branch.
    // turbo
    git push origin master
6. Create a tag using the EXACT format `vX.Y.Z`. A **lowercase 'v'** is absolutely CRITICAL because the GitHub Action workflow `.github/workflows/publish_repo.yml` is configured to trigger only on tags matching `v*`.
    // turbo
    git tag vX.Y.Z
7. Push the new tag to the remote repository. This will trigger the GitHub Action to package the ZIP and update the Kodi repository.
    // turbo
    git push origin vX.Y.Z
8. Create a GitHub Release for the newly pushed tag using the GitHub CLI (`gh`). This makes the version officially available to users.
    // turbo
    gh release create vX.Y.Z --title "Release vX.Y.Z" --notes "Add your release notes here."

# Fully Automatic Anime Reel Bot

This version removes `VIDEO_SOURCE_MAP` completely.

## Automatic pipeline

1. AniList finds anime matching **ALL** genres in `ANIME_GENRES`.
2. The source adapter automatically searches Internet Archive.
3. It accepts only records carrying recognizable Creative Commons/public-domain license markers.
4. The video is downloaded automatically.
5. FFmpeg/OpenCV analyzes motion, audio, edges, and brightness to choose a strong 15-45 second moment.
6. The clip is rendered as 1080x1920 H.264/AAC.
7. The MP4 is uploaded to a GitHub Release so Instagram can fetch it from a public HTTPS URL.
8. Instagram Graph API publishes the Reel.
9. `posted.json` prevents the same AniList anime from being selected again.

## GitHub secrets

Only these two user-provided secrets are required:

- `INSTAGRAM_ACCESS_TOKEN`
- `INSTAGRAM_USER_ID`

`GITHUB_TOKEN` is provided automatically by GitHub Actions.

There is **no `VIDEO_SOURCE_MAP` secret** in this version.

## Important source limitation

AniList is a metadata API; it does not provide anime episode video files. The automatic source adapter therefore uses Internet Archive records that advertise Creative Commons/public-domain style rights markers. This means the bot can be fully automatic, but it cannot guarantee that every mainstream anime title will have a suitable rights-approved video available there.

The bot does not scrape protected streaming sites or bypass DRM, authentication, paywalls, anti-bot systems, or other access controls.

## Change genres

Edit the workflow:

```yaml
ANIME_GENRES: "Action,Fantasy"
```

Multiple genres are treated as **ALL**: an anime must contain every listed genre.

## No content filter

There is no SFW/NSFW/category filter in the anime selection logic.

## Instagram requirements

Your Instagram account and Meta app must be configured for Instagram Graph API Reel publishing, and the access token/user ID must have the required permissions for your account.

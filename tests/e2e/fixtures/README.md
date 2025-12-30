# E2E Test Fixtures

This directory contains test fixtures for E2E testing of the stream handler pipeline.

## Required Fixtures

### 1-min-nfl.mp4 (Primary Test Fixture)

A 60-second video file used for all E2E tests.

**Required Properties:**
- **Duration**: 60 seconds
- **Video Codec**: H.264 (libx264)
- **Video Resolution**: 1280x720 (720p)
- **Video Frame Rate**: 30 fps
- **Audio Codec**: AAC
- **Audio Sample Rate**: 48000 Hz
- **Audio Channels**: 2 (stereo)

**Expected Segments**: 10 segments (6 seconds each)

## Obtaining Test Fixtures

### Option 1: Use Big Buck Bunny (Recommended)

Download the 60-second clip from Blender Foundation:

```bash
# Download Big Buck Bunny (public domain)
curl -L -o 1-min-nfl.mp4 "https://download.blender.org/demo/movies/BBB/bbb_sunflower_1080p_60fps_normal.mp4"

# Convert to required format (720p, 60s)
ffmpeg -i bbb_sunflower_1080p_60fps_normal.mp4 \
  -t 60 \
  -vf "scale=1280:720" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -ar 48000 -ac 2 \
  1-min-nfl.mp4

rm bbb_sunflower_1080p_60fps_normal.mp4
```

### Option 2: Generate Synthetic Test Video

Generate a test pattern video with ffmpeg:

```bash
ffmpeg -f lavfi -i "testsrc2=duration=60:size=1280x720:rate=30" \
  -f lavfi -i "sine=frequency=440:duration=60:sample_rate=48000" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -ar 48000 -ac 2 \
  -shortest \
  1-min-nfl.mp4
```

### Option 3: Use Your Own Video

Any video file can be used as long as it meets the required properties.
Convert using:

```bash
ffmpeg -i your_video.mp4 \
  -t 60 \
  -vf "scale=1280:720" \
  -r 30 \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -ar 48000 -ac 2 \
  1-min-nfl.mp4
```

## Verifying Fixture Properties

Use ffprobe to verify fixture properties:

```bash
ffprobe -v quiet -print_format json -show_format -show_streams tests/e2e/fixtures/test-streams/1-min-nfl.mp4
```

Expected output:
```json
{
  "format": {
    "duration": "60.000000",
    "format_name": "mov,mp4,m4a,3gp,3g2,mj2"
  },
  "streams": [
    {
      "codec_name": "h264",
      "codec_type": "video",
      "width": 1280,
      "height": 720,
      "r_frame_rate": "30/1"
    },
    {
      "codec_name": "aac",
      "codec_type": "audio",
      "sample_rate": "48000",
      "channels": 2
    }
  ]
}
```

## Automated Verification

The conftest.py includes a `verify_test_fixture` fixture that automatically
validates fixture properties before E2E tests run.

## Notes

- Test fixtures are NOT committed to git (see .gitignore)
- CI/CD pipeline should download/generate fixtures as part of setup
- Keep fixture files small for faster CI execution
- The 60-second duration is chosen to produce exactly 10 segments (6s each)

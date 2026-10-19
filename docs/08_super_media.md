# ⚡ Super Media: dHash Video Reducer & Timeline Sync (`super_media` module)

The `super_media` module reduces video frames by up to 88% using Perceptual dHash comparisons, and synchronizes audio transcript timestamps with keyframe visual cards.

## Features
- **dHash Reducer (<12% Difference):** Discards nearly identical duplicate frames, cutting video token cost dramatically.
- **Audio-Visual Timeline Sync:** Merges STT transcribed sentences with their exact visual frame snapshots.
- **Categorized Smart Archive Blueprint:** Classifies archive contents into Docs, Config, Code, Media, and Build/Trash.

## Commands

### 1. Video Intelligent Reducer
```bash
ai-tool super-media video /path/to/video.mp4 --threshold 0.12 --interval 1s
```
Extracts only unique, non-redundant visual frames and binds them to audio timestamps.

### 2. Smart Categorized Archive
```bash
ai-tool super-media archive /path/to/project.zip
```
Outputs a categorized 5-tier blueprint of any codebase archive in 0 tokens.

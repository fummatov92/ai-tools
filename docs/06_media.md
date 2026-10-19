# 🎬 Interoperable Media Intelligence (`media` module)

The `media` module extracts structured metadata, frames, audio transcripts, OCR text, and archive inspection without external cloud APIs.

## Commands

### 1. Video Analysis
```bash
ai-tool media video /path/to/video.mp4 --interval 2s --extract-audio
ai-tool media video /path/to/video.mp4 --scene-change
```
Extracts keyframes at specified intervals or scene changes and separates audio tracks.

### 2. Audio Processing & STT
```bash
ai-tool media audio /path/to/audio.oga --silence-removal --transcribe
```
Splits audio into 30s chunks, strips silence, and performs Speech-to-Text transcription.

### 3. Image OCR & dHash
```bash
ai-tool media image /path/to/image.png --ocr --palette-size 5
```
Extracts EXIF, calculates Perceptual dHash/aHash, detects dominant color palettes, and performs OCR.

### 4. Zero-Extract Archive Inspection
```bash
ai-tool media archive /path/to/archive.zip
ai-tool media archive /path/to/archive.zip --view-file internal/file.py
```
Safely inspects archive hierarchies in memory, prevents Zip-Bomb attacks, and reads individual files without unpacking the entire archive.

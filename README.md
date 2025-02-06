# Subtitle Processing Tool

A command-line Python tool for extracting, generating, and translating video subtitles. The tool supports subtitle extraction from video files, speech-to-text subtitle generation, and subtitle translation.

## Features

- Extract existing subtitle tracks from mkv files
- Generate subtitles from video audio using OpenAI Whisper
- Translate subtitles to different languages using OpenAI API
- Support for batch processing of files in folders

## Prerequisites

- mkvmerge and mkvextract (part of MKVToolNix)
- ffmpeg
- [OpenAI Whisper](https://github.com/openai/whisper)
- OpenAI API key (for translation feature)

## Good things to know

- Currently using Whisper "medium.en" model for English-only audio. Can be changed to other models (tiny, base, small, medium, large) for multilingual support. See [available models](https://github.com/openai/whisper?tab=readme-ov-file#available-models-and-languages)

import os
import subprocess
import whisper
from pathlib import Path
from typing import List, Dict
import re
from openai import OpenAI
import time
import threading
import json

class SubtitleProcessor:
    def __init__(self, config_path='config.json'):
        try:
            with open(config_path, 'r') as config_file:
                config = json.load(config_file)
                openai_api_key = config.get('openai_api_key')
                self.openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        except FileNotFoundError:
            print(f"Config file {config_path} not found.")
            self.openai_client = None
        except json.JSONDecodeError:
            print(f"Invalid JSON in {config_path}.")
            self.openai_client = None

    def extract_subtitle_tracks(self, mkv_file: str) -> List[str]:
        try:
            list_tracks_cmd = ['mkvmerge', '-i', mkv_file]
            result = subprocess.run(list_tracks_cmd, capture_output=True, text=True)
            subtitle_track_ids = []
            
            for line in result.stdout.split('\n'):
                if 'subtitles' in line:
                    track_id = re.search(r"Track ID (\d+): subtitles", line)
                    if track_id:
                        subtitle_track_ids.append(track_id.group(1))
            
            return subtitle_track_ids
        except Exception as e:
            print(f"Error extracting subtitle tracks: {e}")
            return []

    def extract_subtitles_from_mkv(self, mkv_file: str, output_dir: str) -> List[str]:
        os.makedirs(output_dir, exist_ok=True)
        subtitle_track_ids = self.extract_subtitle_tracks(mkv_file)
        extracted_subtitles = []

        for track_id in subtitle_track_ids:
            filename = os.path.basename(mkv_file)
            dst_srt_path = os.path.join(output_dir, f"{filename.rsplit('.', 1)[0]}_track{track_id}.srt")
            command = ['mkvextract', mkv_file, 'tracks', f'{track_id}:{dst_srt_path}']
            subprocess.run(command)
            extracted_subtitles.append(dst_srt_path)

        return extracted_subtitles

    def extract_audio(self, video_path: str, audio_path: str) -> None:
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        command = [
            'ffmpeg', '-i', video_path,
            '-vn', '-acodec', 'pcm_s16le',
            '-ar', '44100', '-ac', '2',
            audio_path, '-y'
        ]
        subprocess.run(command, check=True, capture_output=True)

    def generate_subtitles_with_whisper(self, video_path: str, language: str = None) -> str:
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        output_srt_path = os.path.splitext(video_path)[0] + ".srt"
        audio_path = f"{os.path.splitext(video_path)[0]}_temp.wav"
        
        try:
            print("Extracting audio...")
            self.extract_audio(video_path, audio_path)
            
            print("Generating subtitles with Whisper...")
            model = whisper.load_model("medium.en")
            
            transcribe_options = {
                "word_timestamps": True,
                "verbose": None
            }
            if language:
                transcribe_options["language"] = language
            
            result = model.transcribe(audio_path, **transcribe_options)
            
            with open(output_srt_path, "w", encoding="utf-8") as f:
                for i, segment in enumerate(result["segments"], start=1):
                    start = self._format_time(segment["start"])
                    end = self._format_time(segment["end"])
                    text = segment["text"].strip()
                    f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
            
            os.remove(audio_path)
            
            print(f"Subtitle file saved to: {output_srt_path}")
            return output_srt_path
        
        except Exception as e:
            print(f"Error generating subtitles: {e}")
            if os.path.exists(audio_path):
                os.remove(audio_path)
            return None

    def translate_subtitles(self, input_path: str, target_language: str) -> str:
        if not self.openai_client:
            print("OpenAI API key not set. Cannot translate.")
            return None

        if not os.path.exists(input_path):
            print(f"Input file not found: {input_path}")
            return None

        output_path = os.path.splitext(input_path)[0] + f".{target_language.lower()}.srt"

        try:
            with open(input_path, 'r', encoding='utf-8') as infile, \
                 open(output_path, 'w', encoding='utf-8') as outfile:
                dialogue_blocks = []
                current_block = ""

                for line in infile:
                    if line.strip().isdigit():
                        if current_block:
                            dialogue_blocks.append(current_block)
                            current_block = ""
                        current_block += line
                    elif "-->" in line:
                        current_block += line
                    elif line.strip() == "":
                        continue
                    else:
                        current_block += line

                    if len(dialogue_blocks) == 5:
                        translated_block = self._translate_block(
                            "\n".join(dialogue_blocks), 
                            target_language
                        ).strip()
                        outfile.write(translated_block + "\n\n")
                        dialogue_blocks = []

                if current_block:
                    dialogue_blocks.append(current_block)

                if dialogue_blocks:
                    translated_block = self._translate_block(
                        "\n".join(dialogue_blocks), 
                        target_language
                    ).strip()
                    outfile.write(translated_block + "\n")

            print(f"Translated subtitle saved to: {output_path}")
            return output_path
        
        except Exception as e:
            print(f"Translation error: {e}")
            return None

    def _translate_block(self, dialogue_block: str, target_language: str) -> str:
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {
                    "role": "system", 
                    "content": f"Translate the following English subtitles into {target_language}. Maintain the original subtitle numbering and timing. Translate accurately."
                },
                {"role": "user", "content": dialogue_block}
            ]
        )
        
        return response.choices[0].message.content.strip()

    def _format_time(self, seconds: float) -> str:
        milliseconds = int((seconds % 1) * 1000)
        total_seconds = int(seconds)
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def main():
    processor = SubtitleProcessor()
    
    while True:
        print("\nSubtitle Processing Tool")
        print("1. Extract subtitles from video files")
        print("2. Generate subtitles with Whisper") 
        print("3. Translate subtitles")
        print("4. Exit")
        
        choice = input("Enter your choice (1-4): ").strip()

        if choice in ['1', '2', '3']:
            mode = input("Process single file or folder? (single/folder): ").strip().lower()
            
            if mode == 'single':
                if choice == '1':
                    mkv_path = input("Enter path to video file: ").strip()
                    if not os.path.exists(mkv_path):
                        print("File does not exist.")
                        continue
                    output_dir = os.path.dirname(mkv_path)
                    processor.extract_subtitles_from_mkv(mkv_path, output_dir)
                    
                elif choice == '2':
                    video_path = input("Enter path to video file: ").strip()
                    if not os.path.exists(video_path):
                        print("File does not exist.")
                        continue
                    language = 'en'  # Set default language to English
                    processor.generate_subtitles_with_whisper(video_path, language)

                    
                elif choice == '3':
                    if not processor.openai_client:
                        print("OpenAI API key not configured in config.json.")
                        continue
                    input_srt = input("Enter path to input SRT file: ").strip()
                    if not os.path.exists(input_srt):
                        print("File does not exist.")
                        continue
                    target_lang = input("Enter target language (e.g., Swedish, French): ").strip()
                    processor.translate_subtitles(input_srt, target_lang)
                    
            elif mode == 'folder':
                folder_path = input("Enter folder path: ").strip()
                if not os.path.isdir(folder_path):
                    print("Invalid folder path")
                    continue
                
                # Ask for target language once when translating multiple files
                target_lang = None
                if choice == '3':
                    if not processor.openai_client:
                        print("OpenAI API key not configured in config.json.")
                        continue
                    target_lang = input("Enter target language for all files (e.g., Swedish, French): ").strip()
                
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        
                        if choice == '1' and file.lower().endswith(('.mkv','.mp4','.avi','.webm')):
                            output_dir = os.path.dirname(file_path)
                            processor.extract_subtitles_from_mkv(file_path, output_dir)
                            
                        elif choice == '2' and file.lower().endswith(('.mkv','.mp4','.avi','.webm')):
                            processor.generate_subtitles_with_whisper(file_path, 'en')
                            
                        elif choice == '3' and file.lower().endswith('.srt'):
                            processor.translate_subtitles(file_path, target_lang)

        elif choice == '4':
            print("Exiting...")
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()

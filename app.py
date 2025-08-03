"""
YouTube Downloader - Versión Simplificada

Descarga videos de YouTube como MP3 o MP4 directamente a tu navegador.
Sin necesidad de cookies o configuración complicada.

Funciona con:
- Videos públicos de YouTube
- Descargas directas al navegador
- Reconexión automática si hay errores temporales
"""

from flask import Flask, request, send_file, jsonify, render_template
import yt_dlp
import os
import re
import tempfile
import logging
import time
import shutil
import uuid
import random
import subprocess
import sys
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = '7772428b-01cf-4d05-9c3e-cea510398586'

# Configure logging with better format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Set FFmpeg path - adjust this to your specific location if needed
FFMPEG_PATH = r"C:\\ffmpeg\\bin"

# Updated user agents for 2025 - more diverse and recent
USER_AGENTS = [
    # Chrome variants
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    
    # Firefox variants
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    
    # Edge variants
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    
    # Mobile variants
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Android 14; Mobile; rv:133.0) Gecko/133.0 Firefox/133.0",
    "Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
]

def get_random_headers():
    """Generate random headers to help avoid detection."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0"
    }

def get_extraction_strategies():
    """Get ultra-aggressive extraction strategies to bypass YouTube blocks."""
    base_headers = get_random_headers()
    
    strategies = [
        # Strategy 1: Android TV - Often less restricted
        {
            "name": "Android TV",
            "options": {
                "http_headers": {
                    **base_headers,
                    "User-Agent": "com.google.android.youtube.tv/1.12.08 (Linux; U; Android 9) gzip"
                },
                "nocheckcertificate": True,
                "geo_bypass": True,
                "geo_bypass_country": "US",
                "socket_timeout": 20,
                "retries": 2,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android_testsuite", "android_vr"],
                        "player_skip": ["configs", "webpage", "js"],
                        "include_live_dash": False,
                        "include_hls": False,
                    }
                },
                "format_sort": ["res:480", "ext:mp4:m4a"],
                "writeinfojson": False,
                "writesubtitles": False,
            }
        },
        
        # Strategy 2: YouTube Music API
        {
            "name": "YouTube Music",
            "options": {
                "http_headers": {
                    "User-Agent": "com.google.android.apps.youtube.music/5.26.52 (Linux; U; Android 11; SM-G973F) gzip",
                    "X-YouTube-Client-Name": "21",
                    "X-YouTube-Client-Version": "5.26.52",
                },
                "nocheckcertificate": True,
                "geo_bypass": True,
                "socket_timeout": 15,
                "retries": 1,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android_music"],
                        "player_skip": ["configs", "webpage", "js", "dash", "hls"],
                    }
                }
            }
        },
        
        # Strategy 3: Embedded player bypass
        {
            "name": "Embedded Player",
            "options": {
                "http_headers": {
                    **base_headers,
                    "Referer": "https://www.youtube-nocookie.com/",
                    "Origin": "https://www.youtube-nocookie.com"
                },
                "nocheckcertificate": True,
                "geo_bypass": True,
                "socket_timeout": 15,
                "retries": 1,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["tv_embedded"],
                        "player_skip": ["configs", "webpage", "dash"],
                    }
                }
            }
        },
        
        # Strategy 4: Web scraping mode
        {
            "name": "Web Scraper",
            "options": {
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Accept": "*/*",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                },
                "nocheckcertificate": True,
                "geo_bypass": True,
                "geo_bypass_country": random.choice(["NL", "SE", "NO", "CH"]),
                "socket_timeout": 10,
                "retries": 1,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["web"],
                        "player_skip": ["configs"],
                    }
                }
            }
        },
        
        # Strategy 5: iOS native app
        {
            "name": "iOS Native",
            "options": {
                "http_headers": {
                    "User-Agent": "com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5 like Mac OS X;)",
                    "X-YouTube-Client-Name": "5",
                    "X-YouTube-Client-Version": "19.29.1",
                },
                "nocheckcertificate": True,
                "geo_bypass": True,
                "socket_timeout": 15,
                "retries": 1,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["ios"],
                        "player_skip": ["webpage", "configs"],
                    }
                }
            }
        },
        
        # Strategy 6: Alternative extraction
        {
            "name": "Alternative",
            "options": {
                "http_headers": base_headers,
                "nocheckcertificate": True,
                "geo_bypass": True,
                "geo_bypass_country": "CA",
                "socket_timeout": 30,
                "retries": 3,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android_creator", "android_vr"],
                        "player_skip": ["webpage"],
                    }
                },
                "format_sort": ["quality", "res", "fps"],
            }
        }
    ]
    
    return strategies

def get_robust_options():
    """Get the most robust options as fallback."""
    return get_extraction_strategies()[0]["options"]



def clean_filename(title):
    """Removes special characters and shortens the filename."""
    title = re.sub(r'[\\/*?:"<>|]', '', title)
    return title[:50]

def update_yt_dlp():
    """Update yt-dlp to the latest version."""
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], check=True)
        logger.info("Successfully updated yt-dlp to the latest version")
        return True
    except Exception as e:
        logger.error(f"Failed to update yt-dlp: {str(e)}")
        return False

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_video_info", methods=["POST"])
def get_video_info():
    """Endpoint to fetch video information without downloading."""
    data = request.get_json()
    video_url = data.get("url")
    
    if not video_url:
        return jsonify({"error": "No URL provided"}), 400
    
    # Try multiple extraction strategies
    strategies = get_extraction_strategies()
    last_error = None
    
    for i, strategy in enumerate(strategies):
        try:
            strategy_name = strategy.get("name", f"Strategy {i+1}")
            logger.info(f"🔄 Trying extraction strategy {i+1}/6: {strategy_name}")
            
            options = {
                "skip_download": True,
                "quiet": True,
                "no_warnings": True,
                **strategy.get("options", {})
            }
            
            # Progressive delay - more aggressive with each failure
            if i > 0:
                delay = min(2 ** i, 10)  # Exponential backoff, max 10 seconds
                logger.info(f"⏳ Waiting {delay}s before retry...")
                time.sleep(delay)
            
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(video_url, download=False)
                
                if info and info.get("title"):
                    logger.info(f"🎉 SUCCESS with {strategy_name}")
                    return jsonify({
                        "title": info.get("title"),
                        "duration": info.get("duration"),
                        "thumbnail": info.get("thumbnail"),
                        "channel": info.get("uploader"),
                        "views": info.get("view_count")
                    })
                else:
                    raise Exception("No video information extracted")
                
        except Exception as e:
            last_error = e
            error_msg = str(e)
            logger.warning(f"❌ {strategy_name} failed: {error_msg[:100]}...")
            
            # If it's a rate limit, wait longer
            if "rate limit" in error_msg.lower() or "too many requests" in error_msg.lower():
                logger.info("⏳ Rate limited, waiting 15 seconds...")
                time.sleep(15)
            
            continue
    
    # All strategies failed
    logger.error("All extraction strategies failed")
    
    if last_error:
        error_str = str(last_error)
        if "HTTP Error 403" in error_str or "Forbidden" in error_str:
            logger.info("🔄 Updating yt-dlp due to video info 403 error...")
            update_yt_dlp()
            return jsonify({"error": "YouTube bloqueó la solicitud. Sistema actualizado. Intenta de nuevo en unos minutos."}), 503
        elif "Sign in to confirm" in error_str or "bot" in error_str.lower():
            return jsonify({"error": "YouTube detectó actividad de bot. Espera 10 minutos antes de intentar de nuevo."}), 429
        elif "player response" in error_str.lower() or "extract" in error_str.lower():
            return jsonify({"error": "YouTube cambió su sistema de protección. Intenta con un video diferente."}), 503
        elif "private" in error_str.lower() or "unavailable" in error_str.lower():
            return jsonify({"error": "Este video no está disponible o es privado."}), 404
    
    return jsonify({"error": "YouTube está bloqueando temporalmente. Intenta en 15-30 minutos o con un video diferente."}), 503

@app.route("/convert", methods=["POST"])
def convert():
    data = request.get_json()
    video_url = data.get("url")
    video_format = data.get("format")  # "mp3" or "mp4"

    if not video_url:
        return jsonify({"error": "No URL provided"}), 400

    # Create the main temporary directory for this request
    request_tmpdir = tempfile.mkdtemp()
    
    # Try multiple extraction strategies for downloads
    strategies = get_extraction_strategies()
    last_error = None
    
    for i, strategy in enumerate(strategies):
        try:
            strategy_name = strategy.get("name", f"Strategy {i+1}")
            logger.info(f"🔄 Trying download strategy {i+1}/6: {strategy_name}")
            
            # Configure yt-dlp options based on format and strategy
            common_options = {
                "outtmpl": os.path.join(request_tmpdir, "%(id)s.%(ext)s"),
                "ffmpeg_location": FFMPEG_PATH,
                "no_warnings": True,
                **strategy.get("options", {})
            }
            
            # Progressive delay - more aggressive with each failure
            if i > 0:
                delay = min(3 * i, 20)  # Progressive delay, max 20 seconds
                logger.info(f"⏳ Waiting {delay}s before download retry...")
                time.sleep(delay)
            
            if video_format == "mp4":
                options = {
                    **common_options,
                    "format": "best[height<=720][ext=mp4]/best[ext=mp4]/mp4/best",
                    "merge_output_format": "mp4"
                }
            else:  # mp3
                options = {
                    **common_options,
                    "format": "bestaudio[ext=m4a]/bestaudio/best",
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ]
                }

            logger.info(f"Created temporary directory: {request_tmpdir}")
            
            with yt_dlp.YoutubeDL(options) as ydl:
                logger.info(f"⬇️ Downloading {video_url} as {video_format} using {strategy_name}")
                
                # Extract info and download
                info = ydl.extract_info(video_url, download=True)
                
                if not info or not info.get("title"):
                    raise Exception("No video information extracted")
                
                video_id = info["id"]
                title = clean_filename(info["title"])
                ext = "mp4" if video_format == "mp4" else "mp3"
                
                # Search for downloaded file more aggressively
                expected_file = None
                for file in os.listdir(request_tmpdir):
                    if (file.startswith(video_id) or 
                        title.lower() in file.lower() or 
                        os.path.splitext(file)[1].lower() == f".{ext}"):
                        expected_file = os.path.join(request_tmpdir, file)
                        logger.info(f"📁 Found downloaded file: {file}")
                        break
                
                if not expected_file or not os.path.exists(expected_file):
                    # Try default name
                    expected_file = os.path.join(request_tmpdir, f"{video_id}.{ext}")
                    if not os.path.exists(expected_file):
                        files = os.listdir(request_tmpdir)
                        logger.error(f"❌ Downloaded file not found. Files in directory: {files}")
                        raise FileNotFoundError(f"Downloaded file not found. Available files: {files}")
                    
                # Create a copy of the file to avoid access issues
                copy_filename = f"{uuid.uuid4()}.{ext}"
                copy_filepath = os.path.join(request_tmpdir, copy_filename)
                
                # Wait for the file to be completely written and try to copy it
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        shutil.copy2(expected_file, copy_filepath)
                        logger.info(f"📋 Successfully copied file to: {copy_filename}")
                        break
                    except (OSError, IOError) as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"⏳ File access error (attempt {attempt+1}), retrying in 2 seconds...")
                            time.sleep(2)
                        else:
                            raise
                
                # Verify file exists and has content
                if not os.path.exists(copy_filepath) or os.path.getsize(copy_filepath) == 0:
                    raise Exception("Downloaded file is empty or corrupted")
                
                # Set correct mime type
                mime_type = "audio/mpeg" if ext == "mp3" else "video/mp4"
                
                # Send the copied file to the client
                response = send_file(
                    copy_filepath, 
                    as_attachment=True, 
                    download_name=f"{title}.{ext}",
                    mimetype=mime_type
                )
                
                # Setup a callback to remove the temp directory after the response is sent
                @response.call_on_close
                def cleanup():
                    try:
                        logger.info(f"🧹 Cleaning up temporary directory: {request_tmpdir}")
                        shutil.rmtree(request_tmpdir, ignore_errors=True)
                    except Exception as e:
                        logger.error(f"Error cleaning up: {str(e)}")
                
                logger.info(f"🎉 DOWNLOAD SUCCESS with {strategy_name} - {title}.{ext}")
                return response
                
        except Exception as e:
            last_error = e
            error_msg = str(e)
            logger.warning(f"❌ Download strategy {strategy_name} failed: {error_msg[:100]}...")
            
            # Clear any partial downloads from this attempt
            try:
                for file in os.listdir(request_tmpdir):
                    file_path = os.path.join(request_tmpdir, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        logger.debug(f"🗑️ Removed partial file: {file}")
            except Exception as cleanup_error:
                logger.debug(f"Cleanup error: {cleanup_error}")
            
            # If it's a rate limit, wait longer
            if "rate limit" in error_msg.lower() or "too many requests" in error_msg.lower():
                logger.info("⏳ Rate limited during download, waiting 20 seconds...")
                time.sleep(20)
            
            continue
    
    # All strategies failed - cleanup and return error
    try:
        shutil.rmtree(request_tmpdir, ignore_errors=True)
    except:
        pass
    
    logger.error("🚫 ALL DOWNLOAD STRATEGIES FAILED")
    
    if last_error:
        error_str = str(last_error)
        if "HTTP Error 403" in error_str or "Forbidden" in error_str:
            logger.info("🔄 Updating yt-dlp due to 403 error...")
            update_yt_dlp()
            return jsonify({"error": "YouTube bloqueó la solicitud. Sistema actualizado. Intenta en 5 minutos."}), 503
        elif "Sign in to confirm" in error_str or "bot" in error_str.lower():
            return jsonify({"error": "YouTube detectó actividad de bot. Espera 10 minutos antes de intentar de nuevo."}), 429
        elif "player response" in error_str.lower() or "extract" in error_str.lower():
            return jsonify({"error": "YouTube cambió su sistema de protección. Intenta con un video diferente."}), 503
        elif "private" in error_str.lower() or "unavailable" in error_str.lower():
            return jsonify({"error": "Este video no está disponible o es privado."}), 404
        elif "age" in error_str.lower() and "restrict" in error_str.lower():
            return jsonify({"error": "Este video tiene restricción de edad y no se puede descargar."}), 403
    
    return jsonify({"error": "YouTube está bloqueando todas las descargas temporalmente. Intenta en 15-30 minutos o con un video diferente."}), 503

@app.route("/update_ytdlp", methods=["POST"])
def update_ytdlp_route():
    """Route to manually trigger an update of yt-dlp."""
    success = update_yt_dlp()
    if success:
        return jsonify({"message": "yt-dlp updated successfully"}), 200
    else:
        return jsonify({"error": "Failed to update yt-dlp"}), 500



if __name__ == '__main__':
    app.run()
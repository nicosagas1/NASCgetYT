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

# Configure logging
logging.basicConfig(level=logging.INFO)
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
    """Get multiple extraction strategies to try sequentially."""
    base_headers = get_random_headers()
    
    strategies = [
        # Strategy 1: Standard Android client
        {
            "name": "Android Client",
            "options": {
                "http_headers": base_headers,
                "nocheckcertificate": True,
                "geo_bypass": True,
                "geo_bypass_country": "US",
                "socket_timeout": 30,
                "retries": 3,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android"],
                        "player_skip": ["configs", "webpage"],
                    }
                }
            }
        },
        
        # Strategy 2: iOS client with mobile headers
        {
            "name": "iOS Client", 
            "options": {
                "http_headers": {
                    **base_headers,
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1"
                },
                "nocheckcertificate": True,
                "geo_bypass": True,
                "socket_timeout": 30,
                "retries": 3,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["ios"],
                    }
                }
            }
        },
        
        # Strategy 3: Web client with TV user agent
        {
            "name": "TV Client",
            "options": {
                "http_headers": {
                    **base_headers,
                    "User-Agent": "Mozilla/5.0 (SMART-TV; Linux; Tizen 2.4.0) AppleWebKit/538.1 (KHTML, like Gecko) Version/2.4.0 TV Safari/538.1"
                },
                "nocheckcertificate": True,
                "geo_bypass": True,
                "socket_timeout": 30,
                "retries": 3,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["tv_embedded"],
                        "player_skip": ["configs"],
                    }
                }
            }
        },
        
        # Strategy 4: Android Music with different approach
        {
            "name": "Android Music",
            "options": {
                "http_headers": {
                    **base_headers,
                    "User-Agent": "Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
                },
                "nocheckcertificate": True,
                "geo_bypass": True,
                "socket_timeout": 45,
                "retries": 5,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android_music", "android_creator"],
                        "player_skip": ["webpage"],
                    }
                }
            }
        },
        
        # Strategy 5: Web with aggressive anti-detection
        {
            "name": "Web Stealth",
            "options": {
                "http_headers": {
                    **base_headers,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="131", "Google Chrome";v="131"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1"
                },
                "nocheckcertificate": True,
                "geo_bypass": True,
                "geo_bypass_country": random.choice(["US", "CA", "GB", "DE", "FR"]),
                "socket_timeout": 60,
                "retries": 10,
                "sleep_interval": 2,
                "max_sleep_interval": 5,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["web", "android"],
                        "player_skip": ["configs"],
                    }
                }
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
            logger.info(f"Trying extraction strategy {i+1}/5: {strategy['name']}")
            
            options = {
                "skip_download": True,
                "quiet": True,
                **strategy["options"]
            }
            
            # Add small delay between attempts
            if i > 0:
                time.sleep(random.uniform(1, 3))
            
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(video_url, download=False)
                
                logger.info(f"✅ Success with {strategy['name']}")
                return jsonify({
                    "title": info.get("title"),
                    "duration": info.get("duration"),
                    "thumbnail": info.get("thumbnail"),
                    "channel": info.get("uploader"),
                    "views": info.get("view_count")
                })
                
        except Exception as e:
            last_error = e
            logger.warning(f"❌ {strategy['name']} failed: {str(e)}")
            continue
    
    # All strategies failed
    logger.error("All extraction strategies failed")
    
    if last_error:
        error_str = str(last_error)
        if "HTTP Error 403: Forbidden" in error_str:
            if update_yt_dlp():
                return jsonify({"error": "Sistema actualizado. Intenta de nuevo."}), 503
        elif "Sign in to confirm you're not a bot" in error_str:
            return jsonify({"error": "YouTube detectó actividad de bot. Intenta con otro video o espera unos minutos."}), 429
    
    return jsonify({"error": "No se pudo extraer información del video. YouTube puede estar bloqueando las solicitudes temporalmente."}), 503

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
            logger.info(f"Trying download strategy {i+1}/5: {strategy['name']}")
            
            # Configure yt-dlp options based on format and strategy
            common_options = {
                "outtmpl": os.path.join(request_tmpdir, "%(id)s.%(ext)s"),
                "ffmpeg_location": FFMPEG_PATH,
                **strategy["options"]
            }
            
            # Add delay between attempts
            if i > 0:
                time.sleep(random.uniform(2, 5))
                logger.info(f"Waiting before retry...")
            
            if video_format == "mp4":
                options = {
                    **common_options,
                    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/mp4"
                }
            else:  # mp3
                options = {
                    **common_options,
                    "format": "bestaudio/best",
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
                logger.info(f"Downloading {video_url} as {video_format} using {strategy['name']}")
                
                # Extract info and download
                info = ydl.extract_info(video_url, download=True)
                video_id = info["id"]
                title = clean_filename(info["title"])
                ext = "mp4" if video_format == "mp4" else "mp3"
                
                expected_file = os.path.join(request_tmpdir, f"{video_id}.{ext}")
                
                # Find the file if it doesn't match expected name
                if not os.path.exists(expected_file):
                    logger.info(f"Expected file {expected_file} not found, searching directory")
                    for file in os.listdir(request_tmpdir):
                        if file.startswith(video_id) or os.path.splitext(file)[1].lower() == f".{ext}":
                            expected_file = os.path.join(request_tmpdir, file)
                            logger.info(f"Found file: {expected_file}")
                            break
                
                if not os.path.exists(expected_file):
                    raise FileNotFoundError("Downloaded file not found")
                    
                # Create a copy of the file to avoid access issues
                copy_filename = f"{uuid.uuid4()}.{ext}"
                copy_filepath = os.path.join(request_tmpdir, copy_filename)
                
                # Wait for the file to be completely written and try to copy it
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        shutil.copy2(expected_file, copy_filepath)
                        logger.info(f"Successfully copied file to: {copy_filepath}")
                        break
                    except (OSError, IOError) as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"File access error (attempt {attempt+1}), retrying in 1 second: {str(e)}")
                            time.sleep(1)
                        else:
                            raise
                
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
                        logger.info(f"Cleaning up temporary directory: {request_tmpdir}")
                        shutil.rmtree(request_tmpdir, ignore_errors=True)
                    except Exception as e:
                        logger.error(f"Error cleaning up temporary directory: {str(e)}")
                
                logger.info(f"✅ Download successful with {strategy['name']}")
                return response
                
        except Exception as e:
            last_error = e
            logger.warning(f"❌ Download strategy {strategy['name']} failed: {str(e)}")
            # Clear any partial downloads from this attempt
            try:
                for file in os.listdir(request_tmpdir):
                    os.remove(os.path.join(request_tmpdir, file))
            except:
                pass
            continue
    
    # All strategies failed - cleanup and return error
    try:
        shutil.rmtree(request_tmpdir, ignore_errors=True)
    except:
        pass
    
    logger.error("All download strategies failed")
    
    if last_error:
        error_str = str(last_error)
        if "HTTP Error 403: Forbidden" in error_str:
            update_yt_dlp()
            return jsonify({"error": "Sistema actualizado. Intenta de nuevo."}), 503
        elif "Sign in to confirm you're not a bot" in error_str:
            return jsonify({"error": "YouTube detectó actividad de bot. Intenta con otro video o espera unos minutos."}), 429
        elif "Failed to extract any player response" in error_str:
            return jsonify({"error": "YouTube cambió su sistema. Intenta con otro video o espera unos minutos."}), 503
    
    return jsonify({"error": "No se pudo descargar el video. YouTube puede estar bloqueando las solicitudes temporalmente."}), 503

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
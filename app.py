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
    """Get working extraction strategies that actually bypass YouTube in 2025."""
    
    strategies = [
        # Strategy 1: Simple Android - Most reliable
        {
            "name": "Android Simple",
            "options": {
                "nocheckcertificate": True,
                "socket_timeout": 30,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android"],
                    }
                }
            }
        },
        
        # Strategy 2: iOS - Often works when others fail
        {
            "name": "iOS",
            "options": {
                "nocheckcertificate": True,
                "socket_timeout": 30,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["ios"],
                    }
                }
            }
        },
        
        # Strategy 3: Android TV Embedded
        {
            "name": "Android TV",
            "options": {
                "nocheckcertificate": True,
                "socket_timeout": 30,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["tv_embedded"],
                    }
                }
            }
        },
        
        # Strategy 4: Web with minimal config
        {
            "name": "Web Clean",
            "options": {
                "nocheckcertificate": True,
                "socket_timeout": 30,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["web"],
                    }
                }
            }
        },
        
        # Strategy 5: Android Music
        {
            "name": "Music",
            "options": {
                "nocheckcertificate": True,
                "socket_timeout": 30,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android_music"],
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
        logger.info("🔄 Updating yt-dlp...")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], 
                              capture_output=True, text=True, check=True)
        logger.info("✅ Successfully updated yt-dlp")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to update yt-dlp: {str(e)}")
        return False

def check_yt_dlp_version():
    """Check and ensure we have a working yt-dlp version."""
    try:
        import yt_dlp
        logger.info(f"yt-dlp version: {yt_dlp.version.__version__}")
        return True
    except Exception as e:
        logger.warning(f"yt-dlp version check failed: {e}")
        return update_yt_dlp()

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
            logger.info(f"🔄 Trying info extraction {i+1}/5: {strategy_name}")
            
            options = {
                "skip_download": True,
                "quiet": True,
                "no_warnings": True,
                **strategy.get("options", {})
            }
            
            # Simple delay between attempts
            if i > 0:
                delay = 3 + i  # 3, 4, 5, 6, 7 seconds
                logger.info(f"⏳ Waiting {delay}s...")
                time.sleep(delay)
            
            with yt_dlp.YoutubeDL(options) as ydl:
                logger.info(f"📊 Extracting video info using {strategy_name}")
                info = ydl.extract_info(video_url, download=False)
                
                if info and info.get("title"):
                    logger.info(f"🎉 INFO SUCCESS with {strategy_name}: {info.get('title')}")
                    return jsonify({
                        "title": info.get("title"),
                        "duration": info.get("duration"),
                        "thumbnail": info.get("thumbnail"),
                        "channel": info.get("uploader"),
                        "views": info.get("view_count")
                    })
                else:
                    raise Exception("No video information found")
                
        except Exception as e:
            last_error = e
            error_msg = str(e)
            logger.warning(f"❌ {strategy_name} failed: {error_msg[:150]}")
            continue
    
    # All strategies failed
    logger.error("All extraction strategies failed")
    
    # Final error handling
    logger.error("🚫 ALL INFO EXTRACTION FAILED")
    
    if last_error:
        error_str = str(last_error)
        logger.error(f"Last error was: {error_str}")
        
        # Try updating yt-dlp as last resort
        logger.info("🔄 Attempting yt-dlp update as last resort...")
        update_yt_dlp()
        
        return jsonify({"error": "No se pudo obtener información del video. Sistema actualizado automáticamente. Intenta con otro video o espera 10 minutos."}), 503
    
    return jsonify({"error": "Error desconocido. Intenta con otro video."}), 503

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
            logger.info(f"🔄 Trying download {i+1}/5: {strategy_name}")
            
            # Configure yt-dlp options based on format and strategy
            common_options = {
                "outtmpl": os.path.join(request_tmpdir, "%(title)s.%(ext)s"),
                "ffmpeg_location": FFMPEG_PATH,
                "no_warnings": True,
                **strategy.get("options", {})
            }
            
            # Simple delay between attempts
            if i > 0:
                delay = 5 + (i * 2)  # 5, 7, 9, 11, 13 seconds
                logger.info(f"⏳ Waiting {delay}s before download retry...")
                time.sleep(delay)
            
            if video_format == "mp4":
                options = {
                    **common_options,
                    "format": "best[height<=720]/best",
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
                logger.info(f"⬇️ Starting download with {strategy_name}")
                
                # Extract info and download
                info = ydl.extract_info(video_url, download=True)
                
                if not info or not info.get("title"):
                    raise Exception("Download failed - no video info")
                
                title = clean_filename(info["title"])
                ext = "mp4" if video_format == "mp4" else "mp3"
                
                # Find any file with the correct extension
                downloaded_file = None
                files = os.listdir(request_tmpdir)
                logger.info(f"📁 Files in directory: {files}")
                
                for file in files:
                    if file.endswith(f".{ext}"):
                        downloaded_file = os.path.join(request_tmpdir, file)
                        logger.info(f"✅ Found downloaded file: {file}")
                        break
                
                if not downloaded_file or not os.path.exists(downloaded_file):
                    raise Exception(f"No {ext} file found after download")
                    
                # Verify file has content
                file_size = os.path.getsize(downloaded_file)
                if file_size == 0:
                    raise Exception("Downloaded file is empty")
                
                logger.info(f"📊 File size: {file_size} bytes")
                
                # Set correct mime type
                mime_type = "audio/mpeg" if ext == "mp3" else "video/mp4"
                
                # Send the file to the client
                response = send_file(
                    downloaded_file, 
                    as_attachment=True, 
                    download_name=f"{title}.{ext}",
                    mimetype=mime_type
                )
                
                # Setup cleanup callback
                @response.call_on_close
                def cleanup():
                    try:
                        logger.info(f"🧹 Cleaning up: {request_tmpdir}")
                        shutil.rmtree(request_tmpdir, ignore_errors=True)
                    except:
                        pass
                
                logger.info(f"🎉 DOWNLOAD SUCCESS with {strategy_name}: {title}.{ext}")
                return response
                
        except Exception as e:
            last_error = e
            error_msg = str(e)
            logger.error(f"❌ {strategy_name} failed: {error_msg}")
            
            # Clear partial files
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
    
    logger.error("🚫 ALL DOWNLOAD STRATEGIES FAILED")
    
    if last_error:
        error_str = str(last_error)
        logger.error(f"Last download error: {error_str}")
        
        # Update yt-dlp as last resort
        logger.info("🔄 Updating yt-dlp after download failures...")
        update_yt_dlp()
        
        return jsonify({"error": "No se pudo descargar el video. Sistema actualizado automáticamente. Intenta con otro video o espera 15 minutos."}), 503
    
    return jsonify({"error": "Error de descarga desconocido. Intenta con otro video."}), 503

@app.route("/update_ytdlp", methods=["POST"])
def update_ytdlp_route():
    """Route to manually trigger an update of yt-dlp."""
    success = update_yt_dlp()
    if success:
        return jsonify({"message": "yt-dlp updated successfully"}), 200
    else:
        return jsonify({"error": "Failed to update yt-dlp"}), 500



if __name__ == '__main__':
    logger.info("🚀 Starting YouTube Downloader...")
    
    # Check yt-dlp version on startup
    if not check_yt_dlp_version():
        logger.error("❌ Could not verify yt-dlp installation")
    
    logger.info("✅ Application ready at http://localhost:5000")
    app.run(debug=False, host='0.0.0.0', port=5000)
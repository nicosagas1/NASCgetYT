# -*- coding: utf-8 -*-
"""
YouTube Downloader - Version Simplificada RENDER-SAFE

Descarga videos de YouTube como MP3 o MP4 directamente a tu navegador.
Sin necesidad de cookies o configuracion complicada.
"""

from flask import Flask, request, send_file, jsonify, render_template
from werkzeug.exceptions import HTTPException
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

# Configure Flask to not show HTML error pages
app.config['TRAP_HTTP_EXCEPTIONS'] = True
app.config['PROPAGATE_EXCEPTIONS'] = True

# Render-specific configuration
IS_RENDER = os.environ.get('RENDER') or os.environ.get('RENDER_SERVICE_NAME')
if IS_RENDER:
    app.config['JSON_SORT_KEYS'] = False
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    logger = logging.getLogger(__name__)
    logger.info("RENDER deployment detected - applying production configs")
else:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    logger = logging.getLogger(__name__)

def safe_log(message, level='info'):
    """Log messages safely, removing emojis in Render environment."""
    if IS_RENDER:
        clean_msg = ''.join(char for char in message if ord(char) < 128)
        getattr(logger, level)(clean_msg)
    else:
        getattr(logger, level)(message)

# Global error handlers to ensure JSON responses
@app.errorhandler(400)
def bad_request_error(error):
    return jsonify({"error": "Solicitud invalida"}), 400

@app.errorhandler(401)
def unauthorized_error(error):
    return jsonify({"error": "No autorizado"}), 401

@app.errorhandler(403)
def forbidden_error(error):
    return jsonify({"error": "Prohibido"}), 403

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "Endpoint no encontrado"}), 404

@app.errorhandler(405)
def method_not_allowed_error(error):
    return jsonify({"error": "Metodo no permitido"}), 405

@app.errorhandler(429)
def rate_limit_error(error):
    return jsonify({"error": "Demasiadas solicitudes"}), 429

@app.errorhandler(500)
def internal_error(error):
    safe_log(f"Internal server error: {str(error)}", 'error')
    return jsonify({"error": "Error interno del servidor. Intenta de nuevo."}), 500

@app.errorhandler(502)
def bad_gateway_error(error):
    return jsonify({"error": "Error de gateway"}), 502

@app.errorhandler(503)
def service_unavailable_error(error):
    return jsonify({"error": "Servicio no disponible"}), 503

@app.errorhandler(HTTPException)
def handle_http_exception(e):
    """Handle all HTTP exceptions and return JSON."""
    safe_log(f"HTTP exception: {e.code} - {e.description}", 'error')
    return jsonify({
        "error": e.description or f"Error HTTP {e.code}",
        "code": e.code
    }), e.code

@app.errorhandler(Exception)
def handle_exception(e):
    safe_log(f"Unhandled exception: {str(e)}", 'error')
    return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

@app.before_request
def before_request():
    """Ensure request is JSON for API endpoints."""
    if request.endpoint in ['get_video_info', 'convert', 'update_ytdlp_route']:
        if request.method == 'POST' and not request.is_json:
            return jsonify({"error": "Content-Type debe ser application/json"}), 400

@app.after_request
def after_request(response):
    """RENDER-SAFE: Force JSON responses for API endpoints and errors."""
    try:
        endpoint = getattr(request, 'endpoint', None)
        
        if response.status_code >= 400:
            safe_log(f"Response {response.status_code} for {endpoint}: {response.mimetype}", 'warning')
        
        api_endpoints = ['get_video_info', 'convert', 'update_ytdlp_route', 'handle_options', 'health_check', 'api_status']
        if endpoint in api_endpoints:
            if response.mimetype != 'application/json':
                error_msg = "Error de servidor"
                if response.status_code == 404:
                    error_msg = "Endpoint no encontrado"
                elif response.status_code == 405:
                    error_msg = "Metodo no permitido"
                elif response.status_code >= 500:
                    error_msg = "Error interno del servidor"
                
                safe_log(f"FORCING HTML->JSON for {endpoint}: {response.status_code}", 'error')
                response.data = json.dumps({
                    "error": error_msg,
                    "status_code": response.status_code,
                    "endpoint": endpoint,
                    "render_safe": True
                }).encode('utf-8')
                response.mimetype = 'application/json'
        
        elif response.status_code >= 400:
            if response.mimetype != 'application/json':
                safe_log(f"FORCING ERROR->JSON: {response.status_code}", 'error')
                response.data = json.dumps({
                    "error": "Error del servidor",
                    "status_code": response.status_code,
                    "render_safe": True
                }).encode('utf-8')
                response.mimetype = 'application/json'
    
        if response.mimetype == 'application/json':
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            response.headers['X-Content-Type-Options'] = 'nosniff'
        
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS, HEAD'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
        response.headers['Access-Control-Max-Age'] = '86400'
        response.headers['X-Render-Safe'] = 'true'
        
    except Exception as e:
        safe_log(f"CRITICAL: after_request failed: {e}", 'error')
        try:
            response.data = json.dumps({
                "error": "Error critico de procesamiento",
                "render_safe": True,
                "timestamp": datetime.now().isoformat()
            }).encode('utf-8')
            response.mimetype = 'application/json'
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
        except:
            response.data = b'{"error":"Error critico"}'
            response.mimetype = 'application/json'
    
    return response

# Set FFmpeg path
FFMPEG_PATH = r"C:\\ffmpeg\\bin"

# User agents for 2025
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_0_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
]

def get_random_headers():
    """Generate random headers to avoid detection."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.youtube.com/"
    }

def get_extraction_strategies():
    """Return ultra-fast extraction strategies optimized for Render deployment."""
    base_headers = get_random_headers()
    
    return [
        {
            "name": "Android Testsuite",
            "options": {
                "http_headers": base_headers,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android_testsuite"],
                        "skip": ["hls", "dash"]
                    }
                },
                "socket_timeout": 15,
                "retries": 0,  # No retries for speed
                "fragment_retries": 0
            }
        },
        {
            "name": "Web Creator",
            "options": {
                "http_headers": base_headers,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["web_creator"],
                        "skip": ["hls", "dash"]
                    }
                },
                "socket_timeout": 15,
                "retries": 0,
                "fragment_retries": 0
            }
        },
        {
            "name": "iOS Fast",
            "options": {
                "http_headers": {
                    **base_headers,
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
                },
                "extractor_args": {
                    "youtube": {
                        "player_client": ["ios"],
                        "skip": ["hls", "dash"]
                    }
                },
                "socket_timeout": 15,
                "retries": 0
            }
        },
        {
            "name": "Android Simple",
            "options": {
                "http_headers": base_headers,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android"],
                        "skip": ["hls", "dash"]
                    }
                },
                "socket_timeout": 15,
                "retries": 0
            }
        },
        {
            "name": "Web Embedded",
            "options": {
                "http_headers": base_headers,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["web_embedded"],
                        "skip": ["hls", "dash"]
                    }
                },
                "socket_timeout": 20,
                "retries": 0
            }
        }
    ]

def clean_filename(title):
    """Clean video title to create a valid filename."""
    if not title:
        return "video"
    title = re.sub(r'[<>:"/\\|?*]', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title[:100] if len(title) > 100 else title

def update_yt_dlp():
    """Fast yt-dlp update - disabled to prevent timeouts."""
    safe_log("yt-dlp update skipped to prevent timeouts")
    return False

def check_yt_dlp_version():
    """Check if yt-dlp is available and up to date."""
    try:
        import yt_dlp
        return True
    except Exception as e:
        safe_log(f"yt-dlp version check failed: {e}", 'warning')
        return update_yt_dlp()

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health")
def health_check():
    """Health check endpoint for Render deployment monitoring."""
    try:
        checks = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "flask": "running",
            "yt_dlp": "unknown"
        }
        
        try:
            import yt_dlp
            checks["yt_dlp"] = "available"
        except ImportError:
            checks["yt_dlp"] = "missing"
            checks["status"] = "degraded"
        
        try:
            if FFMPEG_PATH and os.path.exists(FFMPEG_PATH):
                checks["ffmpeg"] = "available"
            else:
                checks["ffmpeg"] = "not_configured"
        except:
            checks["ffmpeg"] = "error"
        
        return jsonify(checks), 200
        
    except Exception as e:
        safe_log(f"Health check failed: {e}", 'error')
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route("/api/status")
def api_status():
    """Simple API status check that ALWAYS returns JSON."""
    return jsonify({
        "api": "online",
        "version": "1.0",
        "endpoints": ["get_video_info", "convert", "update_ytdlp"],
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route("/get_video_info", methods=["OPTIONS"])
@app.route("/convert", methods=["OPTIONS"])
@app.route("/update_ytdlp", methods=["OPTIONS"])
def handle_options():
    """Handle preflight OPTIONS requests."""
    return jsonify({"status": "ok"}), 200

@app.route("/get_video_info", methods=["POST"])
def get_video_info():
    """Endpoint to fetch video information without downloading."""
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type debe ser application/json"}), 400
            
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON invalido o vacio"}), 400
            
        video_url = data.get("url")
        if not video_url:
            return jsonify({"error": "No URL provided"}), 400
        
        video_url = video_url.strip()
        if not video_url:
            return jsonify({"error": "URL vacia"}), 400
    
    except Exception as e:
        safe_log(f"Error parsing request: {e}", 'error')
        return jsonify({"error": "Error al procesar la solicitud"}), 400
    
    try:
        strategies = get_extraction_strategies()
        last_error = None
        
        for i, strategy in enumerate(strategies):
            try:
                strategy_name = strategy.get("name", f"Strategy {i+1}")
                safe_log(f"Trying info extraction {i+1}/5: {strategy_name}")
                
                options = {
                    "skip_download": True,
                    "quiet": True,
                    "no_warnings": True,
                    **strategy.get("options", {})
                }
                
                # No delays - immediate retry for faster response
                
                with yt_dlp.YoutubeDL(options) as ydl:
                    safe_log(f"Extracting video info using {strategy_name}")
                    info = ydl.extract_info(video_url, download=False)
                    
                    if info and info.get("title"):
                        safe_log(f"INFO SUCCESS with {strategy_name}: {info.get('title')}")
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
                safe_log(f"{strategy_name} failed: {error_msg[:150]}", 'warning')
                continue
        
        safe_log("ALL INFO EXTRACTION FAILED", 'error')
        
        # Fast fail - no update attempts to avoid timeouts
        return jsonify({"error": "Video no disponible temporalmente. Intenta con otro video."}), 503
        
    except Exception as e:
        safe_log(f"Critical error in get_video_info: {str(e)}", 'error')
        return jsonify({"error": "Error critico del servidor. Intenta de nuevo."}), 500

@app.route("/convert", methods=["POST"])
def convert():
    """Download and convert YouTube videos to MP3 or MP4."""
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type debe ser application/json"}), 400
            
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON invalido o vacio"}), 400
            
        video_url = data.get("url")
        video_format = data.get("format")
        
        if not video_url:
            return jsonify({"error": "No URL provided"}), 400
            
        if not video_format or video_format not in ["mp3", "mp4"]:
            return jsonify({"error": "Formato debe ser 'mp3' o 'mp4'"}), 400
            
        video_url = video_url.strip()
        if not video_url:
            return jsonify({"error": "URL vacia"}), 400
            
    except Exception as e:
        safe_log(f"Error parsing convert request: {e}", 'error')
        return jsonify({"error": "Error al procesar la solicitud"}), 400

    request_tmpdir = None
    try:
        request_tmpdir = tempfile.mkdtemp()
        strategies = get_extraction_strategies()
        last_error = None
        
        for i, strategy in enumerate(strategies):
            try:
                strategy_name = strategy.get("name", f"Strategy {i+1}")
                safe_log(f"Trying download {i+1}/5: {strategy_name}")
                
                # No delays - immediate retry for faster downloads
                
                common_options = {
                    "outtmpl": os.path.join(request_tmpdir, "%(title)s.%(ext)s"),
                    "ffmpeg_location": FFMPEG_PATH,
                    "no_warnings": True,
                    **strategy.get("options", {})
                }
                
                if video_format == "mp4":
                    options = {
                        **common_options,
                        "format": "best[height<=720]/best",
                    }
                else:  # mp3
                    options = {
                        **common_options,
                        "format": "bestaudio/best",
                        "postprocessors": [{
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }]
                    }
                
                safe_log(f"Starting download with {strategy_name}")
                
                with yt_dlp.YoutubeDL(options) as ydl:
                    ydl.download([video_url])
                
                # Find downloaded file
                ext = "mp3" if video_format == "mp3" else "mp4"
                downloaded_file = None
                
                for root, dirs, filenames in os.walk(request_tmpdir):
                    for file in filenames:
                        if file.endswith(f".{ext}"):
                            downloaded_file = os.path.join(root, file)
                            break
                    if downloaded_file:
                        break
                
                if not downloaded_file or not os.path.exists(downloaded_file):
                    raise Exception(f"No {ext} file found after download")
                
                file_size = os.path.getsize(downloaded_file)
                if file_size == 0:
                    raise Exception("Downloaded file is empty")
                
                safe_log(f"DOWNLOAD SUCCESS with {strategy_name}: {file_size} bytes")
                
                title = clean_filename(os.path.basename(downloaded_file))
                if not title.endswith(f".{ext}"):
                    title = f"{title}.{ext}"
                
                return send_file(
                    downloaded_file,
                    as_attachment=True,
                    download_name=title,
                    mimetype="audio/mpeg" if ext == "mp3" else "video/mp4"
                )
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                safe_log(f"{strategy_name} failed: {error_msg[:100]}", 'warning')
                continue
        
        # Fast fail - no complex error analysis to avoid timeouts
        safe_log("ALL DOWNLOAD STRATEGIES FAILED", 'error')
        return jsonify({"error": "Descarga no disponible temporalmente. Intenta con otro video."}), 503
        
    except Exception as e:
        safe_log(f"Critical error in convert: {str(e)}", 'error')
        return jsonify({"error": "Error critico del servidor. Intenta de nuevo."}), 500
    
    finally:
        if request_tmpdir:
            try:
                shutil.rmtree(request_tmpdir, ignore_errors=True)
            except:
                pass

@app.route("/update_ytdlp", methods=["POST"])
def update_ytdlp_route():
    """Route to manually trigger an update of yt-dlp."""
    success = update_yt_dlp()
    if success:
        return jsonify({"message": "yt-dlp updated successfully"}), 200
    else:
        return jsonify({"error": "Failed to update yt-dlp"}), 500

if __name__ == '__main__':
    safe_log("Starting YouTube Downloader...")
    
    safe_log(f"Python version: {sys.version}")
    safe_log(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    safe_log(f"Debug mode: {app.debug}")
    
    if not check_yt_dlp_version():
        safe_log("Could not verify yt-dlp installation", 'error')
    else:
        safe_log("yt-dlp verified successfully")
    
    with app.test_client() as client:
        try:
            response = client.get('/health')
            if response.status_code == 200:
                safe_log("Health check endpoint working")
            else:
                safe_log(f"Health check returned {response.status_code}", 'warning')
        except Exception as e:
            safe_log(f"Health check failed: {e}", 'error')
    
    port = int(os.environ.get('PORT', 5000))
    safe_log(f"Application ready at http://0.0.0.0:{port}")
    app.run(debug=False, host='0.0.0.0', port=port)
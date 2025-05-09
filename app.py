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

app = Flask(__name__)
app.secret_key = '7772428b-01cf-4d05-9c3e-cea510398586'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set FFmpeg path - adjust this to your specific location if needed
FFMPEG_PATH = r"C:\\ffmpeg\\bin"

# List of potential user agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
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
    
    try:
        options = {
            "skip_download": True,
            "quiet": True,
            "headers": get_random_headers(),
            "nocheckcertificate": True,
            "geo_bypass": True,
            "geo_bypass_country": "US"
        }
        
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            return jsonify({
                "title": info.get("title"),
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
                "channel": info.get("uploader"),
                "views": info.get("view_count")
            })
    
    except Exception as e:
        logger.error(f"Error fetching video info: {str(e)}")
        if "HTTP Error 403: Forbidden" in str(e):
            # Try to update yt-dlp on 403 errors
            if update_yt_dlp():
                return jsonify({"error": "YouTube blocked the request. We've updated our tools, please try again."}), 503
        return jsonify({"error": str(e)}), 500

@app.route("/convert", methods=["POST"])
def convert():
    data = request.get_json()
    video_url = data.get("url")
    video_format = data.get("format")  # "mp3" or "mp4"

    if not video_url:
        return jsonify({"error": "No URL provided"}), 400

    # Create the main temporary directory for this request
    request_tmpdir = tempfile.mkdtemp()
    
    try:
        # Configure yt-dlp options based on format
        common_options = {
            "outtmpl": os.path.join(request_tmpdir, "%(id)s.%(ext)s"),
            "ffmpeg_location": FFMPEG_PATH,
            "headers": get_random_headers(),
            "nocheckcertificate": True,
            "geo_bypass": True,
            "geo_bypass_country": "US", 
            "cookiefile": os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt"),
            "socket_timeout": 30,
            "retries": 10,
            "fragment_retries": 10
        }
        
        if video_format == "mp4":
            options = {
                **common_options,
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"
            }
        else:  # mp3
            options = {
                **common_options,
                "format": "bestaudio/best",
                "outtmpl": os.path.join(request_tmpdir, "%(id)s.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ]
            }

        logger.info(f"Created temporary directory: {request_tmpdir}")
        
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                logger.info(f"Downloading {video_url} as {video_format}")
                
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
                
                return response
        except yt_dlp.utils.DownloadError as e:
            if "HTTP Error 403: Forbidden" in str(e):
                # Try updating yt-dlp
                update_yt_dlp()
                raise Exception("YouTube blocked the request. Our system has been updated - please try again.")
            raise

    except Exception as e:
        # Clean up the temp directory in case of error
        try:
            shutil.rmtree(request_tmpdir, ignore_errors=True)
        except:
            pass
        
        logger.error(f"Error during conversion: {str(e)}")
        return jsonify({"error": str(e)}), 500

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
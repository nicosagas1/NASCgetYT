from flask import Flask, request, send_file, jsonify, render_template
import yt_dlp
import os
import re
import tempfile
import logging
import time
import shutil
import uuid

app = Flask(__name__)
app.secret_key = '7772428b-01cf-4d05-9c3e-cea510398586'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set FFmpeg path - adjust this to your specific location if needed
FFMPEG_PATH = r"C:\\ffmpeg\\bin"

def clean_filename(title):
    """Removes special characters and shortens the filename."""
    title = re.sub(r'[\\/*?:"<>|]', '', title)
    return title[:50]

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
        if video_format == "mp4":
            options = {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
                "outtmpl": os.path.join(request_tmpdir, "%(id)s.%(ext)s"),
                "ffmpeg_location": FFMPEG_PATH,
            }
        else:  # mp3
            options = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(request_tmpdir, "%(id)s.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "ffmpeg_location": FFMPEG_PATH,
            }

        logger.info(f"Created temporary directory: {request_tmpdir}")
        
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
                    if file.startswith(video_id):
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

    except Exception as e:
        # Clean up the temp directory in case of error app.run()
        try:
            shutil.rmtree(request_tmpdir, ignore_errors=True)
        except:
            pass
        
        logger.error(f"Error during conversion: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run()
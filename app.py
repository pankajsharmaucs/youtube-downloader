import os
import yt_dlp
import requests
from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import time

# Initialize Flask app and SocketIO
app = Flask(__name__)
socketio = SocketIO(app)

# Make sure the "downloads" folder exists
DOWNLOAD_FOLDER = "./downloads"
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Set up allowed file types and max content length
ALLOWED_EXTENSIONS = {"mp4", "webm", "mp3", "flv", "mkv", "avi", "mov"}
app.config["UPLOAD_FOLDER"] = DOWNLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max file size


# Function to check allowed extensions
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Home route
@app.route("/")
def index():
    return render_template("index.html")


# Download route
@app.route("/download", methods=["POST"])
def download():
    video_url = request.form.get("url")
    quality = request.form.get("quality")
    download_type = request.form.get("download_type")  # 'video' or 'mp3'

    # Check if the URL is a Pexels URL (you can further validate this based on Pexels API)
    if "pexels.com" in video_url:
        try:
            # Fetch video from Pexels (direct download for now)
            video_id = video_url.split("/")[-1]  # Assuming video URL ends with video ID
            video_download_url = f"https://www.pexels.com/video/{video_id}/download/"  # Pexels direct download URL
            response = requests.get(video_download_url, stream=True)
            filename = f"pexels_video_{video_id}.mp4"
            filepath = os.path.join(DOWNLOAD_FOLDER, filename)

            # Save the video to the downloads folder
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
                
            return render_template(
                "download.html",
                title=filename,
                filename=filename,
                download_folder=DOWNLOAD_FOLDER,
            )

        except Exception as e:
            return f"Error: {str(e)}"

    else:
        # YouTube download using yt-dlp
        cookies_file = "cookies.txt"

        ydl_opts = {
            "format": quality,
            "outtmpl": os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s"),
            "cookies": cookies_file,  # Load cookies from file
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            },
            "quiet": False,  # Show download progress
            "progress_hooks": [
                progress_hook
            ],  # Use progress_hook for real-time updates
            "geo-bypass": True,  # Bypass geo-blocking if required
            "nocheckcertificate": True,  # Bypass SSL certificate check
        }

        if download_type == "mp3":
            ydl_opts.update(
                {
                    "postprocessors": [
                        {
                            "key": "FFmpegAudioConvertor",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                }
            )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(video_url, download=True)
                title = info_dict.get("title", None)
                filename = ydl.prepare_filename(info_dict)
                return render_template(
                    "download.html",
                    title=title,
                    filename=title+".mp4",
                    download_folder=DOWNLOAD_FOLDER,
                )

        except Exception as e:
            return f"Error: {str(e)}"


# Serve the downloaded files
@app.route("/downloads/<filename>")
def download_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)


# Progress hook for yt-dlp
def progress_hook(d):
    if d["status"] == "downloading":
        # Check if total_bytes is available
        if "total_bytes" in d and d["total_bytes"] > 0:
            percentage = (d["downloaded_bytes"] / d["total_bytes"]) * 100
            socketio.emit("progress", {"percentage": percentage})
        else:
            socketio.emit("progress", {"percentage": 0})


# Run the app
if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)

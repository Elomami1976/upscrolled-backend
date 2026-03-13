# UpScrolled Video Downloader

A free, open-source web application to download videos from UpScrolled. Simply paste a share link and download the video in MP4 format.

## Features

- **Free to use** - No subscriptions, no hidden fees
- **No watermarks** - Download original quality videos
- **No login required** - No accounts, no registration
- **Privacy focused** - No data stored, no tracking
- **Mobile friendly** - Works on all devices
- **Fast processing** - Videos ready in seconds

## Tech Stack

### Frontend
- Pure HTML5, CSS3, JavaScript (no frameworks)
- Responsive design (mobile-first)
- PWA support with offline caching
- SEO optimized with Schema.org markup

### Backend
- Python 3.9+
- FastAPI
- httpx for async HTTP requests
- ffmpeg for video processing

## Project Structure

```
upscrolled-downloader/
├── frontend/
│   ├── index.html          # Home page with download form
│   ├── how-it-works.html   # Step-by-step guide
│   ├── about.html          # About page
│   ├── contact.html        # Contact form
│   ├── terms.html          # Terms of Service
│   ├── privacy.html        # Privacy Policy
│   ├── dmca.html           # DMCA Policy
│   ├── style.css           # Global styles
│   ├── app.js              # Download logic
│   ├── nav.js              # Navigation component
│   ├── manifest.json       # PWA manifest
│   ├── sw.js               # Service worker
│   ├── sitemap.xml         # XML sitemap
│   └── robots.txt          # Robots file
├── backend/
│   ├── main.py             # FastAPI application
│   ├── requirements.txt    # Python dependencies
│   └── .env.example        # Environment variables template
└── README.md
```

## Prerequisites

- Python 3.9 or higher
- ffmpeg installed and available in PATH
- pip (Python package manager)

### Installing ffmpeg

**Windows:**
```powershell
# Using Chocolatey
choco install ffmpeg

# Or using Scoop
scoop install ffmpeg

# Or download from https://ffmpeg.org/download.html
```

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

## Local Development

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/upscrolled-downloader.git
cd upscrolled-downloader
```

### 2. Set up the backend

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
```

### 3. Run the development server

```bash
# From the backend directory
python main.py

# Or using uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Access the application

Open your browser and navigate to:
- Frontend: http://localhost:8000
- API Docs: http://localhost:8000/api/docs

## API Endpoints

### POST /api/download

Download a video from an UpScrolled share link.

**Request:**
```json
{
  "url": "https://share.upscrolled.com/en/post/VIDEO_ID/"
}
```

**Response:**
- Success: MP4 file stream (video/mp4)
- Error: JSON with error details

**Error Codes:**
| Code | Description |
|------|-------------|
| 400 | Invalid UpScrolled link format |
| 404 | Video not found or is private |
| 500 | Video processing failed |
| 502 | Cannot reach UpScrolled |
| 504 | Request timed out |

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

## Deployment

### Option 1: VPS/Dedicated Server

1. **Install dependencies:**
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv ffmpeg nginx
   ```

2. **Clone and set up:**
   ```bash
   git clone https://github.com/yourusername/upscrolled-downloader.git
   cd upscrolled-downloader/backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Create systemd service:**
   ```ini
   # /etc/systemd/system/upscrolled.service
   [Unit]
   Description=UpScrolled Video Downloader
   After=network.target

   [Service]
   User=www-data
   WorkingDirectory=/path/to/upscrolled-downloader/backend
   ExecStart=/path/to/upscrolled-downloader/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

4. **Configure nginx:**
   ```nginx
   server {
       listen 80;
       server_name upscrolleddownloader.com;

       location / {
           root /path/to/upscrolled-downloader/frontend;
           index index.html;
           try_files $uri $uri/ =404;
       }

       location /api {
           proxy_pass http://127.0.0.1:8000;
           proxy_http_version 1.1;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_read_timeout 120s;
       }

       location /health {
           proxy_pass http://127.0.0.1:8000;
       }
   }
   ```

5. **Start services:**
   ```bash
   sudo systemctl enable upscrolled
   sudo systemctl start upscrolled
   sudo systemctl restart nginx
   ```

### Option 2: Docker

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Install ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY frontend/ ./frontend/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t upscrolled-downloader .
docker run -p 8000:8000 upscrolled-downloader
```

### Option 3: Platform as a Service

**Railway, Render, Fly.io:**

1. Connect your GitHub repository
2. Set the build command: `pip install -r backend/requirements.txt`
3. Set the start command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Ensure ffmpeg is available (may need buildpacks or custom Dockerfile)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| HOST | 0.0.0.0 | Server host |
| PORT | 8000 | Server port |
| ALLOWED_ORIGINS | localhost | CORS allowed origins |
| HTTP_TIMEOUT | 30 | HTTP request timeout (seconds) |
| FFMPEG_TIMEOUT | 120 | ffmpeg processing timeout (seconds) |
| DEBUG | true | Debug mode |

## How It Works

1. User pastes an UpScrolled share link
2. Backend fetches the HTML page using httpx
3. Extracts the Mux playback ID from thumbnail URL pattern
4. Builds the HLS stream URL: `https://stream.mux.com/{PLAYBACK_ID}.m3u8`
5. Uses ffmpeg to convert the HLS stream to MP4
6. Streams the MP4 file to the user's browser
7. Temporary files are deleted immediately after download

## Legal Notice

- This project is **not affiliated with UpScrolled**
- Use only for downloading content you have rights to
- Respect copyright laws and content creators
- See [Terms of Service](frontend/terms.html) for full details

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is open source and available under the MIT License.

## Support

- Create an issue for bug reports
- Email: support@upscrolleddownloader.com

---

Made with ♥ for the community

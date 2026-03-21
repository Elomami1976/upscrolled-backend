"""
UpScrolled Video Downloader - Backend API
FastAPI application for downloading UpScrolled videos

Endpoints:
- POST /api/download - Download a video from UpScrolled share link
- GET /health - Health check endpoint
"""

import os
import re
import tempfile
import asyncio
import uuid
from typing import Optional
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl, field_validator


# ============================================================================
# Configuration
# ============================================================================

UPSCROLLED_URL_PATTERN = re.compile(
    r'^https://share\.upscrolled\.com/[a-z]{2}/post/([\w-]+)/?$',
    re.IGNORECASE
)

# OLD: Mux video hosting pattern (deprecated)
MUX_PLAYBACK_ID_PATTERN = re.compile(
    r'https://image\.mux\.com/([a-zA-Z0-9]+)/thumbnail\.jpg'
)

# NEW: UpScrolled's own video hosting patterns
# Note: URLs can be URL-encoded (%2F instead of /) in the HTML
UPSCROLLED_VIDEO_THUMBNAIL_PATTERN = re.compile(
    r'(?:image\.)?prod-ext\.video\.upscrolled\.com(?:/|%2F)([a-zA-Z0-9]+)(?:/|%2F)thumbnail\.jpg',
    re.IGNORECASE
)

UPSCROLLED_VIDEO_STREAM_PATTERN = re.compile(
    r'video\.upscrolled\.com(?:/|%2F)([a-zA-Z0-9]+)\.m3u8',
    re.IGNORECASE
)

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:5000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:5000",
    "https://upscrolleddownload.com",
    "https://www.upscrolleddownload.com",
]

# Regex pattern for wildcard origins (e.g., Vercel preview deployments)
ALLOWED_ORIGIN_REGEX = r"https://.*\.vercel\.app"

# Timeout settings
HTTP_TIMEOUT = 30.0
FFMPEG_TIMEOUT = 120  # 2 minutes max for video processing

# Global ffmpeg path - will be set at startup
FFMPEG_PATH = None


def find_ffmpeg():
    """
    Find ffmpeg executable in various locations.
    Returns the path to ffmpeg or None if not found.
    """
    import subprocess
    import shutil
    
    # Check if ffmpeg is in PATH
    ffmpeg_in_path = shutil.which('ffmpeg')
    if ffmpeg_in_path:
        return ffmpeg_in_path
    
    # Check common installation locations
    possible_paths = [
        # Project local ffmpeg folder
        os.path.join(os.path.dirname(__file__), '..', 'ffmpeg', 'ffmpeg-master-latest-win64-gpl', 'bin', 'ffmpeg.exe'),
        os.path.join(os.path.dirname(__file__), '..', 'ffmpeg', 'bin', 'ffmpeg.exe'),
        os.path.join(os.path.dirname(__file__), '..', 'ffmpeg', 'ffmpeg.exe'),
        # Common Windows installation paths
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\ffmpeg\ffmpeg.exe'),
        os.path.expandvars(r'%LOCALAPPDATA%\Programs\ffmpeg\bin\ffmpeg.exe'),
        # Chocolatey
        r'C:\ProgramData\chocolatey\bin\ffmpeg.exe',
        # Scoop
        os.path.expandvars(r'%USERPROFILE%\scoop\apps\ffmpeg\current\bin\ffmpeg.exe'),
    ]
    
    # Also check for extracted ffmpeg folders in project
    ffmpeg_dir = os.path.join(os.path.dirname(__file__), '..', 'ffmpeg')
    if os.path.exists(ffmpeg_dir):
        for item in os.listdir(ffmpeg_dir):
            item_path = os.path.join(ffmpeg_dir, item)
            if os.path.isdir(item_path):
                bin_path = os.path.join(item_path, 'bin', 'ffmpeg.exe')
                if os.path.exists(bin_path):
                    possible_paths.insert(0, bin_path)
    
    for path in possible_paths:
        expanded_path = os.path.expandvars(path)
        if os.path.isfile(expanded_path):
            # Verify it works
            try:
                result = subprocess.run(
                    [expanded_path, '-version'],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return expanded_path
            except:
                continue
    
    return None


# ============================================================================
# Pydantic Models
# ============================================================================

class DownloadRequest(BaseModel):
    """Request model for video download endpoint"""
    url: str
    
    @field_validator('url')
    @classmethod
    def validate_upscrolled_url(cls, v: str) -> str:
        """Validate that the URL is a valid UpScrolled share link"""
        if not UPSCROLLED_URL_PATTERN.match(v):
            raise ValueError('Invalid UpScrolled share link format')
        return v


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str


class ErrorResponse(BaseModel):
    """Response model for errors"""
    detail: str


# ============================================================================
# Application Setup
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    global FFMPEG_PATH
    
    # Startup
    print("UpScrolled Video Downloader API starting...")
    
    # Find ffmpeg
    FFMPEG_PATH = find_ffmpeg()
    if FFMPEG_PATH:
        print(f"ffmpeg found at: {FFMPEG_PATH}")
    else:
        print("WARNING: ffmpeg not found. Video processing will fail.")
        print("Please install ffmpeg: https://ffmpeg.org/download.html")
    
    yield
    
    # Shutdown
    print("UpScrolled Video Downloader API shutting down...")


app = FastAPI(
    title="UpScrolled Video Downloader API",
    description="API for downloading videos from UpScrolled share links",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ============================================================================
# Helper Functions
# ============================================================================

async def fetch_page_html(url: str) -> str:
    """
    Fetch the HTML content of an UpScrolled page
    
    Args:
        url: The UpScrolled share link URL
        
    Returns:
        The HTML content of the page
        
    Raises:
        HTTPException: If the page cannot be fetched
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request to UpScrolled timed out. Please try again."
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found. The video may have been deleted or is private."
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach UpScrolled. Please try again later."
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect to UpScrolled. Please check your connection."
        )


def extract_playback_id(html: str) -> tuple[str, str]:
    """
    Extract the video playback ID from the page HTML
    
    Args:
        html: The HTML content of the UpScrolled page
        
    Returns:
        Tuple of (playback_id, source) where source is 'upscrolled' or 'mux'
        
    Raises:
        HTTPException: If the playback ID cannot be extracted
    """
    # Check for common error pages first
    if "Profile Not Found" in html or "does not exist or deactivated" in html:
        print("Page indicates profile/video not found or deactivated")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found. The video may have been deleted or the profile is deactivated."
        )
    
    if "This post is private" in html or "private post" in html.lower():
        print("Page indicates video is private")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This video is private and cannot be downloaded."
        )
    
    # Try NEW UpScrolled video patterns first (as of March 2026)
    # Check for direct m3u8 stream URL
    upscrolled_stream_match = UPSCROLLED_VIDEO_STREAM_PATTERN.search(html)
    if upscrolled_stream_match:
        playback_id = upscrolled_stream_match.group(1)
        print(f"Found UpScrolled video ID from stream URL: {playback_id}")
        return (playback_id, 'upscrolled')
    
    # Check for thumbnail URL pattern
    upscrolled_thumb_match = UPSCROLLED_VIDEO_THUMBNAIL_PATTERN.search(html)
    if upscrolled_thumb_match:
        playback_id = upscrolled_thumb_match.group(1)
        print(f"Found UpScrolled video ID from thumbnail URL: {playback_id}")
        return (playback_id, 'upscrolled')
    
    # Try OLD Mux patterns (legacy)
    mux_match = MUX_PLAYBACK_ID_PATTERN.search(html)
    if mux_match:
        playback_id = mux_match.group(1)
        print(f"Found Mux playback ID: {playback_id}")
        return (playback_id, 'mux')
    
    # Log the HTML for debugging (first 3000 chars)
    print(f"Failed to find video ID in HTML. First 3000 chars of HTML:")
    print(html[:3000])
    
    # Try alternative patterns (including URL-encoded versions)
    alt_patterns = [
        # UpScrolled patterns (URL-encoded and non-encoded)
        (r'video\.upscrolled\.com(?:/|%2F)([a-zA-Z0-9]+)', 'upscrolled'),
        (r'(?:image\.)?prod-ext\.video\.upscrolled\.com(?:/|%2F)([a-zA-Z0-9]+)', 'upscrolled'),
        # Mux patterns (legacy)
        (r'https://stream\.mux\.com/([a-zA-Z0-9]+)', 'mux'),
        (r'"playbackId"[:\s]*"([a-zA-Z0-9]+)"', 'mux'),
        (r'mux-player[^>]*playback-id="([a-zA-Z0-9]+)"', 'mux'),
        (r'data-playback-id="([a-zA-Z0-9]+)"', 'mux'),
    ]
    
    for pattern, source in alt_patterns:
        alt_match = re.search(pattern, html)
        if alt_match:
            playback_id = alt_match.group(1)
            print(f"Found video ID using alternative pattern '{pattern}': {playback_id} (source: {source})")
            return (playback_id, source)
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Video not found or is private. Could not extract video stream."
    )


def build_stream_url(playback_id: str, source: str = 'upscrolled') -> str:
    """
    Build the HLS stream URL from the playback ID
    
    Args:
        playback_id: The video playback ID
        source: Video source ('upscrolled' or 'mux')
        
    Returns:
        The HLS stream URL
    """
    if source == 'upscrolled':
        # New UpScrolled video hosting (as of March 2026)
        return f"https://stream.prod-ext.video.upscrolled.com/{playback_id}.m3u8"
    else:
        # Legacy Mux hosting
        return f"https://stream.mux.com/{playback_id}.m3u8"


async def convert_stream_to_mp4(stream_url: str, output_path: str) -> None:
    """
    Convert an HLS stream to MP4 using ffmpeg
    
    Args:
        stream_url: The HLS stream URL
        output_path: The output file path
        
    Raises:
        HTTPException: If ffmpeg fails
    """
    import subprocess
    
    # Check if ffmpeg is available
    if not FFMPEG_PATH:
        print("ERROR: ffmpeg not found at startup")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Video processor (ffmpeg) not installed. Please install ffmpeg from https://ffmpeg.org/download.html"
        )
    
    print(f"Processing stream: {stream_url}")
    print(f"Output path: {output_path}")
    print(f"Using ffmpeg: {FFMPEG_PATH}")
    
    cmd = [
        FFMPEG_PATH,
        '-y',  # Overwrite output file
        '-i', stream_url,  # Input HLS stream
        '-c', 'copy',  # Copy streams without re-encoding
        '-bsf:a', 'aac_adtstoasc',  # Fix AAC audio for MP4 container
        '-movflags', '+faststart',  # Enable fast start for web playback
        output_path
    ]
    
    print(f"Running ffmpeg command: {' '.join(cmd)}")
    
    try:
        # Use synchronous subprocess for Windows compatibility
        # Run in executor to not block the event loop
        loop = asyncio.get_event_loop()
        
        def run_ffmpeg():
            return subprocess.run(
                cmd,
                capture_output=True,
                timeout=FFMPEG_TIMEOUT
            )
        
        result = await loop.run_in_executor(None, run_ffmpeg)
        
        if result.returncode != 0:
            error_msg = result.stderr.decode() if result.stderr else "Unknown error"
            stdout_msg = result.stdout.decode() if result.stdout else ""
            print(f"ffmpeg failed with return code: {result.returncode}")
            print(f"ffmpeg stderr: {error_msg}")
            print(f"ffmpeg stdout: {stdout_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Video processing failed: {error_msg[:200] if len(error_msg) > 200 else error_msg}"
            )
        
        print(f"ffmpeg completed successfully, output file exists: {os.path.exists(output_path)}")
        if os.path.exists(output_path):
            print(f"Output file size: {os.path.getsize(output_path)} bytes")
            
    except subprocess.TimeoutExpired:
        print(f"ffmpeg timed out after {FFMPEG_TIMEOUT} seconds")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Video processing timed out. The video may be too long."
        )
    except FileNotFoundError:
        print(f"ffmpeg not found at path: {FFMPEG_PATH}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Video processor not available. Please install ffmpeg."
        )


async def stream_file(file_path: str, chunk_size: int = 1024 * 1024):
    """
    Stream a file in chunks
    
    Args:
        file_path: Path to the file to stream
        chunk_size: Size of each chunk in bytes (default 1MB)
        
    Yields:
        File chunks
    """
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                yield chunk
    finally:
        # Clean up the temporary file after streaming
        try:
            os.remove(file_path)
        except OSError:
            pass


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint
    
    Returns the current health status of the API
    """
    return HealthResponse(status="ok")


@app.post(
    "/api/download",
    tags=["Download"],
    responses={
        200: {
            "description": "Video file download",
            "content": {"video/mp4": {}}
        },
        400: {"model": ErrorResponse, "description": "Invalid URL format"},
        404: {"model": ErrorResponse, "description": "Video not found"},
        500: {"model": ErrorResponse, "description": "Processing error"},
        502: {"model": ErrorResponse, "description": "Cannot reach UpScrolled"},
    }
)
async def download_video(request: DownloadRequest):
    """
    Download a video from an UpScrolled share link
    
    This endpoint:
    1. Validates the UpScrolled share link
    2. Fetches the page HTML
    3. Extracts the video playback ID
    4. Converts the HLS stream to MP4 using ffmpeg
    5. Streams the MP4 file to the client
    
    All temporary files are deleted after the download completes.
    """
    print(f"=== New download request ===")
    print(f"URL: {request.url}")
    
    # Step 1: Fetch the page HTML
    print("Step 1: Fetching page HTML...")
    html = await fetch_page_html(request.url)
    print(f"Fetched HTML successfully, length: {len(html)} chars")
    
    # Step 2: Extract the playback ID
    print("Step 2: Extracting playback ID...")
    playback_id, video_source = extract_playback_id(html)
    print(f"Extracted playback ID: {playback_id}, source: {video_source}")
    
    # Step 3: Build the stream URL
    stream_url = build_stream_url(playback_id, video_source)
    print(f"Step 3: Built stream URL: {stream_url}")
    
    # Step 4: Create temporary file for the MP4
    temp_dir = tempfile.gettempdir()
    output_filename = f"upscrolled_{uuid.uuid4().hex}.mp4"
    output_path = os.path.join(temp_dir, output_filename)
    print(f"Step 4: Output path: {output_path}")
    
    try:
        # Step 5: Convert stream to MP4
        print("Step 5: Converting stream to MP4...")
        await convert_stream_to_mp4(stream_url, output_path)
        
        # Step 6: Get file size for Content-Length header
        file_size = os.path.getsize(output_path)
        print(f"Step 6: File ready, size: {file_size} bytes")
        
        # Step 7: Stream the file to the client
        print("Step 7: Streaming file to client...")
        return StreamingResponse(
            stream_file(output_path),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="upscrolled-video.mp4"',
                "Content-Length": str(file_size),
            }
        )
        
    except HTTPException:
        # Clean up on error
        print("HTTPException occurred, cleaning up...")
        try:
            os.remove(output_path)
        except OSError:
            pass
        raise
    except Exception as e:
        # Clean up on unexpected error
        print(f"Unexpected error during download: {type(e).__name__}: {e}")
        try:
            os.remove(output_path)
        except OSError:
            pass
        print(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)[:100]}"
        )


@app.post("/api/debug", tags=["Debug"])
async def debug_video(request: DownloadRequest):
    """
    Debug endpoint to test video extraction without downloading.
    Returns the extracted playback ID and stream URL.
    """
    try:
        print(f"=== Debug request ===")
        print(f"URL: {request.url}")
        
        html = await fetch_page_html(request.url)
        print(f"HTML length: {len(html)}")
        
        playback_id, video_source = extract_playback_id(html)
        stream_url = build_stream_url(playback_id, video_source)
        
        # Test if stream URL is accessible
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.head(stream_url)
            stream_accessible = response.status_code == 200
        
        return JSONResponse({
            "success": True,
            "playback_id": playback_id,
            "video_source": video_source,
            "stream_url": stream_url,
            "stream_accessible": stream_accessible,
            "ffmpeg_available": FFMPEG_PATH is not None,
            "ffmpeg_path": FFMPEG_PATH,
            "html_length": len(html)
        })
    except HTTPException as e:
        return JSONResponse({
            "success": False,
            "error": e.detail,
            "status_code": e.status_code
        }, status_code=e.status_code)
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# ============================================================================
# Static Files (for development)
# ============================================================================

# Mount static files for development
# In production, use a proper web server like nginx
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.environ.get("RAILWAY_ENVIRONMENT") is None,  # Only reload in dev
        log_level="info"
    )

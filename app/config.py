import os
import secrets

# ---------------trace.moe------------------
TRACE_MOE_BASE_URL = "https://api.trace.moe"  # API path
TRACE_MOE_CUT_BORDERS = True  # cut borders of img
TRACE_MOE_TIMER = 8.0  # max seconds of waiting for response

# Confidence gate
CONFIDENT_THRESHOLD = 95  # if trace.moe have x>95% simillarty - dont ask other API

# Quota
QUOTA_LOW_THRESHOLD = 10  # warn user when remaining searches drop to this number 
QUOTA_WARN_EVERY = 10  # tell user every QUOTA_WARN_EVERY searches how many he made so far

# Frame 
MAX_FRAMES_LIMIT = 16 # cap on user selected frame count (1-16)

# ---------------local API security------------------
# Shared secret between the UI and the local API. Requests without this header
# are rejected - this blocks drive-by browser requests (a custom header forces
# a CORS preflight that will fail) and other processes/machines.
# When the UI and API run in the same process (python main.py) they share this value automatically.

# For a standalone server (uvicorn main:app), set ANIMERS_TOKEN in the environment for BOTH processes.
API_TOKEN = os.environ.get("ANIMERS_TOKEN") or secrets.token_hex(16)

# Upload limits
MAX_UPLOAD_MB = 250  # reject uploads bigger than this

# Server-side acceptlist - mirrors the UI's file dialog filter. Anything else
# is rejected before it ever reaches ffmpeg/imageio.
ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif",
    ".gif", ".mp4", ".mkv", ".webm", ".mov", ".avi",
}

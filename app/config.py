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
# ---------------trace.moe------------------
TRACE_MOE_API_KEY = None  # API key, optinal 
TRACE_MOE_BASE_URL = "https://api.trace.moe"  # API path
TRACE_MOE_CUT_BORDERS = True  # cut borders of img
TRACE_MOE_TIMER = 8.0  # max seconds of waiting for responde

# Confidence gate
CONFIDENT_THRESHOLD = 95  # if trace.moe have x>95% simillarty - dont ask other API

# Quota
QUOTA_LOW_THRESHOLD = 10  # warn user when remaining searches drop to this level
import os
import sys

# The macOS torch and faiss-cpu wheels each bundle libomp; a second copy aborts the process.
if sys.platform == "darwin":
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

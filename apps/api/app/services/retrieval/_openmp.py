import os
import sys

# The macOS torch and faiss-cpu wheels each bundle libomp: a second copy aborts the process,
# and two thread pools running at once can segfault. One thread each is stable and fast enough.
if sys.platform == "darwin":
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    os.environ.setdefault("OMP_NUM_THREADS", "1")

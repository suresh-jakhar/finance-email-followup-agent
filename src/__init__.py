import os
import warnings
import logging

# ── GLOBAL SILENCE: Mute all library warnings at the earliest possible stage ──
os.environ["PYTHONWARNINGS"] = "ignore"
warnings.filterwarnings("ignore")
logging.captureWarnings(True)
logging.getLogger("py.warnings").setLevel(logging.CRITICAL)

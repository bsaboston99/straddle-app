Place the output of `_claude_ml_v2_persist.py` here:
  - straddle_model_v2.joblib
  - straddle_model_v2_metadata.json

paper_trading.py loads straddle_model_v2.joblib from this directory (or from
the path in the MODEL_PATH env var) at first use.

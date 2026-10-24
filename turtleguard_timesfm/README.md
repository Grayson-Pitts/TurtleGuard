# TurtleGuard TimesFM 3 starter kit

This kit includes a verified transcription of the **loggerhead** and **green** annual Boca Raton counts from the City of Boca Raton public website, 1988–2025. Source: https://www.myboca.us/2140/Sea-Turtle-Nesting-Totals . Counts apply to Boca Raton beaches, not all Florida. Review against the live source before publishing. `smoke_test.py` uses synthetic example data. No model weights are bundled.

## Windows PowerShell (Python 3.11)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install 'timesfm[torch]'
.\.venv\Scripts\python.exe smoke_test.py
.\.venv\Scripts\python.exe forecast_csv.py boca_counts.csv
```

If the `timesfm` PyPI release does not expose `timesfm3`, follow Google's current installation guidance at https://github.com/google-research/timesfm and install its GitHub source instead:

```powershell
.\.venv\Scripts\python.exe -m pip install 'git+https://github.com/google-research/timesfm.git'
```

Model: https://huggingface.co/google/timesfm-3.0-pytorch . The pretrained weights have a **noncommercial, nonproduction** license. Local internet access is needed to download them the first time.

## Output

`forecast_csv.py` produces `nesting_forecasts.json` plus a one-year holdout comparison. It defaults to CPU so the RTX 4050's 6 GB VRAM doesn't cause a GPU out-of-memory error; CPU execution may be slow. After verifying this run, change `device='cpu'` to `device='cuda'` if CUDA-enabled PyTorch is installed and enough memory is available. This is a forecast experiment, not a validated conservation forecast. A genuine accuracy assessment should backtest multiple years against seasonal and trailing-average baselines.

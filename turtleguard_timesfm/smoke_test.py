import numpy as np
from timesfm3 import TimesFM3Evaluator, ModelConfig

print('Loading TimesFM 3 (first run downloads model weights)...', flush=True)
forecaster = TimesFM3Evaluator(ModelConfig(checkpoint_path='google/timesfm-3.0-pytorch', per_core_batch_size=1, device='cpu'))
series = np.array([740,770,730,850,810,880,840,790,870,900,860,920,880,890,930,950,910,970,980,960,1000,990,1020,1010,1030,1020,1050,1040,1070,1080,1060,1100], dtype=np.float32)
prediction = next(iter(forecaster.predict_batch([series], horizon=1, return_quantiles=True, use_symmetric_averaging=False)))
print('Success: one-step demonstration forecast:', prediction.forecast.tolist())
print('This demonstration series is synthetic, not turtle nesting data.')

from dataclasses import asdict, is_dataclass
from enum import Enum
import numpy as np

def probability_calibration_governance_to_dict(value):
    if is_dataclass(value): return {k:probability_calibration_governance_to_dict(v) for k,v in asdict(value).items()}
    if isinstance(value,dict): return {str(k):probability_calibration_governance_to_dict(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [probability_calibration_governance_to_dict(v) for v in value]
    if isinstance(value,Enum): return value.value
    if isinstance(value,np.generic): return value.item()
    return value

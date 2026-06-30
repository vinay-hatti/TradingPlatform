import numpy as np


def safe_div(a, b):
    if b == 0:
        return 0
    return a / b


def sigmoid(x):
    return 1 / (1 + np.exp(-x))

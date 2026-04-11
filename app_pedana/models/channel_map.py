from __future__ import annotations

P1_CHANNELS = {
    "P1_FZ1": "Dev1/ai0",
    "P1_FZ2": "Dev1/ai1",
    "P1_FZ3": "Dev1/ai2",
    "P1_FZ4": "Dev1/ai3",
    "P1_FY14": "Dev1/ai4",
    "P1_FY23": "Dev1/ai5",
    "P1_FX12": "Dev1/ai6",
    "P1_FX34": "Dev1/ai7",
}

P2_CHANNELS = {
    "P2_FZ1": "Dev1/ai8",
    "P2_FZ2": "Dev1/ai9",
    "P2_FZ3": "Dev1/ai10",
    "P2_FZ4": "Dev1/ai11",
    "P2_FY14": "Dev1/ai12",
    "P2_FY23": "Dev1/ai13",
    "P2_FX12": "Dev1/ai14",
    "P2_FX34": "Dev1/ai15",
}

DEFAULT_CHANNEL_MAP = {**P1_CHANNELS, **P2_CHANNELS}

FZ_CHANNEL_NAMES = [
    "P1_FZ1",
    "P1_FZ2",
    "P1_FZ3",
    "P1_FZ4",
    "P2_FZ1",
    "P2_FZ2",
    "P2_FZ3",
    "P2_FZ4",
]

P1_FZ_CHANNELS = ["P1_FZ1", "P1_FZ2", "P1_FZ3", "P1_FZ4"]
P2_FZ_CHANNELS = ["P2_FZ1", "P2_FZ2", "P2_FZ3", "P2_FZ4"]

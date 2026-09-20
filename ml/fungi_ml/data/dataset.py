"""Torch dataset and augmentation policy.

Augmentation is deliberately conservative on colour. Cap colour, gill colour
and bruising reactions are diagnostic characters -- aggressive colour jitter
teaches the model to ignore exactly the signal a mycologist relies on. We
vary geometry and lighting freely and keep hue nearly fixed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset, WeightedRandomSampler
from torchvision import transforms

from .prepare import METADATA_COLUMNS

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def build_transforms(image_size: int, train: bool) -> transforms.Compose:
    if train:
        return transforms.Compose(
            [
                transforms.RandomResizedCrop(
                    image_size, scale=(0.5, 1.0), ratio=(0.75, 1.33)
                ),
                transforms.RandomHorizontalFlip(),
                # No vertical flip: a mushroom photographed upside down is a
                # different diagnostic view, not the same one mirrored.
                transforms.RandomApply(
                    [transforms.RandomRotation(20, expand=False)], p=0.3
                ),
                transforms.ColorJitter(
                    brightness=0.25, contrast=0.25, saturation=0.15, hue=0.02
                ),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
                transforms.RandomErasing(p=0.25, scale=(0.02, 0.15)),
            ]
        )
    return transforms.Compose(
        [
            transforms.Resize(int(image_size * 1.14)),
            transforms.CenterCrop(image_size),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )


class FungiDataset(Dataset):
    def __init__(
        self,
        manifest: pd.DataFrame,
        split: str,
        image_size: int = 384,
        train: bool | None = None,
    ):
        self.frame = manifest[manifest["split"] == split].reset_index(drop=True)
        if self.frame.empty:
            raise ValueError(f"No rows for split {split!r}")
        self.is_train = train if train is not None else (split == "train")
        self.image_size = image_size
        self.transform = build_transforms(image_size, self.is_train)
        self.metadata = self.frame[METADATA_COLUMNS].to_numpy(dtype=np.float32)
        self.labels = self.frame["label"].to_numpy(dtype=np.int64)
        self.paths = self.frame["path"].tolist()

    def __len__(self) -> int:
        return len(self.frame)

    def __getitem__(self, idx: int):
        path = self.paths[idx]
        try:
            image = Image.open(path).convert("RGB")
        except (OSError, ValueError):
            # A truncated download must not kill a multi-hour training run.
            image = Image.new("RGB", (self.image_size, self.image_size), (0, 0, 0))
        return (
            self.transform(image),
            torch.from_numpy(self.metadata[idx]),
            int(self.labels[idx]),
        )


def build_balanced_sampler(dataset: FungiDataset) -> WeightedRandomSampler:
    """Oversample rare species so the long tail is learned, not memorised.

    Weights go as 1/sqrt(count) rather than 1/count. Full inverse-frequency
    weighting over-corrects on a tail this long and destabilises training.
    """
    labels = dataset.labels
    counts = np.bincount(labels, minlength=int(labels.max()) + 1).astype(np.float64)
    counts[counts == 0] = 1.0
    weights = 1.0 / np.sqrt(counts)
    sample_weights = weights[labels]
    return WeightedRandomSampler(
        weights=torch.as_tensor(sample_weights, dtype=torch.double),
        num_samples=len(labels),
        replacement=True,
    )


def load_manifest(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(path)

"""Model definition: a timm vision backbone fused with field metadata.

The metadata branch is small but earns its place. Fungal fruiting is
intensely seasonal and geographically bounded, so month and coarse location
carry real discriminative signal -- often more than the last few points of
backbone capacity. Consumer apps collect this data and then throw it away.

Missing metadata is handled by explicit `*_known` flags rather than
imputation. A model told "it is January" when the month is actually unknown
will happily rule out autumn species that are in fact the right answer.
"""

from __future__ import annotations

from copy import deepcopy

import torch
import torch.nn as nn

try:
    import timm
except ImportError as exc:  # pragma: no cover - surfaced at runtime only
    raise ImportError(
        "timm is required. Install the training extras: pip install -r ml/requirements.txt"
    ) from exc


class MetadataEncoder(nn.Module):
    """Projects the 7-dim field metadata vector into the fusion space."""

    def __init__(self, in_dim: int = 7, out_dim: int = 128, dropout: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, out_dim),
            nn.LayerNorm(out_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(out_dim, out_dim),
            nn.LayerNorm(out_dim),
            nn.GELU(),
        )

    def forward(self, meta: torch.Tensor) -> torch.Tensor:
        return self.net(meta)


class FungiClassifier(nn.Module):
    """Vision backbone + metadata branch -> species logits.

    Set `metadata_dropout` above zero during training so the model learns to
    cope without metadata. Users skip the habitat questions constantly, and a
    model that collapses when they do is useless in the field.
    """

    def __init__(
        self,
        num_classes: int,
        backbone: str = "vit_base_patch16_384.augreg_in21k_ft_in1k",
        pretrained: bool = True,
        metadata_dim: int = 7,
        metadata_width: int = 128,
        drop_rate: float = 0.1,
        drop_path_rate: float = 0.2,
        metadata_dropout: float = 0.3,
        use_metadata: bool = True,
    ):
        super().__init__()
        self.use_metadata = use_metadata
        self.metadata_dropout = metadata_dropout
        self.num_classes = num_classes

        self.backbone = timm.create_model(
            backbone,
            pretrained=pretrained,
            num_classes=0,  # feature extractor; we own the head
            drop_rate=drop_rate,
            drop_path_rate=drop_path_rate,
        )
        visual_dim = self.backbone.num_features

        if use_metadata:
            self.metadata_encoder = MetadataEncoder(metadata_dim, metadata_width, drop_rate)
            fused_dim = visual_dim + metadata_width
        else:
            self.metadata_encoder = None
            fused_dim = visual_dim

        self.head = nn.Sequential(
            nn.LayerNorm(fused_dim),
            nn.Dropout(drop_rate),
            nn.Linear(fused_dim, num_classes),
        )

    def forward_features(
        self, images: torch.Tensor, metadata: torch.Tensor | None = None
    ) -> torch.Tensor:
        visual = self.backbone(images)
        if not self.use_metadata or self.metadata_encoder is None:
            return visual

        if metadata is None:
            metadata = images.new_zeros((images.shape[0], 7))

        if self.training and self.metadata_dropout > 0:
            # Drop the whole metadata vector for a fraction of the batch so
            # the visual pathway stays self-sufficient.
            mask = (
                torch.rand(metadata.shape[0], 1, device=metadata.device)
                >= self.metadata_dropout
            ).float()
            metadata = metadata * mask

        return torch.cat([visual, self.metadata_encoder(metadata)], dim=1)

    def forward(
        self, images: torch.Tensor, metadata: torch.Tensor | None = None
    ) -> torch.Tensor:
        return self.head(self.forward_features(images, metadata))

    def parameter_groups(self, base_lr: float, backbone_lr_mult: float) -> list[dict]:
        """Discriminative learning rates: a gentler rate on pretrained weights."""
        backbone_params = list(self.backbone.parameters())
        head_params = list(self.head.parameters())
        if self.metadata_encoder is not None:
            head_params += list(self.metadata_encoder.parameters())
        return [
            {"params": backbone_params, "lr": base_lr * backbone_lr_mult},
            {"params": head_params, "lr": base_lr},
        ]


def build_model(config: dict, num_classes: int) -> FungiClassifier:
    model_cfg = config.get("model", {})
    return FungiClassifier(
        num_classes=num_classes,
        backbone=model_cfg.get("backbone", "vit_base_patch16_384.augreg_in21k_ft_in1k"),
        pretrained=model_cfg.get("pretrained", True),
        drop_rate=model_cfg.get("drop_rate", 0.1),
        drop_path_rate=model_cfg.get("drop_path_rate", 0.2),
        metadata_dropout=model_cfg.get("metadata_dropout", 0.3),
        use_metadata=model_cfg.get("use_metadata", True),
    )


def load_checkpoint_model(checkpoint: dict) -> FungiClassifier:
    """Rebuild the exact architecture a checkpoint was trained with.

    Calibration and export both need the trained model back, and both used to
    reconstruct it by hand from two config keys. That quietly dropped every
    other architectural switch -- `use_metadata` above all, which changes the
    state dict -- so a run configured without the metadata branch trained
    fine and then failed at calibration, after the GPU time had been spent.

    Routing all three through `build_model` means the architecture can only be
    described in one place. `pretrained` is forced off: the weights come from
    the checkpoint, and fetching backbone weights we are about to overwrite
    costs a download and needs network the serving box may not have.
    """
    config = deepcopy(checkpoint["config"])
    config.setdefault("model", {})["pretrained"] = False
    model = build_model(config, len(checkpoint["classes"]))
    model.load_state_dict(checkpoint["model"])
    return model.eval()

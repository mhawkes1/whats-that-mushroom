"""The config file and the code must agree, in both directions.

Audited on 2026-10-19, before the first paid GPU run. Nine keys in
`default.yaml` were read by nobody, and two keys the code *does* read were
not in the file at all -- one of them `risk_strength`, which is what makes
this model different from an ordinary classifier.

Both failures are quiet. A dead key reads as a decision somebody made:
`mixup_alpha: 0.2` sat there for months while the training loop used hard
targets throughout, so anyone reading the file would conclude the model had
seen augmentation it has never seen. An undeclared key is worse in the
other direction -- it has a default buried in `train.py` and nobody tuning
a run ever sees it.

Neither is caught by a run completing successfully, which is exactly why
this is a test and not a code review.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "ml" / "configs" / "default.yaml"
PACKAGE = ROOT / "ml" / "fungi_ml"


def _flatten(d: dict, prefix: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in d.items():
        if isinstance(value, dict):
            out.update(_flatten(value, f"{prefix}{key}."))
        else:
            out[f"{prefix}{key}"] = value
    return out


@pytest.fixture(scope="module")
def config() -> dict[str, object]:
    return _flatten(yaml.safe_load(CONFIG.read_text()))


@pytest.fixture(scope="module")
def source() -> str:
    return "\n".join(p.read_text() for p in sorted(PACKAGE.rglob("*.py")))


# Keys that are in the file on purpose while nothing reads them. Each needs
# a reason, and the reason has to be that the *value* is informative even
# though the code ignores it. Ten keys were dead when this was written; these
# two are what survived the clear-out.
# Empty since 2026-10-28, when mixup and cutmix were wired up and left it
# so. Both were exempted here for months on the grounds that a 0.0 value
# was an informative statement about augmentation the loop never performed;
# `train.py` now reads them, so the exemptions came out in the same commit
# that made them false. Nothing is exempt today, and that is the state to
# return to rather than the one to add a line to.
DECLARED_BUT_UNREAD: dict[str, str] = {}


def test_every_config_key_is_read_by_something(config, source):
    """No key may sit in the file doing nothing unexplained.

    Matched on the quoted leaf, which is how the code reads them:
    `config["train"]["epochs"]`. A loose check -- it cannot tell `"epochs"`
    in a config lookup from `"epochs"` in a log string -- and tight enough
    to have caught all ten, including `eval.topk`, which matched the
    evaluator's own default by coincidence rather than by wiring.
    """
    dead = [
        key
        for key in config
        if key not in DECLARED_BUT_UNREAD
        and not re.search(rf'["\']{re.escape(key.split(".")[-1])}["\']', source)
    ]
    assert dead == [], (
        "config keys nothing reads -- implement them, delete them, or add "
        "them to DECLARED_BUT_UNREAD with a reason. A dead setting reads as "
        f"a decision somebody made: {dead}"
    )


def test_the_allowlist_has_not_become_a_dumping_ground(config):
    """Every exemption must still be a key, and must still carry a reason.

    An allowlist entry for a key that has since been deleted is a comment
    nobody will read; one with an empty reason is the habit this test exists
    to prevent.
    """
    for key, reason in DECLARED_BUT_UNREAD.items():
        assert key in config, f"{key} is exempted but no longer in the config"
        assert len(reason) > 20, f"{key} is exempted without a real reason"


@pytest.mark.parametrize(
    "key",
    [
        "data.taxonomy",
        "train.risk_strength",
        "train.epochs",
        "train.batch_size",
        "data.image_size",
        "output.dir",
    ],
)
def test_keys_the_trainer_reads_are_declared(config, key):
    """Specifically the two that were missing, plus the obvious ones.

    `train.py` reads `data.taxonomy` and `train.risk_strength` through
    `.get()` with a fallback, so the run works without them and nobody
    notices they are tunable.
    """
    assert key in config, f"{key} is read by train.py but absent from the config"


def test_risk_strength_is_on(config):
    """Rule 6, at the level of the file that configures the run.

    0 trains an ordinary accuracy-seeking classifier. That is a legitimate
    ablation and must never be what `default.yaml` ships.
    """
    assert float(config["train.risk_strength"]) > 0


def test_the_mixing_alphas_and_the_loop_agree_in_both_directions(config):
    """The alphas say what the model saw, so they must match the loop.

    This replaced a test that asserted the alphas were 0.0 *while* nothing
    read them, with an `if not wired:` guard that was to be deleted when
    somebody wired it up. Wiring it up made that test pass vacuously
    instead -- a guard that silently stops guarding is the failure this
    file exists to catch, so the shape is now unconditional.
    """
    source = (PACKAGE / "train.py").read_text()
    mixing_declared = (float(config["train.mixup_alpha"]) > 0
                       or float(config["train.cutmix_alpha"]) > 0)
    loop_can_mix = "Mixer(" in source and "SoftTargetRiskLoss(" in source

    if mixing_declared:
        assert loop_can_mix, (
            "the config declares augmentation the training loop cannot "
            "perform -- a reader would conclude the model saw it"
        )
        assert "mixer(images, labels)" in source, (
            "a Mixer is built and never applied to a batch"
        )
    # And the other way: the loop must still be able to train without it,
    # because 0.0/0.0 is a legitimate ablation and was the shipping config.
    assert "RiskWeightedCrossEntropy(" in source, (
        "the hard-target path was removed; mixing must stay optional"
    )


def test_mix_prob_is_a_probability(config):
    """It gates how often a batch is mixed at all. Above 1 it silently
    means `always` and below 0 it means `never`, either of which is a
    config that does not do what it says."""
    assert 0.0 <= float(config["train.mix_prob"]) <= 1.0


def test_checkpoint_selection_is_on_risk_not_accuracy():
    """Rule 6 itself, read off the training loop.

    The config no longer offers `save_top_k`, because a top-k selected on
    the wrong metric is a footgun rather than a feature. This asserts the
    metric the loop actually keeps.
    """
    source = (PACKAGE / "train.py").read_text()
    assert "best_risk" in source
    assert 'metrics["risk"]' in source
    assert not re.search(r"best_acc|best_accuracy|metrics\[.accuracy.\]", source)


class TestDataPathsResolve:
    """Every `data:` path must mean the same thing from any directory.

    Found on the first real GPU run, 2026-10-27, after a two-hour dataset
    build: the config carried `manifest: data/processed/...` (wanting the
    repo root as cwd) beside `taxonomy: ../data/...` (wanting `ml/`). No
    single working directory satisfied both, so the command
    `build_dataset.py` prints as "Next:" failed from everywhere -- and
    failed at the point where the meter had already been running for two
    hours.

    `train._data_path` anchors them to the repo root. These read the source
    rather than importing it, like the rest of this file, so the checks run
    without torch installed.
    """

    def test_the_trainer_anchors_data_paths_to_the_repo_root(self):
        source = (PACKAGE / "train.py").read_text()
        assert "REPO_ROOT" in source
        assert "def _data_path" in source
        # Each of the three must go through it, or the one that does not is
        # the one that breaks, and only on a machine with a different cwd.
        for key in ("manifest", "label_map", "taxonomy"):
            assert re.search(rf'_data_path\([^)]*{key}', source), (
                f"config['data']['{key}'] is not resolved through _data_path"
            )

    def test_output_dir_is_deliberately_not_anchored(self):
        # `runs/baseline` must keep landing in `ml/runs/baseline`, which is
        # where the run-book's later steps look for best.pt and the model
        # card. Anchoring it would silently move every documented path.
        source = (PACKAGE / "train.py").read_text()
        assert 'Path(config["output"]["dir"])' in source

    def test_no_data_path_climbs_out_of_the_repo(self, config):
        # `../data/...` was the whole bug: read from `ml/` it worked, read
        # from anywhere else it pointed outside the checkout entirely.
        for key, value in config.items():
            if key.startswith("data.") and isinstance(value, str):
                assert not value.startswith(".."), (
                    f"{key} is {value!r}; data paths resolve against the repo "
                    "root, so a leading '..' leaves the checkout"
                )

    def test_the_taxonomy_the_config_names_is_really_there(self, config):
        # The check that would have caught the original bug outright.
        assert (ROOT / str(config["data.taxonomy"])).is_file()

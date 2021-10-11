#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Model Interpretability App Example
=============================================

This is an example TorchX app that uses captum to analyze inputs to for model
interpretability purposes. It consumes the trained model from the trainer app
example and the preprocessed examples from the datapreproc app example. The
output is a series of images with integrated gradient attributions overlayed on
them.

See https://captum.ai/tutorials/CIFAR_TorchVision_Interpret for more info on
using captum.
"""

import argparse
import itertools
import os.path
import sys
import tempfile
from typing import List

import fsspec
import torch

# ensure data and module are on the path
sys.path.append(".")

from torchx.examples.apps.lightning_classy_vision.data import (
    TinyImageNetDataModule,
    download_data,
)
from torchx.examples.apps.lightning_classy_vision.model import TinyImageNetModel


# FIXME: captum must be imported after torch otherwise it causes python to crash
if True:
    import numpy as np
    from captum.attr import IntegratedGradients
    from captum.attr import visualization as viz


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="example TorchX captum app")
    parser.add_argument(
        "--load_path",
        type=str,
        help="checkpoint path to load model weights from",
        required=True,
    )
    parser.add_argument(
        "--data_path",
        type=str,
        help="path to load the training data from",
        required=True,
    )
    parser.add_argument(
        "--output_path",
        type=str,
        help="path to place analysis results",
        required=True,
    )

    return parser.parse_args(argv)


def convert_to_rgb(arr: torch.Tensor) -> np.ndarray:  # pyre-ignore[24]
    """
    This converts the image from a torch tensor with size (1, 1, 64, 64) to
    numpy array with size (64, 64, 3).
    """
    squeezed = arr.squeeze()
    stacked = torch.stack([squeezed, squeezed, squeezed], dim=2)
    print("img stats: ", stacked.count_nonzero(), stacked.mean())
    return stacked.numpy()


def main(argv: List[str]) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        args = parse_args(argv)

        # Init our model
        model = TinyImageNetModel()

        print(f"loading checkpoint: {args.load_path}...")
        model.load_from_checkpoint(checkpoint_path=args.load_path)

        # Download and setup the data module
        data_path = download_data(args.data_path, tmpdir)
        data = TinyImageNetDataModule(
            data_dir=data_path,
            batch_size=1,
        )

        ig = IntegratedGradients(model)

        data.setup("test")
        dataloader = data.test_dataloader()

        # process first 5 images
        for i, (input, label) in enumerate(itertools.islice(dataloader, 5)):
            print(f"analyzing example {i}")
            model.zero_grad()
            attr_ig, delta = ig.attribute(
                input,
                target=label,
                baselines=input * 0,
                return_convergence_delta=True,
            )

            if attr_ig.count_nonzero() == 0:
                # Our toy model sometimes has no IG results.
                print("skipping due to zero gradients")
                continue

            fig, axis = viz.visualize_image_attr(
                convert_to_rgb(attr_ig),
                convert_to_rgb(input),
                method="blended_heat_map",
                sign="all",
                show_colorbar=True,
                title="Overlayed Integrated Gradients",
            )
            out_path = os.path.join(args.output_path, f"ig_{i}.png")
            print(f"saving heatmap to {out_path}")
            with fsspec.open(out_path, "wb") as f:
                fig.savefig(f)


if __name__ == "__main__" and "NOTEBOOK" not in globals():
    main(sys.argv[1:])
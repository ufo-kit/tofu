import sys
import types
from types import SimpleNamespace

import numpy as np
import pytest


def ensure_ufo_importable():
    try:
        import gi

        try:
            gi.require_version('Ufo', '0.0')
        except ValueError:
            gi.require_version('Ufo', '1.0')
        from gi.repository import Ufo  # noqa: F401
    except (ImportError, ValueError):
        gi = types.ModuleType("gi")
        repository = types.ModuleType("gi.repository")

        gi.require_version = lambda *args: None
        gi.repository = repository

        class UfoStub:
            class PluginManager:
                pass

            class TaskGraph:
                pass

            class Scheduler:
                pass

            class FixedScheduler:
                pass

            class Resources:
                pass

        repository.Ufo = UfoStub
        sys.modules["gi"] = gi
        sys.modules["gi.repository"] = repository


ensure_ufo_importable()

from tofu import tune


def test_apply_tune_defaults_uses_interactive_defaults(monkeypatch):
    monkeypatch.setattr(tune.sys, "argv", ["tofu", "tune"])
    args = SimpleNamespace(
        width=None,
        height=None,
        energy=None,
        propagation_distance=None,
        ict_alpha_threshold=0.0,
        frequency_cutoff=0.0,
        sharpen_method="laplace",
    )

    tune.apply_tune_defaults(args)

    assert args.width == 1024
    assert args.height == 1024
    assert args.energy == 15
    assert args.propagation_distance == (0.1,)
    assert args.ict_alpha_threshold == 1e30
    assert args.frequency_cutoff == 0.0
    assert args.sharpen_method == "lorentz"


def test_apply_tune_defaults_keeps_command_line_values(monkeypatch):
    monkeypatch.setattr(
        tune.sys,
        "argv",
        [
            "tofu",
            "tune",
            "--width=512",
            "--energy=20",
            "--propagation-distance",
            "0.2",
            "--ict-alpha-threshold=3.5",
            "--sharpen-method=laplace",
        ],
    )
    args = SimpleNamespace(
        width=512,
        height=None,
        energy=20,
        propagation_distance=(0.2,),
        ict_alpha_threshold=3.5,
        frequency_cutoff=1e30,
        sharpen_method="laplace",
    )

    tune.apply_tune_defaults(args)

    assert args.width == 512
    assert args.height == 1024
    assert args.energy == 20
    assert args.propagation_distance == (0.2,)
    assert args.ict_alpha_threshold == 3.5
    assert args.frequency_cutoff == 1e30
    assert args.sharpen_method == "laplace"


@pytest.mark.parametrize(
    "region, text",
    [
        ((0, -1, 1), "0,-1,1"),
        ((-1.5, 2.25, 0.5), "-1.5,2.25,0.5"),
        (np.array([1.0, 2.0, 0.25]), "1,2,0.25"),
    ],
)
def test_format_region(region, text):
    assert tune.format_region(region) == text


@pytest.mark.parametrize(
    "value, default, text",
    [
        (None, 2.0, "2"),
        ((3.0,), 0.0, "3"),
        ([1.25], 0.0, "1.25"),
        (np.array([]), 4.0, "4"),
    ],
)
def test_format_scalar(value, default, text):
    assert tune.format_scalar(value, default=default) == text


@pytest.mark.parametrize(
    "value, text",
    [
        (None, ""),
        (True, "True"),
        (False, "False"),
        ((1, 2.5, "x"), "1,2.5,x"),
        (np.array([1.0, 2.0]), "1.0,2.0"),
    ],
)
def test_format_config_value(value, text):
    assert tune.format_config_value(value) == text


def test_parse_region_accepts_comma_separated_floats():
    assert tune.parse_region(" -3.5, 4, 0.5 ", "x region") == (-3.5, 4.0, 0.5)


@pytest.mark.parametrize(
    "text, message",
    [
        ("0,1", "from,to,step"),
        ("0,,1", "from,to,step"),
        ("a,1,1", "numeric"),
        ("0,1,0", "step must not be zero"),
        ("0,0,1", "does not select any pixels"),
    ],
)
def test_parse_region_rejects_invalid_regions(text, message):
    with pytest.raises(ValueError, match=message):
        tune.parse_region(text, "x region")


def test_prepare_processing_args_uses_projection_shape(monkeypatch):
    import tofu.util

    monkeypatch.setattr(tofu.util, "determine_shape", lambda *a, **kw: (63, 65))
    args = SimpleNamespace(projections="projections.tif", number=None)

    prepared = tune._prepare_processing_args(args, sharpen=True)

    assert prepared.sharpen is True
    assert prepared.width == 63
    assert prepared.height == 65
    assert prepared.retrieval_padded_width == 64
    assert prepared.retrieval_padded_height == 128
    assert prepared.number == 1
    assert prepared.darks is None
    assert prepared.flats is None
    assert prepared.transpose_input is False


def make_reconstruction_args(**overrides):
    args = SimpleNamespace(
        projections="projections.tif",
        number=None,
        energy=15.0,
        propagation_distance=(0.1,),
        pixel_size=1e-3,
        retrieval_method="tie",
        sharpen_method="lorentz",
        reconstruction_slice=32,
        overall_angle=180.0,
        center_position_x=0.0,
        center_position_z=[0.5],
        axis_angle_x=[0.0],
        axis_angle_y=[0.0],
        x_region=(0.0, -1.0, 1.0),
        y_region=(0.0, -1.0, 1.0),
    )
    for name, value in overrides.items():
        setattr(args, name, value)

    return args


def test_prepare_reconstruction_args_uses_larger_phase_margin(monkeypatch):
    import tofu.util

    monkeypatch.setattr(tofu.util, "determine_shape", lambda *a, **kw: (63, 64))
    monkeypatch.setattr(tune, "get_single_tiff_sequence_info", lambda path: None)
    monkeypatch.setattr(tune, "get_fresnel_required_half_height", lambda *a: 8)
    monkeypatch.setattr(
        tune,
        "get_reconstruction_projection_region",
        lambda *a: (-10, 30, 10, 35),
    )

    prepared = tune._prepare_reconstruction_args(
        make_reconstruction_args(), sharpen=True, phase_retrieval=True)

    assert prepared.sharpen is True
    assert prepared.delta == 1e-6
    assert prepared.retrieval_padding_mode == "clamp_to_edge"
    assert prepared.disable_projection_crop is True
    assert prepared.y == 22
    assert prepared.height == 20
    assert prepared.center_position_z == [-21.5]
    assert prepared.z == 32
    assert prepared.region == (32, 33, 1)
    assert prepared.width == 63
    assert prepared.retrieval_padded_width == 64
    assert prepared.retrieval_padded_height == 32


def test_prepare_reconstruction_args_absorption_uses_geometry_only(monkeypatch):
    import tofu.util

    monkeypatch.setattr(tofu.util, "determine_shape", lambda *a, **kw: (63, 64))
    monkeypatch.setattr(tune, "get_single_tiff_sequence_info", lambda path: None)
    monkeypatch.setattr(
        tune,
        "get_reconstruction_projection_region",
        lambda *a: (-10, 30, 10, 35),
    )

    prepared = tune._prepare_reconstruction_args(
        make_reconstruction_args(), sharpen=True, phase_retrieval=False)

    assert prepared.sharpen is False
    assert prepared.energy is None
    assert prepared.propagation_distance is None
    assert prepared.absorptivity is True
    assert prepared.y == 30
    assert prepared.height == 5
    assert prepared.center_position_z == [-29.5]
    assert prepared.retrieval_padded_width == 64
    assert prepared.retrieval_padded_height == 8


def test_prepare_reconstruction_args_rejects_slice_outside_height(monkeypatch):
    import tofu.util

    monkeypatch.setattr(tofu.util, "determine_shape", lambda *a, **kw: (63, 64))
    monkeypatch.setattr(tune, "get_single_tiff_sequence_info", lambda path: None)

    with pytest.raises(ValueError, match="outside the projection height"):
        tune._prepare_reconstruction_args(
            make_reconstruction_args(reconstruction_slice=123),
            sharpen=False,
            phase_retrieval=True,
        )


def test_get_result_data_by_method_uses_absorption_when_no_methods(monkeypatch):
    calls = []

    def fake_get_result_data(args, sharpen=False, phase_retrieval=True):
        calls.append((sharpen, phase_retrieval))
        return "projection"

    monkeypatch.setattr(tune, "get_result_data", fake_get_result_data)

    result = tune.get_result_data_by_method(SimpleNamespace(retrieval_methods=[]))

    assert result == {"absorption": {"phase": "projection"}}
    assert calls == [(False, False)]


def test_get_reconstruction_data_by_method_uses_absorption_when_no_methods(monkeypatch):
    calls = []

    def fake_get_reconstruction_data(args, sharpen=False, phase_retrieval=True):
        calls.append((sharpen, phase_retrieval))
        return "slice"

    monkeypatch.setattr(tune, "get_reconstruction_data", fake_get_reconstruction_data)

    result = tune.get_reconstruction_data_by_method(SimpleNamespace(retrieval_methods=[]))

    assert result == {"absorption": {"phase": "slice"}}
    assert calls == [(False, False)]

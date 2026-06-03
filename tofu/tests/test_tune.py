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


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, False),
        (1, True),
        (2, True),
        (3, False),
        (1024, True),
    ],
)
def test_is_power_of_two(value, expected):
    assert tune.is_power_of_two(value) is expected


def test_powers_of_two_and_closest_power_of_two():
    assert list(tune.powers_of_two(minimum=4, maximum=33)) == [4, 8, 16, 32]
    assert tune.closest_power_of_two(17, minimum=4, maximum=64) == 16
    assert tune.closest_power_of_two(50, minimum=4, maximum=64) == 64


def make_filter_args(**overrides):
    args = SimpleNamespace(
        width=4,
        height=4,
        energy=15.0,
        pixel_size=1e-6,
        propagation_distance=(0.1,),
        retrieval_method="tie",
        regularization_rate=2.0,
        thresholding_rate=0.0,
        ict_alpha=0.01,
        ict_alpha_threshold=1.0,
        frequency_cutoff=1.0,
    )
    for name, value in overrides.items():
        setattr(args, name, value)

    return args


def test_validate_args_accepts_power_of_two_dimensions():
    tune.validate_args(make_filter_args())


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"width": 0}, "width must be greater than 0"),
        ({"width": 3}, "width must be a power of 2"),
        ({"height": None}, "height must be greater than 0"),
        ({"height": 6}, "height must be a power of 2"),
        ({"energy": None}, "energy must be greater than 0"),
        ({"pixel_size": 0}, "pixel size must be greater than 0"),
        ({"propagation_distance": None}, "distance must be specified"),
        ({"propagation_distance": (0.1, 0.2, 0.3)}, "distance must contain one value or x,y"),
        ({"propagation_distance": (-0.1,)}, "distance must be greater than 0"),
    ],
)
def test_validate_args_reports_invalid_parameters(overrides, message):
    with pytest.raises(ValueError, match=message):
        tune.validate_args(make_filter_args(**overrides))


def test_validate_result_args_uses_synthetic_power_of_two_dimensions():
    args = make_filter_args(width=63, height=65)

    tune.validate_result_args(args)

    assert args.width == 63
    assert args.height == 65


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


def test_default_and_expanded_display_regions():
    assert tune.make_default_region(5) == (-2.5, 3.5, 1.0)
    assert tune.make_default_region(4) == (-2.0, 2.0, 1.0)
    assert tune.expand_display_region((0, -1, 1), 6) == (-3.0, 3.0, 1.0)
    assert tune.expand_display_region((1, 4, 0.5), 6) == (1.0, 4.0, 0.5)


def test_percentile_levels_ignore_non_finite_values_and_expand_flat_data():
    assert tune.get_percentile_levels([np.nan, np.inf]) is None
    low, high = tune.get_percentile_levels(np.ones((3, 3)) * 5)
    assert low < 5 < high
    assert tune.get_percentile_levels(np.arange(100), lower=10, upper=90) == pytest.approx(
        (9.9, 89.1))


def test_frequency_helpers_use_fresnel_argument_when_args_are_available():
    args = make_filter_args(energy=20.0, propagation_distance=(0.2,), pixel_size=2e-6)
    frequencies = np.array([0.0, 0.25, 0.5])
    wavelength = tune.get_wavelength(args.energy)

    expected = np.pi * wavelength * args.propagation_distance[0] * frequencies ** 2
    expected /= args.pixel_size ** 2

    np.testing.assert_allclose(tune.get_ict_argument(frequencies, args), expected)
    assert tune.get_ict_argument(frequencies, None) is frequencies
    assert tune.get_ict_argument(frequencies, make_filter_args(energy=None)) is frequencies
    assert tune.get_max_ict_argument(args.energy, 0.2, args.pixel_size) == pytest.approx(
        expected[-1])


def test_fresnel_required_half_height_has_minimum_and_ceil():
    assert tune.get_fresnel_required_half_height(15.0, 0.1, 1e-3) == 16

    energy = 20.0
    distance = 0.2
    pixel_size = 1e-8
    expected = np.ceil(tune.get_wavelength(energy) * distance / (2 * pixel_size ** 2))
    assert tune.get_fresnel_required_half_height(energy, distance, pixel_size) == expected


def test_get_first_half_frequency_row_uses_real_interleaved_values():
    data = np.array([[10, 99, 20, 98, 30, 97, 40, 96]], dtype=np.float32)
    args = make_filter_args(energy=None)

    x, row = tune.get_first_half_frequency_row(data, args=args)

    np.testing.assert_allclose(row, [10, 20])
    np.testing.assert_allclose(x, [0.0, 0.25])


def test_plot_first_row_builds_matplotlib_plot_without_showing(monkeypatch):
    shown = []
    monkeypatch.setattr("matplotlib.pyplot.show", lambda: shown.append(True))
    data = np.array([[1, 0, 2, 0, 3, 0, 4, 0]], dtype=np.float32)

    fig, ax = tune.plot_first_row(data, args=make_filter_args(energy=None), show=False)

    assert not shown
    assert ax.get_xlabel() == r"Fresnel phase $\pi \lambda d u^2$"
    assert ax.get_ylabel() == "Filter value"
    assert ax.lines[0].get_ydata().tolist() == [1, 2]
    fig.clear()


def test_get_parameter_help_and_tooltip():
    help_text = tune.get_parameter_help("energy", preferred_sections=("retrieve-phase",))
    assert help_text

    class Widget:
        tooltip = None

        def setToolTip(self, text):
            self.tooltip = text

    widget = Widget()
    tune.set_parameter_tooltip(widget, "energy", preferred_sections=("retrieve-phase",))
    assert widget.tooltip == help_text

    missing = Widget()
    tune.set_parameter_tooltip(missing, "definitely_not_a_real_parameter")
    assert missing.tooltip is None


def test_reset_profile_line_roi_preserves_state_and_restores_signal_blocking():
    class ROI:
        def __init__(self):
            self.blocked = False
            self.state = {"custom": "kept"}
            self.calls = []

        def blockSignals(self, blocked):
            previous = self.blocked
            self.blocked = blocked
            self.calls.append(blocked)
            return previous

        def saveState(self):
            return dict(self.state)

        def setState(self, state):
            self.state = state

    roi = ROI()
    tune.reset_profile_line_roi(roi, width=5, height=3)

    assert roi.calls == [True, False]
    assert roi.state["custom"] == "kept"
    assert roi.state["pos"] == (0, 0)
    assert roi.state["points"] == [(0, 1.0), (4, 1.0)]


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


def test_set_phase_retrieval_and_sharpening_properties():
    class Task:
        def __init__(self):
            self.props = SimpleNamespace()

    phase = Task()
    tune._set_phase_retrieval_props(phase, make_filter_args(propagation_distance=(0.1, 0.2)))
    assert phase.props.method == "tie"
    assert phase.props.energy == 15.0
    assert phase.props.distance_x == 0.1
    assert phase.props.distance_y == 0.2
    assert phase.props.pixel_size == 1e-6
    assert phase.props.output_filter is True

    sharpen = Task()
    args = SimpleNamespace(
        sharpen_method="lorentz",
        sharpen_strength=2.0,
        sharpen_lorentz_fwhm=0.5,
        sharpen_max_boost=4.0,
    )
    tune._set_sharpening_props(sharpen, args)
    assert sharpen.props.method == "lorentz"
    assert sharpen.props.strength == 2.0
    assert sharpen.props.lorentz_fwhm == 0.5
    assert sharpen.props.max_boost == 4.0


def test_get_filter_data_by_method_honors_visibility(monkeypatch):
    calls = []

    def fake_get_filter_data(args, sharpen=False):
        calls.append((args.retrieval_method, sharpen))
        return "{}-{}".format(args.retrieval_method, "sharpened" if sharpen else "phase")

    monkeypatch.setattr(tune, "get_filter_data", fake_get_filter_data)
    args = SimpleNamespace(
        retrieval_methods=["tie", "ctf"],
        retrieval_method="tie",
        sharpen=True,
        curve_visibility={
            "tie": {"phase": True, "sharpened": False},
            "ctf": {"phase": False, "sharpened": True},
        },
    )

    result = tune.get_filter_data_by_method(args)

    assert result == {
        "tie": {"phase": "tie-phase"},
        "ctf": {"sharpened": "ctf-sharpened"},
    }
    assert calls == [("tie", False), ("ctf", True)]


def test_get_result_and_reconstruction_data_by_method_default_visibility(monkeypatch):
    result_calls = []
    reco_calls = []

    def fake_get_result_data(args, sharpen=False, phase_retrieval=True):
        result_calls.append((args.retrieval_method, sharpen, phase_retrieval))
        return "result"

    def fake_get_reconstruction_data(args, sharpen=False, phase_retrieval=True):
        reco_calls.append((args.retrieval_method, sharpen, phase_retrieval))
        return "reco"

    monkeypatch.setattr(tune, "get_result_data", fake_get_result_data)
    monkeypatch.setattr(tune, "get_reconstruction_data", fake_get_reconstruction_data)
    args = SimpleNamespace(retrieval_method="ict", retrieval_methods=None, sharpen=True)

    assert tune.get_result_data_by_method(args) == {
        "ict": {"phase": "result", "sharpened": "result"}
    }
    assert tune.get_reconstruction_data_by_method(args) == {
        "ict": {"phase": "reco", "sharpened": "reco"}
    }
    assert result_calls == [("ict", False, True), ("ict", True, True)]
    assert reco_calls == [("ict", False, True), ("ict", True, True)]


def test_get_single_tiff_sequence_info_reads_one_tiff(monkeypatch):
    class Reader:
        num_images = 7

        def __init__(self, filename):
            self.filename = filename

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, index):
            assert index == 0
            return np.zeros((11, 13), dtype=np.float32)

    import tofu.util

    monkeypatch.setattr(tofu.util, "get_filenames", lambda path: [path])
    monkeypatch.setattr(tofu.util, "TiffSequenceReader", Reader)

    assert tune.get_single_tiff_sequence_info("projections.tif") == {
        "number": 7,
        "height": 11,
        "width": 13,
    }
    assert tune.get_single_tiff_sequence_info("projections.raw") is None
    monkeypatch.setattr(tofu.util, "get_filenames", lambda path: ["a.tif", "b.tif"])
    assert tune.get_single_tiff_sequence_info("*.tif") is None


class FakeGraph:
    def __init__(self):
        self.connections = []

    def connect_nodes(self, source, target):
        self.connections.append((source, target))


class FakeTask:
    def __init__(self, name):
        self.name = name
        self.props = SimpleNamespace()

    def __repr__(self):
        return "FakeTask({})".format(self.name)


def test_create_tune_filter_graph_without_and_with_sharpening(monkeypatch):
    tasks = []

    def fake_get_task(name):
        task = FakeTask(name)
        tasks.append(task)
        return task

    monkeypatch.setattr(tune.Ufo, "TaskGraph", FakeGraph)
    monkeypatch.setattr(tune, "get_memory_in", lambda array: ("memory-in", array.shape))
    monkeypatch.setattr(tune, "get_memory_out", lambda width, height: ("memory-out", width, height))
    monkeypatch.setattr(tune, "get_task", fake_get_task)

    graph, memory_out = tune.create_tune_filter_graph(make_filter_args(), sharpen=False)

    assert memory_out == ("memory-out", 8, 4)
    assert [task.name for task in tasks] == ["retrieve-phase"]
    assert graph.connections == [
        (("memory-in", (4, 4)), tasks[0]),
        (tasks[0], ("memory-out", 8, 4)),
    ]
    assert tasks[0].props.output_filter is False

    tasks.clear()
    args = make_filter_args()
    args.sharpen_method = "lorentz"
    args.sharpen_strength = 2.0
    args.sharpen_lorentz_fwhm = 0.4
    args.sharpen_max_boost = 3.0
    graph, memory_out = tune.create_tune_filter_graph(args, sharpen=True)

    assert [task.name for task in tasks] == ["retrieve-phase", "frequency-sharpen"]
    assert graph.connections == [
        (("memory-in", (4, 4)), tasks[0]),
        (tasks[0], tasks[1]),
        (tasks[1], ("memory-out", 8, 4)),
    ]
    assert tasks[1].props.method == "lorentz"


def test_create_result_graph_builds_phase_and_absorption_pipelines(monkeypatch):
    import tofu.preprocess
    import tofu.util

    prepared = make_filter_args(width=5, height=6)
    prepared.projections = "projections.tif"
    prepared.sharpen = False
    read = FakeTask("read")
    first = FakeTask("phase-first")
    last = FakeTask("phase-last")
    absorption_last = FakeTask("absorptivity")
    calls = []

    monkeypatch.setattr(tune.Ufo, "TaskGraph", FakeGraph)
    monkeypatch.setattr(tune, "_prepare_processing_args", lambda args, sharpen: prepared)
    monkeypatch.setattr(tune, "get_memory_out", lambda width, height: ("memory-out", width, height))
    monkeypatch.setattr(tune, "get_task", lambda name: read)
    monkeypatch.setattr(tofu.util, "set_node_props", lambda node, args: calls.append(("props", node)))
    monkeypatch.setattr(
        tofu.util,
        "setup_read_task",
        lambda node, path, args: calls.append(("read", node, path)),
    )
    monkeypatch.setattr(
        tofu.preprocess,
        "create_phase_retrieval_pipeline",
        lambda args, graph: (first, last),
    )
    monkeypatch.setattr(
        tofu.preprocess,
        "create_preprocessing_pipeline",
        lambda args, graph, cone_beam_weight=False: absorption_last,
    )

    graph, memory_out = tune.create_result_graph(SimpleNamespace(), sharpen=True, phase_retrieval=True)

    assert memory_out == ("memory-out", 5, 6)
    assert calls == [("props", read), ("read", read, "projections.tif")]
    assert graph.connections == [(read, first), (last, ("memory-out", 5, 6))]

    graph, memory_out = tune.create_result_graph(SimpleNamespace(), sharpen=True, phase_retrieval=False)

    assert prepared.energy is None
    assert prepared.propagation_distance is None
    assert prepared.absorptivity is True
    assert graph.connections == [(absorption_last, ("memory-out", 5, 6))]


def test_create_reconstruction_graph_uses_computed_slice_shape(monkeypatch):
    import tofu.genreco
    import tofu.util

    prepared = make_reconstruction_args()
    prepared.x_region = (0, 3, 1)
    prepared.y_region = (0, 4, 1)
    prepared.region = (5, 6, 1)
    backproject = FakeTask("backproject")
    calls = []

    monkeypatch.setattr(tune.Ufo, "TaskGraph", FakeGraph)
    monkeypatch.setattr(tune, "_prepare_reconstruction_args", lambda *a, **kw: prepared)
    monkeypatch.setattr(tune, "get_memory_out", lambda width, height: ("memory-out", width, height))
    monkeypatch.setattr(tofu.genreco, "_fill_missing_args", lambda args: calls.append("fill"))
    monkeypatch.setattr(tofu.genreco, "_convert_angles_to_rad", lambda args: calls.append("angles"))
    monkeypatch.setattr(tofu.genreco, "set_projection_filter_scale", lambda args: calls.append("scale"))
    monkeypatch.setattr(
        tofu.util,
        "get_reconstruction_regions",
        lambda args, store=True, dtype=float: ((0, 3, 1), (0, 4, 1), (5, 6, 1)),
    )
    monkeypatch.setattr(tofu.util, "get_reconstructed_cube_shape", lambda *regions: (3, 4, 1))
    monkeypatch.setattr(
        tofu.genreco,
        "setup_graph",
        lambda args, graph, x, y, z, gpu=None, do_output=False: ("source", backproject),
    )

    graph, memory_out = tune.create_reconstruction_graph(SimpleNamespace(), sharpen=False, gpu="gpu")

    assert calls == ["fill", "angles", "scale"]
    assert memory_out == ("memory-out", 3, 4)
    assert graph.connections == [(backproject, ("memory-out", 3, 4))]

    monkeypatch.setattr(tofu.util, "get_reconstructed_cube_shape", lambda *regions: (3, 4, 2))
    with pytest.raises(ValueError, match="expects exactly one slice"):
        tune.create_reconstruction_graph(SimpleNamespace(), sharpen=False)


def test_get_filter_result_and_reconstruction_data_run_schedulers(monkeypatch):
    scheduler_runs = []

    class Scheduler:
        def set_resources(self, resources):
            self.resources = resources

        def run(self, graph):
            scheduler_runs.append((type(self).__name__, graph, self.resources))

    class FixedScheduler(Scheduler):
        pass

    class Resources:
        def get_gpu_nodes(self):
            return ["gpu0"]

    memory_out = SimpleNamespace(np_array=np.array([[1, 2]], dtype=np.float32))
    monkeypatch.setattr(tune.Ufo, "Scheduler", Scheduler)
    monkeypatch.setattr(tune.Ufo, "FixedScheduler", FixedScheduler)
    monkeypatch.setattr(tune.Ufo, "Resources", Resources)
    monkeypatch.setattr(tune, "create_tune_filter_graph", lambda *a, **kw: ("filter-graph", memory_out))
    monkeypatch.setattr(tune, "create_result_graph", lambda *a, **kw: ("result-graph", memory_out))
    monkeypatch.setattr(
        tune,
        "create_reconstruction_graph",
        lambda *a, **kw: ("reconstruction-graph", memory_out),
    )
    monkeypatch.setattr(tune, "RESOURCES", None)

    filter_data = tune.get_filter_data(make_filter_args(), sharpen=True)
    result_data = tune.get_result_data(
        SimpleNamespace(projections="projections.tif"), sharpen=False, phase_retrieval=False)
    reco_data = tune.get_reconstruction_data(
        SimpleNamespace(projections="projections.tif"), sharpen=False, phase_retrieval=False)

    np.testing.assert_array_equal(filter_data, memory_out.np_array)
    np.testing.assert_array_equal(result_data, memory_out.np_array)
    np.testing.assert_array_equal(reco_data, memory_out.np_array)
    assert [run[0] for run in scheduler_runs] == ["Scheduler", "Scheduler", "FixedScheduler"]
    assert [run[1] for run in scheduler_runs] == [
        "filter-graph", "result-graph", "reconstruction-graph"]


def test_get_reconstruction_data_requires_gpu(monkeypatch):
    class Resources:
        def get_gpu_nodes(self):
            return []

    monkeypatch.setattr(tune.Ufo, "Resources", Resources)
    monkeypatch.setattr(tune, "RESOURCES", None)

    with pytest.raises(RuntimeError, match="No UFO GPU nodes"):
        tune.get_reconstruction_data(
            SimpleNamespace(projections="projections.tif"), phase_retrieval=False)


def test_float_slider_linear_and_log_modes(qtbot):
    from PyQt5 import QtWidgets

    class Signal:
        def __init__(self):
            self.count = 0

        def emit(self):
            self.count += 1

    parent = SimpleNamespace(value_changed=Signal())
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    qtbot.addWidget(widget)

    slider = tune.FloatSlider(parent, layout, "Value", "value", 0.0, 10.0, steps=10)
    slider.set_value(5.0)
    assert slider.slider.value() == 5
    assert slider.value_edit.text() == "5"
    assert slider.value() == 5.0

    slider.slider.setValue(8)
    assert slider.raw_value() == 8.0
    assert parent.value_changed.count == 1

    slider.value_edit.setText("bad")
    assert slider.raw_value() == slider.slider_value()
    slider.value_edit.setText("9")
    slider.on_text_edited("9")
    assert slider.slider.value() == 9
    slider.on_editing_finished()
    assert parent.value_changed.count == 2

    slider.set_value(20)
    assert slider.value() == 10.0
    slider.set_range(0.0, 12.0)
    assert slider.value() == 12.0

    log_slider = tune.FloatSlider(parent, layout, "Log", "log", 1.0, 100.0, steps=2, scale="log")
    log_slider.set_value(10.0)
    assert log_slider.slider.value() == 1
    assert log_slider.slider_value() == pytest.approx(10.0)


def test_worker_wrappers_create_qthreads(qtbot, monkeypatch):
    monkeypatch.setattr(tune, "get_filter_data_by_method", lambda args: {"ok": True})
    monkeypatch.setattr(tune, "get_result_data_by_method", lambda args: {"ok": True})
    monkeypatch.setattr(tune, "get_reconstruction_data_by_method", lambda args: {"ok": True})

    filter_worker = tune.FilterWorker(SimpleNamespace(), request_id=1)
    result_worker = tune.ResultWorker(SimpleNamespace(), request_id=2)
    reco_worker = tune.ReconstructionWorker(SimpleNamespace(), request_id=3)

    assert filter_worker.thread is not None
    assert result_worker.worker is not None
    assert reco_worker.thread is not None


def make_window_shell():
    window = tune.InteractiveWindow.__new__(tune.InteractiveWindow)
    window._last_result_data = {"result": "data"}
    window._last_reco_data = {"reco": "data"}
    window._result_windows = {"result-window"}
    window._reco_windows = {"reco-window"}
    window._result_tabs = {"result": "tabs"}
    window._reco_tabs = {"reco": "tabs"}
    window._result_status = {"result": "status"}
    window._reco_status = {"reco": "status"}
    window._result_viewers = {"result": "viewers"}
    window._reco_viewers = {"reco": "viewers"}
    window._result_profile_plots = {"result": "plots"}
    window._reco_profile_plots = {"reco": "plots"}
    window._result_profile_rois = {"result": "profile-rois"}
    window._reco_profile_rois = {"reco": "profile-rois"}
    window._reco_region_rois = {"reco": "region-rois"}
    window._result_auto_level_windows = {"result-auto"}
    window._reco_auto_level_windows = {"reco-auto"}

    return window


def test_interactive_window_data_accessors_without_constructing_gui():
    window = make_window_shell()

    assert window._image_data("result") == {"result": "data"}
    assert window._image_data("reco") == {"reco": "data"}
    assert window._data_windows("result") == {"result-window"}
    assert window._data_windows("reco") == {"reco-window"}
    assert window._data_tabs("result") == {"result": "tabs"}
    assert window._data_tabs("reco") == {"reco": "tabs"}
    assert window._data_status("result") == {"result": "status"}
    assert window._data_status("reco") == {"reco": "status"}
    assert window._data_viewers("result") == {"result": "viewers"}
    assert window._data_viewers("reco") == {"reco": "viewers"}
    assert window._data_profile_plots("result") == {"result": "plots"}
    assert window._data_profile_plots("reco") == {"reco": "plots"}
    assert window._data_profile_rois("result") == {"result": "profile-rois"}
    assert window._data_profile_rois("reco") == {"reco": "profile-rois"}
    assert window._data_region_rois("result") == {}
    assert window._data_region_rois("reco") == {"reco": "region-rois"}
    assert window._data_auto_level_windows("result") == {"result-auto"}
    assert window._data_auto_level_windows("reco") == {"reco-auto"}


def test_interactive_window_optional_reconstruction_values():
    window = make_window_shell()

    assert window._optional_float(SimpleNamespace(text=lambda: " 1.25 ")) == 1.25
    assert window._optional_float(SimpleNamespace(text=lambda: " ")) is None

    special_minimum = SimpleNamespace(value=lambda: 0, minimum=lambda: 0, specialValueText=lambda: "auto")
    regular_minimum = SimpleNamespace(value=lambda: 0, minimum=lambda: 0, specialValueText=lambda: "")
    non_minimum = SimpleNamespace(value=lambda: 3, minimum=lambda: 0, specialValueText=lambda: "auto")
    assert window._optional_spin_value(special_minimum) is None
    assert window._optional_spin_value(regular_minimum) == 0
    assert window._optional_spin_value(non_minimum) == 3


def test_current_filtering_config_args_sets_sharpen_from_visible_curves():
    window = make_window_shell()
    args = SimpleNamespace(sharpen=False)
    window._current_args = lambda: args
    window.method_curve_buttons = {
        "tie": {"sharpened": SimpleNamespace(isChecked=lambda: False)},
        "ctf": {"sharpened": SimpleNamespace(isChecked=lambda: True)},
    }

    assert window._current_filtering_config_args() is args
    assert args.sharpen is True


def test_current_reco_display_regions_and_full_roi():
    window = make_window_shell()
    window._last_reco_args = SimpleNamespace(x_region=(0, -1, 1), y_region=(-2, 2, 1))
    x_region, y_region = window._current_reco_display_regions(np.zeros((4, 6)))

    assert x_region == (-3.0, 3.0, 1.0)
    assert y_region == (-2.0, 2.0, 1.0)

    class ROI:
        def __init__(self):
            self.blocked = False
            self.calls = []

        def blockSignals(self, blocked):
            previous = self.blocked
            self.blocked = blocked
            self.calls.append(("block", blocked))
            return previous

        def setPos(self, pos, update=False):
            self.calls.append(("pos", pos, update))

        def setSize(self, size, update=True):
            self.calls.append(("size", size, update))

    roi = ROI()
    window._set_region_roi_to_full(roi, width=0, height=3)
    assert roi.calls == [
        ("block", True),
        ("pos", [0, 0], False),
        ("size", [1, 3], True),
        ("block", False),
    ]


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

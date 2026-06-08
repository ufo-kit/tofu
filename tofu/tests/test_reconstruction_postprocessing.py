from types import SimpleNamespace

import pytest

from tofu import compress, config


class Props(SimpleNamespace):
    def __contains__(self, name):
        return hasattr(self, name)


class Task:
    def __init__(self, name):
        self.name = name
        self.props = Props(
            bits=32,
            level=0,
            rescale=True,
            tiff_jpeg2000=False,
        )


class Graph:
    def __init__(self):
        self.connections = []

    def connect_nodes(self, source, target):
        self.connections.append((source.name, target.name))


def make_args(**overrides):
    values = {
        'compress_output': True,
        'compress_bits': 16,
        'compress_compander': 'tanh',
        'compress_center': 1.5,
        'compress_delta': 0.25,
        'compress_j2k_rmse': None,
        'denoise': False,
        'denoise_compression_aware': False,
        'dry_run': False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_reconstruction_commands_expose_postprocessing_options():
    tomo = config.Params(config.TOMO_PARAMS).get_defaults()
    reco = config.Params(config.GEN_RECO_PARAMS).get_defaults()

    for args in (tomo, reco):
        assert args.compress_output is False
        assert args.denoise is False
        assert args.compress_bits == 16


def test_output_pipeline_adds_denoise_before_compand(monkeypatch):
    graph = Graph()
    source = Task('reconstruction')
    denoise = Task('denoise')
    compand = Task('compand')
    args = make_args(denoise=True)

    monkeypatch.setattr(
        compress,
        'create_denoising_pipeline',
        lambda args, processing_node=None: denoise,
    )
    monkeypatch.setattr(
        compress.TanhCompander,
        'create_ufo_task',
        lambda self, direction='forward', processing_node=None: compand,
    )

    result = compress.create_output_processing_pipeline(args, graph, source)

    assert result is compand
    assert graph.connections == [
        ('reconstruction', 'denoise'),
        ('denoise', 'compand'),
    ]


def test_output_companding_requires_explicit_center_and_delta():
    graph = Graph()
    source = Task('reconstruction')

    with pytest.raises(RuntimeError, match='--compress-center'):
        compress.create_output_processing_pipeline(
            make_args(compress_center=None),
            graph,
            source,
        )

    with pytest.raises(RuntimeError, match='--compress-delta'):
        compress.create_output_processing_pipeline(
            make_args(compress_delta=None),
            graph,
            source,
        )


def test_output_writer_uses_lossless_jpeg2000_by_default():
    writer = Task('writer')

    compress.configure_output_writer(writer, make_args())

    assert writer.props.bits == 16
    assert writer.props.rescale is False
    assert writer.props.tiff_jpeg2000 is True
    assert writer.props.level == 0


def test_compression_aware_denoising_requires_companded_output():
    args = make_args(
        compress_output=False,
        denoise=True,
        denoise_compression_aware=True,
    )

    with pytest.raises(RuntimeError, match='requires --compress-output'):
        compress.create_output_processing_pipeline(args, Graph(), Task('reconstruction'))

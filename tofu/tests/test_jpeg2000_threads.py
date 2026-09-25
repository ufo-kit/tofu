import argparse

from tofu import config, tasks, util


class Params(argparse.Namespace):
    def __contains__(self, name):
        return hasattr(self, name)


class Props:
    jpeg2000_threads = 0


class Task:
    def __init__(self):
        self.props = Props()


def test_jpeg2000_thread_arguments():
    parser = argparse.ArgumentParser()
    config.Params().add_arguments(parser)

    defaults = parser.parse_args([])
    assert defaults.jpeg2000_threads == 0
    assert defaults.output_jpeg2000_threads == 0

    args = parser.parse_args(
        ["--jpeg2000-threads", "3", "--output-jpeg2000-threads", "5"]
    )
    assert args.jpeg2000_threads == 3
    assert args.output_jpeg2000_threads == 5


def test_setup_read_task_sets_jpeg2000_threads(monkeypatch):
    task = Task()
    monkeypatch.setattr(util, "get_filenames", lambda path: [])

    util.setup_read_task(task, "input.tif", Params(jpeg2000_threads=3))

    assert task.props.path == "input.tif"
    assert task.props.jpeg2000_threads == 3


def test_get_writer_sets_jpeg2000_threads(monkeypatch):
    writer = Task()
    writer.props.append = False
    writer.props.bits = 32
    writer.props.minimum = 0
    writer.props.maximum = 0
    writer.props.rescale = False
    writer.props.bytes_per_file = 0
    writer.props.tiff_bigtiff = False
    monkeypatch.setattr(tasks, "get_task", lambda *args, **kwargs: writer)

    params = Params(
        dry_run=False,
        output="output.tif",
        output_append=False,
        output_bitdepth=32,
        output_minimum=None,
        output_maximum=None,
        output_rescale=False,
        output_bytes_per_file=1024,
        output_jpeg2000_threads=5,
    )

    assert tasks.get_writer(params) is writer
    assert writer.props.jpeg2000_threads == 5

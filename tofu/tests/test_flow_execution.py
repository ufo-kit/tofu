import pytest
from tofu.flow.execution import get_gpu_splitting_models, UfoExecutor
from tofu.flow.main import get_filled_registry
from tofu.flow.scene import UfoScene


@pytest.fixture(scope='function')
def scene():
    reg = get_filled_registry()
    scene = UfoScene(reg)

    for name in ['dummy_data', 'pad', 'null']:
        # Set nodes as scene attributes for convenience
        setattr(scene, name, scene.create_node(reg.create(name)))

    scene.create_connection(scene.dummy_data['output'][0], scene.pad['input'][0])
    scene.create_connection(scene.pad['output'][0], scene.null['input'][0])

    return scene


@pytest.fixture(scope='function')
def executor():
    return UfoExecutor()


class TestUfoExecutor:
    def test_init(self, executor):
        ...

    def test_reset(self, executor):
        assert not executor._aborted
        assert executor._schedulers == []
        assert executor.num_generated == 0

    def test_abort(self, executor):
        self.called = False

        def slot():
            self.called = True

        executor.execution_finished.connect(slot)
        executor.abort()
        assert self.called

    def test_on_processed(self, executor):
        self.num_generated = 0

        def slot():
            self.num_generated += 1

        executor.processed_signal.connect(slot)

        executor.on_processed(None)
        executor.on_processed(None)

        assert self.num_generated == executor.num_generated == 2

    def test_setup_ufo_graph(self, qtbot, scene, executor):
        graph = scene.get_simple_node_graphs()[0]
        gpus = executor._resources.get_gpu_nodes()
        assert gpus
        executor.setup_ufo_graph(graph, gpu=gpus[0], region=None,
                                 signalling_model=scene.dummy_data.model)

    def test_run_ufo_graph(self, qtbot, scene, executor):
        graph = scene.get_simple_node_graphs()[0]
        gpus = executor._resources.get_gpu_nodes()
        assert gpus
        ufo_graph = executor.setup_ufo_graph(graph, gpu=gpus[0], region=None,
                                             signalling_model=scene.dummy_data.model)
        # Run with default scheduler
        executor._run_ufo_graph(ufo_graph, False)
        # Run with fixed scheduler
        executor._run_ufo_graph(ufo_graph, True)

    # def test_check_graph(self, qtbot, scene, executor):
    #     # TODO: implement this when memory-in is implemented and there is something to test

    def test_run(self, qtbot, scene, executor):
        def on_num_inputs_changed(number):
            self.num_inputs = number

        def on_processed(number):
            self.num_processed = number

        def on_execution_started():
            self.started = True

        def on_execution_finished():
            self.finished = True

        def on_exception_occured():
            self.exception = True

        scene.dummy_data.model['number'] = 10
        graph = scene.get_simple_node_graphs()[0]

        self.num_inputs = 0
        self.num_processed = 0
        self.started = False
        self.finished = False
        self.exception = None

        executor.number_of_inputs_changed.connect(on_num_inputs_changed)
        executor.processed_signal.connect(on_processed)
        executor.execution_started.connect(on_execution_started)
        executor.execution_finished.connect(on_execution_finished)
        executor.exception_occured.connect(on_exception_occured)

        with qtbot.waitSignal(signal=executor.execution_finished, timeout=100000):
            executor.run(graph)

        assert self.num_inputs == scene.dummy_data.model['number']
        assert self.num_processed == scene.dummy_data.model['number']
        assert self.started
        assert self.finished
        assert self.exception is None

        scene.remove_node(scene.dummy_data)

        # Create a reader and point it to a nonexistent path so that it raises an exception and
        # check that this exception has been processed byt the executor
        setattr(scene, 'read', scene.create_node(scene.registry.create('read')))
        scene.create_connection(scene.read['output'][0], scene.pad['input'][0])
        # Make sure the path is nonsense
        scene.read.model['path'] = '/dfasf/fsdafsdaf/asd/asf'
        scene.read.model['number'] = 10
        graph = scene.get_simple_node_graphs()[0]
        executor.swallow_run_exceptions = True

        with qtbot.waitSignal(signal=executor.execution_finished):
            executor.run(graph)

        assert self.exception


def test_get_gpu_splitting_models(qtbot, scene, executor):
    graph = scene.get_simple_node_graphs()[0]
    assert len(get_gpu_splitting_models(graph)) == 0

    scene.clear_scene()
    scene.create_node(scene.registry.create('general_backproject'))
    graph = scene.get_simple_node_graphs()[0]
    assert len(get_gpu_splitting_models(graph)) == 1

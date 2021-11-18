import gi
import logging
import networkx as nx
gi.require_version('Ufo', '0.0')
from gi.repository import Ufo
from PyQt5.QtCore import QObject, pyqtSignal
from qtpynodeeditor import PortType
from threading import Thread
from tofu.flow.models import ARRAY_DATA_TYPE, UFO_DATA_TYPE, UfoTaskModel
from tofu.flow.util import FlowError


LOG = logging.getLogger(__name__)


class UfoExecutor(QObject):

    """Class holding GPU resources and organizing UFO graph execution."""

    number_of_inputs_changed = pyqtSignal(int)  # Number of inputs has been determined
    processed_signal = pyqtSignal(int)  # Image has been processed
    execution_started = pyqtSignal()  # Graph execution started
    execution_finished = pyqtSignal()  # Graph execution finished
    exception_occured = pyqtSignal(str)

    def __init__(self):
        super().__init__(parent=None)
        self._resources = Ufo.Resources()
        self._reset()
        # If True only log the exception and emit the signal but don't re-raise it in the executing
        # thread
        self.swallow_run_exceptions = False

    def _reset(self):
        self._aborted = False
        self._schedulers = []
        self.num_generated = 0

    def abort(self):
        LOG.debug('Execution aborted')
        try:
            self._aborted = True
            for scheduler in self._schedulers:
                scheduler.abort()
        finally:
            self.execution_finished.emit()

    def on_processed(self, ufo_task):
        self.processed_signal.emit(self.num_generated)
        self.num_generated += 1

    def setup_ufo_graph(self, graph, gpu=None, region=None, signalling_model=None):
        ufo_graph = Ufo.TaskGraph()
        ufo_tasks = {}
        for source, dest, ports in graph.edges.data():
            if hasattr(source, 'create_ufo_task') and hasattr(dest, 'create_ufo_task'):
                if dest not in ufo_tasks:
                    ufo_tasks[dest] = dest.create_ufo_task(region=region)
                if source not in ufo_tasks:
                    ufo_tasks[source] = source.create_ufo_task(region=region)
                ufo_graph.connect_nodes_full(ufo_tasks[source],
                                             ufo_tasks[dest],
                                             ports[PortType.input])
                LOG.debug(f'{source.name}->{dest.name}@{ports[PortType.input]}')
                if source == signalling_model:
                    ufo_tasks[source].connect('generated', self.on_processed)

        if gpu is not None:
            for task in ufo_tasks.values():
                if task.uses_gpu():
                    task.set_proc_node(gpu)

        return ufo_graph

    def _run_ufo_graph(self, ufo_graph, use_fixed_scheduler):
        LOG.debug(f'Executing graph, fixed scheduler: {use_fixed_scheduler}')

        try:
            scheduler = Ufo.FixedScheduler() if use_fixed_scheduler else Ufo.Scheduler()
            self._schedulers.append(scheduler)
            scheduler.set_resources(self._resources)
            scheduler.run(ufo_graph)
            LOG.info(f'Execution time: {scheduler.props.time} s')
        except Exception as e:
            # Do not continue execution of other batches
            self._aborted = True
            LOG.error(e, exc_info=True)
            self.exception_occured.emit(str(e))
            if not self.swallow_run_exceptions:
                raise e

    def check_graph(self, graph):
        """
        Check that *graph* starts with an UfoTaskModel and ends with either that or an UfoModel
        but no UfoTaskModel successor exists (there can be only one UFO path in the graph).
        """
        roots = [n for n in graph.nodes if graph.in_degree(n) == 0]
        leaves = [n for n in graph.nodes if graph.out_degree(n) == 0]

        for root in roots:
            for leave in leaves:
                for path in nx.simple_paths.all_simple_paths(graph, root, leave):
                    if not isinstance(path[0], UfoTaskModel):
                        raise FlowError('Flow must start with an UFO node')
                    ufo_ended = False
                    for (i, succ) in enumerate(path[1:]):
                        model = path[i]
                        edge_data = graph.get_edge_data(model, succ)
                        if len(edge_data) > 1:
                            # There cannot be multiple edges between nodes
                            raise FlowError('Multiple edges not allowed but detected '
                                            'between {model} and {succ}')
                        out_index = edge_data[0]['output']
                        # We don't need to check if input data type is ARRAY_DATA_TYPE because
                        # UFO_DATA_TYPE cannot be connected to ARRAY_DATA_TYPE in the scene
                        if ufo_ended:
                            # From now on only non-UFO tasks are allowed
                            if model.data_type['output'][out_index] != ARRAY_DATA_TYPE:
                                raise FlowError('After a non-UFO node cannot come another UFO node')
                        elif model.data_type['output'][out_index] != UFO_DATA_TYPE:
                            # Output is non-UFO, UFO ends here
                            ufo_ended = True

    def run(self, graph):
        self._reset()
        self.check_graph(graph)
        gpus = self._resources.get_gpu_nodes()

        num_inputs = -1
        signalling_model = None
        for model in graph.nodes:
            if graph.in_degree(model) == 0:
                if 'number' in model:
                    current = model['number']
                if current > num_inputs:
                    num_inputs = current
                    signalling_model = model

        batches = [[(None, None)]]
        gpu_splitting_model = None
        gpu_splitting_models = get_gpu_splitting_models(graph)
        if len(gpu_splitting_models) > 1:
            # There cannot be multiple splitting models
            raise FlowError('Only one gpu splitting model is allowed')
        elif gpu_splitting_models:
            gpu_splitting_model = gpu_splitting_models[0]
            batches = gpu_splitting_model.split_gpu_work(self._resources.get_gpu_nodes())

        for model in graph.nodes:
            # Reset internal model state
            if hasattr(model, 'reset_batches'):
                model.reset_batches()

        LOG.debug(f'{len(batches)} batches: {batches}')
        if signalling_model:
            self.number_of_inputs_changed.emit(len(batches) * num_inputs)
            LOG.debug(f'Number of inputs: {len(batches) * num_inputs}, defined '
                      f'by {signalling_model}')

        def execute_batches():
            self.execution_started.emit()
            try:
                for (i, parallel_batch) in enumerate(batches):
                    LOG.info(f'starting batch {i}: {parallel_batch}')
                    threads = []
                    for gpu_index, region in parallel_batch:
                        if self._aborted:
                            break
                        gpu = None if gpu_index is None else gpus[gpu_index]
                        ufo_graph = self.setup_ufo_graph(graph, gpu=gpu, region=region,
                                                         signalling_model=signalling_model)
                        t = Thread(target=self._run_ufo_graph,
                                   args=(ufo_graph,
                                         len(gpu_splitting_models) > 0))
                        t.daemon = True
                        threads.append(t)
                        t.start()
                    for t in threads:
                        t.join()
                    if self._aborted:
                        break
            except Exception as e:
                LOG.error(e, exc_info=True)
                self.exception_occured.emit(str(e))
                raise e
            finally:
                self.execution_finished.emit()

        gt = Thread(target=execute_batches)
        gt.daemon = True
        gt.start()


def get_gpu_splitting_models(graph):
    gpu_splitting_models = []
    for model in graph.nodes:
        if isinstance(model, UfoTaskModel) and model.can_split_gpu_work:
            gpu_splitting_models.append(model)

    return gpu_splitting_models

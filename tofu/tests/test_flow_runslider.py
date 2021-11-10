import pytest
from tofu.flow.runslider import RunSlider, RunSliderError


@pytest.fixture(scope='function')
def runslider(qtbot, scene):
    slider = RunSlider()
    node = scene.create_node(scene.registry.create('filter'))
    slider.setup(node.model._view._properties['cutoff'].view_item)
    qtbot.addWidget(slider)

    return slider


class TestRunSlider:
    def test_setup(self, qtbot, runslider):
        assert not runslider.setup(runslider.view_item)
        bottom = runslider.view_item.widget.validator().bottom()
        top = runslider.view_item.widget.validator().top()
        assert runslider.type == float
        assert runslider.real_minimum == bottom
        assert runslider.real_maximum == top
        assert float(runslider.min_edit.text()) == bottom
        assert float(runslider.max_edit.text()) == top
        assert float(runslider.current_edit.text()) == runslider.view_item.get()
        assert runslider.slider.value() / 100 + runslider.real_minimum == runslider.view_item.get()
        assert runslider.isEnabled()

    def test_reset(self, qtbot, runslider):
        runslider.reset()
        assert runslider.view_item is None
        assert runslider.type is None
        assert runslider.real_minimum == 0
        assert runslider.real_maximum == 100
        assert runslider.real_span == 100
        assert runslider.min_edit.text() == ''
        assert runslider.max_edit.text() == ''
        assert runslider.current_edit.text() == ''
        assert not runslider.isEnabled()

    def test_empty(self, qtbot, runslider):
        runslider.reset()
        runslider.on_min_edit_editing_finished()
        runslider.on_max_edit_editing_finished()
        runslider.on_current_edit_editing_finished()

    def test_min_edit_changed(self, qtbot, runslider):
        top = runslider.view_item.widget.validator().top()

        with pytest.raises(RunSliderError):
            runslider.min_edit.setText('asdf')
            runslider.on_min_edit_editing_finished()

        with pytest.raises(RunSliderError):
            runslider.min_edit.setText(str(top + 1))
            runslider.on_min_edit_editing_finished()

        # Current value lower than new minimum, must be updated
        value = runslider.get_real_value() + 0.1
        runslider.min_edit.setText(str(value))
        runslider.on_min_edit_editing_finished()
        assert value == runslider.get_real_value()

    def test_max_edit_changed(self, qtbot, runslider):
        bottom = runslider.view_item.widget.validator().bottom()

        with pytest.raises(RunSliderError):
            runslider.max_edit.setText('asdf')
            runslider.on_max_edit_editing_finished()

        with pytest.raises(RunSliderError):
            runslider.max_edit.setText(str(bottom - 1))
            runslider.on_max_edit_editing_finished()

        # Current value greater than new maximum, must be updated
        value = runslider.get_real_value() - 0.1
        runslider.max_edit.setText(str(value))
        runslider.on_max_edit_editing_finished()
        assert value == runslider.get_real_value()

    def test_current_edit_changed(self, qtbot, runslider):
        self.value_changed_value = None

        def on_value_changed(value):
            self.value_changed_value = value

        # Nothing changed, no update triggered
        runslider.on_current_edit_editing_finished()
        assert self.value_changed_value is None

        runslider.value_changed.connect(on_value_changed)
        current = runslider.get_real_value() + 0.1
        runslider.current_edit.setText(str(current))
        runslider.on_current_edit_editing_finished()
        assert runslider.get_real_value() == current

        runslider.current_edit.setText('asf')
        with pytest.raises(RunSliderError):
            runslider.on_current_edit_editing_finished()

    def test_int(self, qtbot, runslider, scene):
        node = scene.create_node(scene.registry.create('read'))
        runslider.setup(node.model._view._properties['y'].view_item)
        assert runslider.type == int

        runslider.min_edit.setText('1')
        runslider.on_min_edit_editing_finished()
        runslider.max_edit.setText('10')
        runslider.on_max_edit_editing_finished()
        runslider.slider.setValue(50)
        assert type(runslider.get_real_value()) == int
        assert runslider.get_real_value() == 5

        runslider.current_edit.setText('7')
        runslider.on_current_edit_editing_finished()
        assert type(runslider.get_real_value()) == int
        assert runslider.get_real_value() == 7

        # Maximum smaller than current -> update current
        runslider.max_edit.setText('5')
        runslider.on_max_edit_editing_finished()
        assert type(runslider.get_real_value()) == int
        assert runslider.get_real_value() == 5

        # Minimum greater than current -> update current
        runslider.max_edit.setText('10')
        runslider.on_max_edit_editing_finished()
        runslider.min_edit.setText('8')
        runslider.on_min_edit_editing_finished()
        assert type(runslider.get_real_value()) == int
        assert runslider.get_real_value() == 8

    def test_range(self, qtbot, scene):
        runslider = RunSlider()
        qtbot.addWidget(runslider)
        node = scene.create_node(scene.registry.create('general_backproject'))
        node.model['center-position-x'] = [1, 2, 3]
        assert not runslider.setup(node.model._view._properties['center-position-x'].view_item)
        assert runslider.view_item is None

        node.model['center-position-x'] = [1]
        assert runslider.setup(node.model._view._properties['center-position-x'].view_item)
        assert runslider.view_item == node.model._view._properties['center-position-x'].view_item
        assert type(runslider.get_real_value()) == float
        assert runslider.get_real_value() == 1

        runslider.current_edit.setText('1.1')
        runslider.on_current_edit_editing_finished()
        assert node.model['center-position-x'] == [runslider.get_real_value()]

    def test_links(self, qtbot, link_model, nodes):
        runslider = RunSlider()
        qtbot.addWidget(runslider)
        read = nodes['read']
        read_2 = nodes['read_2']
        runslider.setup(read.model._view._properties['number'].view_item)

        link_model.add_item(read, read.model, 'number', -1, -1)
        link_model.add_item(read_2, read_2.model, 'number', 0, -1)
        runslider.current_edit.setText('123')
        runslider.on_current_edit_editing_finished()
        assert read_2.model['number'] == 123

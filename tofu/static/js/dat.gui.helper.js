guiControls = new function() {
	this.gray_min = -1;
	this.gray_max = -1;
	this.steps = -1;
	this.number_slices = -1;
	this.render_size = 8;
	this.render_canvas_size = 7;
	this.row_col = -1 + "x" + -1;
	this.absorption_mode = -1;
	this.opacity_factor = -1;
	this.color_factor = -1;
	this.x_min = -1;
	this.x_max = -1;
	this.y_min = -1;
	this.y_max = -1;
	this.z_min = -1;
	this.z_max = -1;
	this.colormap = 13;
	this.thresholding = 4;

	this.auto_steps = -1;
};

var UpdateGUI = function(config) {
	guiControls.number_slices = config["slices_range"][1];
	guiControls.gray_min = config["gray_min"];
	guiControls.gray_max = config["gray_max"];
	guiControls.row_col = config["row_col"][0] + "x" + config["row_col"][1];
	guiControls.steps = config["steps"];
	guiControls.absorption_mode = config["absorption_mode"];
	guiControls.opacity_factor = config["opacity_factor"];
	guiControls.color_factor = config["color_factor"];
	guiControls.x_min = config["x_min"];
	guiControls.x_max = config["x_max"];
	guiControls.y_min = config["y_min"];
	guiControls.y_max = config["y_max"];
	guiControls.z_min = config["z_min"];
	guiControls.z_max = config["z_max"];
	guiControls.auto_steps = config["auto_steps"];

};

var InitGUI = function(config, rcl2) {
	UpdateGUI( config );

	var gui = new dat.GUI();

	var x_min_controller = gui.add(guiControls, 'x_min', 0, 1, 0.1).listen();
	x_min_controller.onChange(function(value) {
		rcl2.setGeometryMinX(value);
	});

	var x_max_controller = gui.add(guiControls, 'x_max', 0, 1, 0.1).listen();
	x_max_controller.onChange(function(value) {
		rcl2.setGeometryMaxX(value);
	});

	var y_min_controller = gui.add(guiControls, 'y_min', 0, 1, 0.1).listen();
	y_min_controller.onChange(function(value) {
		rcl2.setGeometryMinY(value);
	});

	var y_max_controller = gui.add(guiControls, 'y_max', 0, 1, 0.1).listen();
	y_max_controller.onChange(function(value) {
		rcl2.setGeometryMaxY(value);
	});

	var z_min_controller = gui.add(guiControls, 'z_min', 0, 1, 0.1).listen();
	z_min_controller.onChange(function(value) {
		rcl2.setGeometryMinZ(value);
	});

	var z_max_controller = gui.add(guiControls, 'z_max', 0, 1, 0.1).listen();
	z_max_controller.onChange(function(value) {
		rcl2.setGeometryMaxZ(value);
	});

	steps_controller = gui.add(guiControls, 'steps', 10, rcl2.getMaxStepsNumber(), 1).listen();
	steps_controller.onFinishChange(function(value) {
		rcl2.setSteps(value);
	});

	var number_slices_controller = gui.add(guiControls, 'number_slices', 1, 2048, 1).listen();
	number_slices_controller.onFinishChange(function(value) {
		rcl2.setSlicesRange(0, value);
	});

	var auto_steps_controller = gui.add(guiControls, 'auto_steps').listen();
	auto_steps_controller.onChange(function(value) {
		rcl2.setAutoStepsOn(value);
	});

	var absorbtion_mode_controller = gui.add(guiControls, 'absorption_mode', {"MIPS": 0, "X-ray": 1, "Maximum projection intensivity": 2}).listen();
	absorbtion_mode_controller.onChange(function(value) {
		rcl2.setAbsorptionMode(value);
	});

	var color_factor_controller = gui.add(guiControls, 'color_factor', 0, 20, 0.1).listen();
	color_factor_controller.onChange(function(value) {
		rcl2.setColorFactor(value);
	});

	var opacity_factor_controller = gui.add(guiControls, 'opacity_factor', 0, 50, 0.1).listen();
	opacity_factor_controller.onChange(function(value) {
		rcl2.setOpacityFactor(value);
	});

	var gray_min_controller = gui.add(guiControls, 'gray_min', 0, 1, 0.1).listen();
	gray_min_controller.onChange(function(value) {
		rcl2.setGrayMinValue(value);
	});

	var gray_max_controller = gui.add(guiControls, 'gray_max', 0, 1, 0.1).listen();
	gray_max_controller.onChange(function(value) {
		rcl2.setGrayMaxValue(value);
	});

	var render_size_controller = gui.add(guiControls, 'render_size', {"128": 0, "256": 1, "512": 2, "768": 3, "1024": 4, "2048": 5, "4096": 6, "*": 7, "default": 8}, 8);
	render_size_controller.onFinishChange(function(value) {
		switch(value) {
			case "0": {
				rcl2.setRenderSize(128, 128);

			}; break;			
			case "1": {
				rcl2.setRenderSize(256, 256);

			}; break;			
			case "2": {
				rcl2.setRenderSize(512, 512);

			}; break;			
			case "3": {
				rcl2.setRenderSize(768, 768);

			}; break;
			case "4": {
				rcl2.setRenderSize(1024, 1024);

			}; break;
			case "5": {
				rcl2.setRenderSize(2048, 2048);

			}; break;
			case "6": {
				rcl2.setRenderSize(4096, 4096);

			}; break;
			case "7": {
				rcl2.setRenderSize('*', '*');

			}; break;
			case "8": {

			}; break;
		}
	});

	var render_canvas_size_controller = gui.add(guiControls, 'render_canvas_size', {"256": 0, "512": 1, "768": 2, "1024": 3, "2048": 4, "4096": 5, "*": 6, "default": 7}, 7);
	render_canvas_size_controller.onFinishChange(function(value) {
		switch(value) {
			case "0": {
				rcl2.setRenderCanvasSize(256, 256);

			}; break;			
			case "1": {
				rcl2.setRenderCanvasSize(512, 512);

			}; break;			
			case "2": {
				rcl2.setRenderCanvasSize(768, 768);

			}; break;
			case "3": {
				rcl2.setRenderCanvasSize(1024, 1024);

			}; break;
			case "4": {
				rcl2.setRenderCanvasSize(2048, 2048);

			}; break;
			case "5": {
				rcl2.setRenderCanvasSize(4096, 4096);

			}; break;
			case "6": {
				rcl2.setRenderCanvasSize('*', '*');

			}; break;
			case "7": {

			}; break;
		}
	});

	var row_col_controller = gui.add(guiControls, 'row_col').listen();
	row_col_controller.onFinishChange(function(value) {
		rcl2.setRowCol(value.split('x')[0], value.split('x')[1]);
	});

	var transfer_function_controller = gui.add(guiControls, 'colormap', {
		"parula": 0,
		"jet": 1,
		"hsv": 2,
		"hot": 3,
		"cool": 4,
		"spring": 5,
		"summer": 6,
		"autumn": 7,
		"winter": 8,
		"gray": 9,
		"bone": 10,
		"copper": 11,
		"pink": 12,
		"default": 13,

	});

	transfer_function_controller.onChange(function(value) {
		switch(value) {
			case "0": {
				rcl2.setTransferFunctionByColors([
				    {"pos": 0, "color": "#352A87"},
				    {"pos": 1, "color": "#F9FB0E"}
				]);
			} break;

			case "1": {
				rcl2.setTransferFunctionByColors([
				    {"pos": 0,   "color": "#0000ff"},
				    {"pos": 1,   "color": "#ff0000"}
				]);
			} break;

			case "2": {
				rcl2.setTransferFunctionByColors([
				    {"pos": 0,    "color": "#ff0000"},
				    {"pos": 0.25, "color": "#00ff00"},
				    {"pos": 0.5,  "color": "#0000ff"},
				    {"pos": 1,    "color": "#ff0000"}
				]);
			} break;

			case "3": {
				rcl2.setTransferFunctionByColors([
				    {"pos": 0,    "color": "#000000"},
				    {"pos": 0.25, "color": "#ff0000"},
				    {"pos": 0.5,  "color": "#ffff00"},
				    {"pos": 1,    "color": "#ffffff"}
				]);
			} break;

			case "4": {
				rcl2.setTransferFunctionByColors([
				    {"pos": 0,    "color": "#00ffff"},
				    {"pos": 1,    "color": "#E405E4"}
				]);
			} break;

			case "5": {
				rcl2.setTransferFunctionByColors([
				    {"pos": 0,    "color": "#E405E4"},
				    {"pos": 1,    "color": "#FFFF00"}
				]);
			} break;

			case "6": {
				rcl2.setTransferFunctionByColors([
				    {"pos": 0,    "color": "#008066"},
				    {"pos": 1,    "color": "#FFFF66"}
				]);
			} break;

			case "7": {
				rcl2.setTransferFunctionByColors([
				    {"pos": 0,    "color": "#ff0000"},
				    {"pos": 1,    "color": "#ffff00"}
				]);
			} break;

			case "8": {
				rcl2.setTransferFunctionByColors([
				    {"pos": 0,    "color": "#0000ff"},
				    {"pos": 1,    "color": "#00ffff"}
				]);
			} break;

			case "9": {
				rcl2.setTransferFunctionByColors([
				    {"pos": 0,    "color": "#000000"},
				    {"pos": 1,    "color": "#ffffff"}
				]);
			} break;

			case "10": {
				rcl2.setTransferFunctionByColors([
				    {"pos": 0,    "color": "#000000"},
				    {"pos": 0.5,  "color": "#788798"},
				    {"pos": 1,    "color": "#ffffff"}
				]);
			} break;

			case "11": {
				rcl2.setTransferFunctionByColors([
				    {"pos": 0,    "color": "#000000"},
				    {"pos": 1,    "color": "#FFC77F"}
				]);
			} break;

			case "12": {
				rcl2.setTransferFunctionByColors([
				    {"pos": 0,    "color": "#000000"},
				    {"pos": 0.25, "color": "#A76C6C"},
				    {"pos": 0.5,  "color": "#E8E8B4"},
				    {"pos": 1,    "color": "#ffffff"}
				]);
			} break;

			case "13": {
			} break;
		}

		return value;

	});

	var thresholding_controller = gui.add(guiControls, 'thresholding', {
		"otsu": 0, 
		"isodata": 1,
		"yen": 2,
		"li": 3,
		"no": 4,

	});

	thresholding_controller.onChange(function(value) {
		switch(value) {
			case "0": {
				rcl2.applyThresholding("otsu");
			} break;

			case "1": {
				rcl2.applyThresholding("isodata");
			} break;

			case "2": {
				rcl2.applyThresholding("yen");
			} break;

			case "3": {
				rcl2.applyThresholding("li");
			} break;

			case "4": {
			} break;
		}

		return value;

	});

};
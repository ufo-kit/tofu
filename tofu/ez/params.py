# This file is used to share params as a global variable
import yaml
from collections import OrderedDict

#TODO Make good structure to store parameters
# similar to tofu? and
# use tofu's structure for existing reco params

params = {}

PARAMS = OrderedDict()
PARAMS['ezmview'] = {
    'num_sets': {
        'default': None,
        'type': float,
        'help': "Axis position"},
    'indir': {
        'default': False,
        'help': "Reconstruct without writing data",
        'action': 'store_true'}}


def save_parameters(params, file_path):
    file_out = open(file_path, 'w')
    yaml.dump(params, file_out)
    print("Parameters file saved at: " + str(file_path))



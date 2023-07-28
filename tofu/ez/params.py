# This file is used to share params as a global variable
import yaml
import os
from collections import OrderedDict
from tofu.util import restrict_value

params = {}

def save_parameters(params, file_path):
    file_out = open(file_path, 'w')
    yaml.dump(params, file_out)
    print("Parameters file saved at: " + str(file_path))


EZVARS = OrderedDict()

EZVARS['inout'] = {
    'input-dir': {
        'ezdefault': os.path.join(os.path.expanduser('~'),""), 
        'type': str, 
        'help': "TODO"},
    'output-dir': {
        'ezdefault': os.path.join(os.path.expanduser('~'),"rec"), 
        'type': str, 
        'help': "TODO"},
    'tmp-dir' : {
        'ezdefault': os.path.join(os.path.expanduser('~'),"tmp-ezufo"),
        'type': str, 
        'help': "TODO"},
    'darks-dir': {
        'ezdefault': "darks",
        'type': str, 
        'help': "TODO"},
    'flats-dir': {
        'ezdefault': "flats",
        'type': str, 
        'help': "TODO"},
    'tomo-dir': {
        'ezdefault': "tomo",
        'type': str, 
        'help': "TODO"},
    'flats2-dir': {
        'ezdefault': "flats2",
        'type': str, 
        'help': "TODO"},
    'bigtiff-output': {
        'ezdefault': False,
        'type': bool, 
        'help': "TODO"},
    'input_ROI': {
        'ezdefault': False,
        'type': bool, 
        'help': "TODO"},
    'clip_hist': {
        'ezdefault': False,
        'type': bool, 
        'help': "TODO"},
    'preprocess': {
        'ezdefault': False, 
        'type': bool, 
        'help': "TODO"},
    'preprocess-command': {
        'ezdefault': "remove-outliers size=3 threshold=500 sign=1", 
        'type': str, 
        'help': "TODO"},
    'output-ROI': {
        'ezdefault': False,
        'type': bool, 
        'help': "TODO"},
    'output-x': {
        'ezdefault': 0,
        'type': restrict_value((0,None),dtype=int), 
        'help': "Crop slices: x"},
    'output-width': {
        'ezdefault': 0,
        'type': restrict_value((0,None),dtype=int), 
        'help': "Crop slices: width"},
    'output-y': {
        'ezdefault': 0,
        'type': restrict_value((0,None),dtype=int), 
        'help': "Crop slices: y"},
    'output-height': {
        'ezdefault': 0,
        'type': restrict_value((0,None),dtype=int), 
        'help': "Crop slices: height"},
    'dryrun': {
        'ezdefault': False, 
        'type': bool, 
        'help': "TODO"},
    'save-params': {
        'ezdefault': True, 
        'type': bool, 
        'help': "TODO"},
    'keep-tmp': {
        'ezdefault': False, 
        'type': bool, 
        'help': "TODO"},
    'open-viewer': {
        'ezdefault': False, 
        'type': bool, 
        'help': "TODO"},
    'shared-flatsdarks': {
        'ezdefault': False, 
        'type': bool, 
        'help': "TODO"},
    'path2-shared-darks': {
        'ezdefault': "Absolute path to darks", 
        'type': str, 
        'help': "TODO"},
    'path2-shared-flats': {
        'ezdefault': "Absolute path to flats", 
        'type': str, 
        'help': "TODO"},
    'shared-flats-after': {
        'ezdefault': False, 
        'type': bool, 
        'help': "TODO"},
    'path2-shared-flats2': {
        'ezdefault': "Absolute path to flats2", 
        'type': str, 
        'help': "TODO"},
    'shared-df-used': {
        'ezdefault': False,
        'type': bool,
        'help': "Internal variable; must be set to True once "
                "shared flats/darks were used in the recontruction pipeline"},
}

EZVARS['COR'] = {
    'search-method': {
        'ezdefault': 1,
        'type': int, 
        'help': "TODO"},
    'search-interval': {
        'ezdefault': "1010,1030,0.5",
        'type': str, 
        'help': "TODO"},
    'patch-size': {
        'ezdefault': 256,
        'type': restrict_value((0,None),dtype=int), 
        'help': "Size of reconstructed patch [pixel]"},
    'search-row': {
        'ezdefault': 100,
        'type': restrict_value((0,None), dtype=int), 
        'help': "Search in slice from row number"},
    'min-std-apply-pr': {
        'ezdefault': False,
        'type': bool,
        'help': "Will apply phase retreival but only while estimating the axis"},
    'user-defined-ax': {
        'ezdefault': 0.0,
        'type': restrict_value((0,None),dtype=float),
        'help': "Axis is in column No [pixel]"},
    'user-defined-dax': {
        'ezdefault': 0.0,
        'type': float, 
        'help': "TODO"},
}

EZVARS['retrieve-phase']= {
    'apply-pr': {
        'default': False,
        'ezdefault': False,
        'type': bool,
        'help': "Applies phase retrieval if checked"}
}

EZVARS['filters'] = {
    'rm_spots': {
        'ezdefault': False,
        'type': bool, 
        'help': "TODO-G"},
    'spot-threshold': {
        'ezdefault': 1000,
        'type': restrict_value((0,None), dtype=float),
        'help': "TODO-G"}
}

EZVARS['RR'] = {
    'enable-RR': {
        'ezdefault': False,
        'type': bool, 
        'help': "TODO-G"},
    'use-ufo': {
        'ezdefault': True,
        'type': bool, 
        'help': "TODO-G"},
    'ufo-2d': {
        'ezdefault': False, 
        'type': bool, 
        'help': "TODO"},
    'sx': {
        'ezdefault': 3,
        'type': restrict_value((0,None),dtype=int), 
        'help': "ufo ring-removal sigma horizontal (try 3..31)"},
    'sy': {
        'ezdefault': 1,
        'type': restrict_value((0,None),dtype=int), 
        'help': "ufo ring-removal sigma vertical (try 1..5)"},
    'spy-narrow-window': {
        'ezdefault': 21,
        'type': restrict_value((0,None),dtype=int), 
        'help': "window size"},
    'spy-rm-wide': {
        'ezdefault': False,
        'type': bool, 
        'help': "TODO"},
    'spy-wide-window': {
        'ezdefault': 91, 
        'type': restrict_value((0,None),dtype=int), 
        'help': "wind"},
    'spy-wide-SNR': {
        'ezdefault': 3, 
        'type': restrict_value((0,None),dtype=int), 
        'help': "SNR"},
}

EZVARS['flat-correction'] = {
    'smart-ffc': {
        'ezdefault': False,
        'type': bool, 
        'help': "TODO"},
    'smart-ffc-method': {
        'ezdefault': "eigen",
        'type': str, 
        'help': "TODO"},
    'eigen-pco-reps': {
        'ezdefault': 4,
        'type': restrict_value((0,None),dtype=int), 
        'help': "Flat Field Correction: Eigen PCO Repetitions"},
    'eigen-pco-downsample': {
        'ezdefault': 2,
        'type': restrict_value((0,None),dtype=int), 
        'help': "Flat Field Correction: Eigen PCO Downsample"},
    'downsample': {
        'ezdefault': 4,
        'type': restrict_value((0,None),dtype=int), 
        'help': "Flat Field Correction: Downsample"},
    'dark-scale': {
        'ezdefault': 1.0,
        'type': float, 
        'help': "Scaling dark"}, #(?) has the same name in SECTION
    'flat-scale': {
        'ezdefault': 1.0,
        'type': float, 
        'help': "Scaling falt"}, #(?) has the same name in SECTION
}

#TODO ADD CHECKING NLMDN SETTINGS
EZVARS['nlmdn'] = {
    'do-after-reco': {
        'ezdefault': False,
        'type': bool, 
        'help': "TODO"},
    'input-dir': {
        'ezdefault': os.getcwd(),
        'type': str, 
        'help': "TODO"},
    'input-is-1file': {
        'ezdefault': False, 
        'type': bool, 
        'help': "TODO"},
    'output_pattern': {
        'ezdefault': os.getcwd() + '-nlmfilt',
        'type': str, 
        'help': "TODO"},
    'bigtiff_output': {
        'ezdefault': False,
        'type': bool, 
        'help': "TODO"},
    'search-radius': {
        'ezdefault': 10,
        'type': int, 
        'help': "TODO"},
    'patch-radius': {
        'ezdefault': 3,
        'type': int, 
        'help': "TODO"},
    'h': {
        'ezdefault': 0.0,
        'type': float, 
        'help': "TODO"},
    'sigma': {
        'ezdefault': 0.0,
        'type': float, 
        'help': "TODO"},
    'window': {
        'ezdefault': 0.0,
        'type': float, 
        'help': "TODO"},
    'fast': {
        'ezdefault': True,
        'type': bool, 
        'help': "TODO"},
    'estimate-sigma': {
        'ezdefault': False,
        'type': bool, 
        'help': "TODO"},
    'dryrun': {
        'ezdefault': False,
        'type': bool, 
        'help': "TODO"},
}


EZVARS['advanced'] = {
    'more-reco-params': {
        'ezdefault': False,
        'type': bool, 
        'help': "TODO"},
    'parameter-type': {
        'ezdefault': "", 
        'type': str, 
        'help': "TODO"},
    'enable-optimization': {
        'ezdefault': False,
        'type': bool,
        'help': "TODO"
    }   
}
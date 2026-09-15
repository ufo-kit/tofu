"""
Created on Apr 5, 2018

@author: gasilos
"""

import os, h5py, glob
from tofu.ez.params import EZVARS, EZVARS_prep
from tofu.ez.Helpers.hereon_h5 import h5log2params, get_beamline_id

VALID_EXTS = ['.tif', '.tiff', '.edf']

class WalkCTdirs:
    """
    Usage:
    First findCTdirs is called to creates list of paths to "potential" CT directories
    "Potential" CT directory is any directory containing subdirectory "tomo" or an h5 file
    if h5 file is found function creates a standard directory structure with flats/darks/tomo subdirectories
    which are populated with symbolic links to respective tif files stored in a standard P05/P07 file sequence
    Secondly a check can be performed to determine whether CT data is consistent or not
    That is kind of optional. Back when python argparser didn't support regex well I used to check that
    flats/darks/tomo directory only contains tif files.
    TODO: a *.tif must be added everywhere in command formatters?
    Any other kind of tests and checks cna be performed at this step.
    Step three: function SortGoodBad creates
    a list with "good" CT directries with are described by a tuple of length 3
    (path, type, hereon?) (str, int, bool)
    TODO: create a class to describe a CT set instead of having a list
    then an array of CTsets can contain all information about it, e.g.
    type, origin, dimensions, experimental params such as pixel size and propagation distance, etc.
    Note: fdt_names variable stores flats/darks/tomo directory names
    """

    def __init__(self, inpath, fdt_names, verb=True):
        self.lvl0 = os.path.abspath(inpath)
        self.ctdirs = []
        self.types = []
        self.ctsets = []
        self.typ = []
        self.total = 0
        self.good = 0
        self.huct = []
        self.verb = verb
        self._fdt_names = fdt_names
        self.common_flats = EZVARS['inout']['path2-shared-flats']['value']
        self.common_darks = EZVARS['inout']['path2-shared-darks']['value']
        self.common_flats2 = EZVARS['inout']['path2-shared-flats2']['value']
        self.use_common_flats2 = EZVARS['inout']['shared-flats-after']['value']

    def print_tree(self):
        print("We start in {}".format(self.lvl0))

    def findCTdirs(self):
        """
        Walks directories rooted at "Input Directory" location
        Appends their absolute path to ctdir if they contain a directory with same name as "tomo" entry in GUI
        """
        print(f" ====> Walking over data in {self.lvl0}")
        for root, dirs, files in os.walk(self.lvl0):
            h5filelist = glob.glob(os.path.join(root,'*.h5')) #perphaps root contains h5 file?
            fdt = 0
            for dname in dirs: # is any of the subdirectories named like a dir with CT projections?
                if dname == self._fdt_names[2]:
                   fdt = 1
                   dirs[:] = [] # once tomo dir is found we stop iterating over subdirectories
            # now there can be three options:
            if h5filelist:
                h5filename = h5filelist[0]
                if fdt: # (1) this is preprocessed hereon data set saved as fdt subdirectories
                    self.ctdirs.append(root)
                    h5log = h5py.File(h5filename,'r')
                    h5log2params(h5log, root)
                    h5log.close()
                    self.huct.append(1)
                    print(f"Found preprocessed Hereon CT sequence in {root}, h5file is {h5filename}")
                else: # (2) this is a raw hereon data set
                    self.ctdirs.append(self.make_symlink_ctdir(root, h5filename))
                    self.huct.append(1)
                    print(f"Found raw Hereon CT sequence in {root} with h5 file {h5filename}")
            elif fdt: # (3) this is an ordinary fdt structure
                self.ctdirs.append(root)
                self.huct.append(0)
                print(f"Found standard CT set with standard flats/dars/tomo in {root}")
        self.ctdirs = list(set(self.ctdirs))
        self.ctdirs.sort()
        if sum(self.huct) > 0 and (not EZVARS_prep['prepro']['extended_prepro']['value']):
            # we are working with raw hereon data structure hence
            # we reset input directory to the temporary directory which
            # contains symbolic links to images. Symbolic links
            # are ordered as a standard flats/darks/tomo structure
            self.lvl0 = os.path.join(EZVARS['inout']['tmp-dir']['value'],'links2images')


    def make_symlink_ctdir(self, ctset, h5fname):
        """
        creates ufo-like CT directory structure populated with symlinks to P05/P07 files
        """
        import numpy as np
        h5log = h5py.File(os.path.join(ctset,h5fname),'r')
        tmplvl0dir = os.path.join(EZVARS['inout']['tmp-dir']['value'],'links2images')
        if not os.path.exists(tmplvl0dir):
            os.mkdir(tmplvl0dir)
        symname = os.path.dirname(os.path.join(tmplvl0dir, ctset[len(self.lvl0)+1:]))
        if symname != tmplvl0dir:
            os.mkdir(symname)
        tmpdar = os.path.join(symname, EZVARS['inout']['darks-dir']['value'])
        tmpref = os.path.join(symname, EZVARS['inout']['flats-dir']['value'])
        tmpimg = os.path.join(symname, EZVARS['inout']['tomo-dir']['value'])
        os.mkdir(tmpdar)
        os.mkdir(tmpref)
        os.mkdir(tmpimg)
        bid = get_beamline_id(h5log)
        for i, imk in enumerate(h5log['entry']['scan']['data']['image_key']['value']):
            imname = h5log['entry']['scan']['data']['image_file']['value'][i].decode()
            if bid == 5:
                imname = h5log['entry']['scan']['data']['image_file']['value'][i].decode()[1:]
            iind = f"{i:05}"
            if imk == 2:
                os.system(f"ln -s {os.path.join(ctset, imname)} \
                                    {os.path.join(tmpdar,'dar_'+iind+'.tif')}")
            elif imk == 1:
                os.system(f"ln -s {os.path.join(ctset, imname)} \
                                    {os.path.join(tmpref,'ref_'+iind+'.tif')}")
            elif imk == 0:
                os.system(f"ln -s {os.path.join(ctset, imname)} \
                                    {os.path.join(tmpimg,'img_'+iind+'.tif')}")
        # Extract necessary hereon data
        h5log2params(h5log, symname)
        h5log.close()
        return symname


    def checkCTdirs(self):
        """
        Determine whether directory is of type 3 or type 4 and store in self.typ with index corresponding to ctdir
        Type3: Has flats, darks and not flats2 -- or flats==flats2
        Type4: Has flats, darks and flats2
        """
        for ctdir in self.ctdirs:
            # flats/darks and no flats2 or flats2==flats -> type 3
            if (
                os.path.exists(os.path.join(ctdir, self._fdt_names[1]))
                and os.path.exists(os.path.join(ctdir, self._fdt_names[0]))
                and (
                    not os.path.exists(os.path.join(ctdir, self._fdt_names[3]))
                    or self._fdt_names[1] == self._fdt_names[3]
                )
            ):
                self.typ.append(3)
            # flats/darks/flats2 -> type4
            elif (
                os.path.exists(os.path.join(ctdir, self._fdt_names[1]))
                and os.path.exists(os.path.join(ctdir, self._fdt_names[0]))
                and os.path.exists(os.path.join(ctdir, self._fdt_names[3]))
            ):
                self.typ.append(4)
            else:
                print(os.path.basename(ctdir))
                self.typ.append(0)

    def checkcommonfdt(self):
        """
        Verifies that paths to directories specified by common_flats, common_darks, and common_flats2 exist
        :return: True if directories exist, False if they do not exist
        """
        for ctdir in self.ctdirs:
            if self.use_common_flats2 is True:
                self.typ.append(4)
            elif self.use_common_flats2 is False:
                self.typ.append(3)

        if self.use_common_flats2 is True:
            if (
                os.path.exists(self.common_flats)
                and os.path.exists(self.common_darks)
                and os.path.exists(self.common_flats2)
            ):
                return True
        elif self.use_common_flats2 is False:
            if (os.path.exists(self.common_flats)
                    and os.path.exists(self.common_darks)):
                return True
        return False

    def checkcommonfdtFiles(self):
        """
        Verifies that directories of tomo and common flats/darks/flats contain only .tif files
        :return: True if directories exist, False if they do not exist
        """
        for i, ctdir in enumerate(self.ctdirs):
            ctdir_tomo_path = os.path.join(ctdir, self._fdt_names[2])
            if not self._checktifs(ctdir_tomo_path):
                print("Invalid files found in " + str(ctdir_tomo_path))
                self.typ[i] = 0
                return False
            if not self._checktifs(self.common_flats):
                print("Invalid files found in " + str(self.common_flats))
                return False
            if not self._checktifs(self.common_darks):
                print("Invalid files found in " + str(self.common_darks))
                return False
            if self.use_common_flats2 and not self._checktifs(self.common_flats2):
                print("Invalid files found in " + str(self.common_flats2))
                return False
            return True

    def checkCTfiles(self):
        """
        Checks whether each ctdir is of type 3 or 4 by comparing index of self.typ[] to corresponding index of ctdir[]
        Then for each directory of type 3 or 4 it checks sub-directories contain only .tif files
        If it contains invalid data then typ[] is set to 0 for corresponding index location
        """
        for i, ctdir in enumerate(self.ctdirs):
            if (
                self.typ[i] == 3
                and self._checktifs(os.path.join(ctdir, self._fdt_names[1]))
                and self._checktifs(os.path.join(ctdir, self._fdt_names[0]))
                and self._checktifs(os.path.join(ctdir, self._fdt_names[2]))
            ):
                continue
            elif (
                self.typ[i] == 4
                and self._checktifs(os.path.join(ctdir, self._fdt_names[1]))
                and self._checktifs(os.path.join(ctdir, self._fdt_names[0]))
                and self._checktifs(os.path.join(ctdir, self._fdt_names[2]))
                and self._checktifs(os.path.join(ctdir, self._fdt_names[3]))
            ):
                continue
            elif self.huct:
                continue
            else:
                self.typ[i] = 0

    def _checktifs(self, tmpath):
        """
        Checks each whether item in directory tmppath is a supported file
        :param tmpath: Path to directory
        :return: 0 if invalid item found in directory - 1 if no invalid items found in directory
        """
        for i in os.listdir(tmpath):
            if os.path.isdir(i):
                print(f"Directory {tmpath} contains a subdirectory")
                return 0
            if os.path.splitext(i)[1] not in VALID_EXTS:
                print(f"Directory {tmpath} has files which are not supported images or containers")
                return 0
        return 1

    def sortbadgoodsets(self):
        """
        Reduces type of all directories to either
        Good with flats 2 (4) or good without flats2 (3) or bad (<0)
        """
        self.total = len(self.ctdirs)
        self.ctsets = sorted(zip(self.ctdirs, self.typ, self.huct), key=lambda s: s[0])
        self.total = len(self.ctsets)
        self.good = [int(y) > 2 for x, y, z  in self.ctsets].count(True)

        #print('sorting good bad')
        print(f"This is what was found in the input directory {self.lvl0}")
        tmp = len(self.lvl0)
        if self.verb:
            print("Total CT-like dirs {}, good CT dirs {}".format(self.total, self.good))
            print("{:>20}\t{}".format("Path to CT set", "Type: 0 bad, 3 no flats2, 4 with flats2"))
            for ctdir in self.ctsets:
                msg1 = "."+ctdir[0][tmp:]
                #msg1 = os.path.basename(ctdir[0])
                # if msg1 == "":
                #     msg1 = "."
                print("{:>20}\t{}".format(msg1, ctdir[1]))

        # keep paths to directories with good ct data only:
        self.ctsets = [q for q in self.ctsets if int(q[1] > 0)]

        #print('Finished sorting goodbad')

    def Getlvl0(self):
        return self.lvl0


def substitute_shared_flatsdarks() -> dict[str, str]:
    """
    Return a dictionary with structure {"flats": "/path/to/shared/flats"}
    which respects EZVARS settings
    """
    substitutes = {}
    if EZVARS['inout']['shared-flatsdarks']['value']:
        for type in ['darks', 'flats', 'flats2']:
            if type == 'flats2' and not EZVARS['inout']['shared-flats-after']['value']:
                continue
            key = f'path2-shared-{type}'
            path = EZVARS['inout'][key]['value']
            if not os.path.exists(path):
                print(f"Shared {type} not found: {path}")
                continue
            name = EZVARS['inout'][f'{type}-dir']['value']
            substitutes[name] = path

    return substitutes

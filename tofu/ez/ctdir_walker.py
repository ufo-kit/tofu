'''
Created on Apr 5, 2018

@author: gasilos
'''

import glob
import os


class WalkCTdirs():
    """
    Walks in the directory structure and creates list of paths to CT folders
    Determines flats before/after
    and checks that folders contain only tiff files
    fdt_names = flats/darks/tomo directory names
    """

    def __init__(self, inpath, fdt_names, args, verb=True):
        self.lvl0 = os.path.abspath(inpath)
        self.ctdirs = []
        self.types = []
        self.ctsets = []
        self.typ = []
        self.total = 0 
        self.good = 0
        self.verb = verb
        self._fdt_names = fdt_names
        self.common_flats = args.common_flats
        self.common_darks = args.common_darks
        self.common_flats2 = args.common_flats2
        self.use_common_flats2 = args.use_common_flats2
    
    def print_tree(self):
        print('We start in {}'.format(self.lvl0))
        
    def findCTdirs(self):
        """
        Walks directories rooted at "Input Directory" location
        Appends their absolute path to ctdir if they contain a directory with same name as "tomo" entry in GUI
        """
        for root, dirs, files in os.walk(self.lvl0):
            for name in dirs:
                if name == self._fdt_names[2]:
                    self.ctdirs.append(root)
        self.ctdirs = list(set(self.ctdirs))

    def checkCTdirs(self):
        """
        Determine whether directory is of type 3 or type 4 and store in self.typ with index corresponding to ctdir
        Type3: Has flats, darks and not flats2 -- or flats==flats2
        Type4: Has flats, darks and flats2
        """
        for ctdir in self.ctdirs:
            # flats/darks and no flats2 or flats2==flats -> type 3
            if ( os.path.exists(os.path.join(ctdir, self._fdt_names[1])) \
                     and os.path.exists(os.path.join(ctdir, self._fdt_names[0])) \
                     and (not os.path.exists(os.path.join(ctdir, self._fdt_names[3])) \
                            or self._fdt_names[1]==self._fdt_names[3]) ):
                self.typ.append(3)
            # flats/darks/flats2 -> type4
            elif ( os.path.exists(os.path.join(ctdir, self._fdt_names[1])) \
                     and os.path.exists(os.path.join(ctdir, self._fdt_names[0])) \
                     and os.path.exists(os.path.join(ctdir, self._fdt_names[3])) ):
                self.typ.append(4)
            else:
                print(os.path.basename(ctdir))
                self.typ.append(0)

    def checkCommonFDT(self):
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
            if (os.path.exists(self.common_flats)
                    and os.path.exists(self.common_darks)
                    and os.path.exists(self.common_flats2)):
                return True
        elif self.use_common_flats2 is False:
            if (os.path.exists(self.common_flats)
                    and os.path.exists(self.common_darks)):
                return True
        return False

    def checkCommonFDTFiles(self):
        """
        Verifies that directories of tomo and common flats/darks/flats contain only .tif files
        :return: True if directories exist, False if they do not exist
        """
        for i, ctdir in enumerate(self.ctdirs):
            ctdir_tomo_path = os.path.join(ctdir, self._fdt_names[2])
            if not self._checkTifs(ctdir_tomo_path):
                print("Invalid files found in " + str(ctdir_tomo_path))
                self.typ[i] = 0
                return False
            if not self._checkTifs(self.common_flats):
                print("Invalid files found in " + str(self.common_flats))
                return False
            if not self._checkTifs(self.common_darks):
                print("Invalid files found in " + str(self.common_darks))
                return False
            if self.use_common_flats2 and not self._checkTifs(self.common_flats2):
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
            if ( self.typ[i] == 3 and \
                    self._checkTifs(os.path.join(ctdir, self._fdt_names[1])) and \
                    self._checkTifs(os.path.join(ctdir, self._fdt_names[0])) and \
                    self._checkTifs(os.path.join(ctdir, self._fdt_names[2])) ):
                continue
            elif  ( self.typ[i] == 4 and \
                    self._checkTifs(os.path.join(ctdir, self._fdt_names[1])) and \
                    self._checkTifs(os.path.join(ctdir, self._fdt_names[0])) and \
                    self._checkTifs(os.path.join(ctdir, self._fdt_names[2]))and \
                    self._checkTifs(os.path.join(ctdir, self._fdt_names[3])) ):
                continue
            else: 
                self.typ[i] = 0
    
    def _checkTifs(self, tmpath):
        """
        Checks each whether item in directory tmppath is a .tif file
        :param tmpath: Path to directory
        :return: 0 if invalid item found in directory - 1 if no invalid items found in directory
        """
        for i in os.listdir(tmpath):
            if os.path.isdir(i):
                return 0
            if i.split('.')[-1] != 'tif':
                return 0
        return 1
            
    def SortBadGoodSets(self):
        """
        Reduces type of all directories to either
        Good with flats 2 (1) or good without flats2 (0) or bad (<0)
        """
        self.total = len(self.ctdirs)
        self.ctsets = sorted(zip(self.ctdirs, self.typ), key=lambda s: s[0])
        self.total = len(self.ctsets)
        self.good = [int(y) > 2 for x, y in self.ctsets].count(True)

        tmp = len(self.lvl0)
        if self.verb:
            print('Total folders {}, good folders {}'.format(self.total, self.good))
            print('{:>20}\t{}'.format("Path to CT set", "Typ: 0 bad, 3 no flats2, 4 with flats2"))
            for ctdir in self.ctsets:
                msg1 = ctdir[0][tmp:]
                if msg1 == '':
                    msg1 = '.'
                print('{:>20}\t{}'.format(msg1, ctdir[1]))

        #keep paths to directories with good ct data only:
        self.ctsets = [q for q in self.ctsets if int(q[1] > 0)]


    def Getlvl0(self):
        return self.lvl0


"""
Created on Dec 1, 2020
@author: sergei gasilov
"""

import os
import warnings
from tofu.ez.ctdir_walker import WalkCTdirs
from tofu.ez.util import *
from tofu.util import get_filenames
from tofu.util import get_filenames, read_image
from tofu.ez.util import enquote


warnings.filterwarnings("ignore")


def fmt_ufo_cmd(inp, out, args):
    cmd = "ufo-launch read path={}".format(inp)
    cmd += " ! non-local-means patch-radius={}".format(args.patch_r)
    cmd += " search-radius={}".format(args.search_r)
    cmd += " h={}".format(args.h)
    cmd += " sigma={}".format(args.sig)
    cmd += " window={}".format(args.w)
    cmd += " fast={}".format(args.fast)
    cmd += " estimate-sigma={}".format(args.autosig)
    cmd += " ! write filename={}".format(enquote(out))
    if not args.bigtif:
        cmd += " bytes-per-file=0 tiff-bigtiff=False"
    return cmd


def main_tk(args):
    if args.input_is_file:
        out_pattern = args.outdir
    else:
        if not os.path.exists(args.outdir):
            os.makedirs(args.outdir)
        out_pattern = os.path.join(args.outdir, "im-nlmfilt-%05i.tif")
    cmd = fmt_ufo_cmd(args.indir, out_pattern, args)
    if args.dryrun:
        print(cmd)
    else:
        os.system(cmd)
    return 0

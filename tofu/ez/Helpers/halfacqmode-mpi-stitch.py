#!/usr/bin/env python3

import sys
import time

import tifffile
from mpi4py import MPI

from tofu.ez.Helpers.stitch_funcs import stitch
from tofu.ez.image_read_write import TiffSequenceReader

path_to_script, ax, crop, bigtif_name, out_fmt = sys.argv

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
# t0 = time.time()
#print(f"{t0:.2f}: Private {rank} of {size} is at your service")

tfs = TiffSequenceReader(bigtif_name)
npairs = tfs.num_images//2
n_my_pairs = int(npairs/size) + (1 if npairs%size > rank else 0)
#print(f'Private {rank} got {n_my_pairs} pairs to process out of total {npairs}')

for pair_number in range(n_my_pairs):
    idx = rank + pair_number * size
 #   print(f'Private {rank} processing pair {idx} - {idx+npairs}')
    first = tfs.read(idx)
    second = tfs.read(idx+npairs)[:, ::-1]

    stitched = stitch(first, second, int(ax), int(crop))
    tifffile.imwrite(out_fmt.format(idx), stitched)

tfs.close()

#print(f"Private {rank} stitched {n_my_pairs} pairs in {time.time()-t0:.2f} s! Am I first?")
# Important - release communicator!
try:
    parent_comm = comm.Get_parent()
    parent_comm.Disconnect()
except MPI.Exception:
    pass





#
# def main():
#     comm = MPI.COMM_WORLD
#     size = comm.Get_size()
#     rank = comm.Get_rank()
#     print(f"I am {rank} of {size}")
#
# if __name__ == "__main__":
#     main()

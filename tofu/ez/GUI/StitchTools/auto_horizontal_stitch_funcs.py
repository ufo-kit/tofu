import os
import tifffile
from collections import defaultdict
import numpy as np
import multiprocessing as mp
from functools import partial
from scipy.stats import gmean
import math
import yaml


class AutoHorizontalStitchFunctions:
    def __init__(self, parameters):
        self.lvl0 = os.path.abspath(parameters["input_dir"])
        self.ct_dirs = []
        self.ct_axis_dict = {}
        self.parameters = parameters
        self.greatest_axis_value = 0

    def run_horizontal_auto_stitch(self):
        """
        Main function that calls all other functions
        """
        # Write parameters to .yaml file - quit if something goes wrong
        if self.write_yaml_params() == -1:
            return -1

        self.print_parameters()

        # Check input directory and find structure
        print("--> Finding CT Directories")
        self.find_ct_dirs()

        if len(self.ct_dirs) == 0:
            print("Error: Could not find any input CT directories")
            print("-> Ensure that the directory you selected contains subdirectories named 'tomo'")
            return -1

        # For each zview we compute the axis of rotation
        print("--> Finding Axis of Rotation for each Z-View")
        self.find_images_and_compute_centre()
        print("\n ==> Found the following z-views and their corresponding axis of rotation <==")

        # Check the axis values and adjust for any outliers
        # If difference between two subsequent zdirs is > 3 then just change it to be 1 greater than previous
        self.correct_outliers()
        print("--> ct_axis_dict after correction: ")
        print(self.ct_axis_dict)

        # Find the greatest axis value for use in determining overall cropping amount when stitching
        self.find_greatest_axis_value()
        print("Greatest axis value: " + str(self.greatest_axis_value))

        # Output the input parameters and axis values to the log file
        self.write_to_log_file()

        # For each ct-dir and z-view we want to stitch all the images using the values in ct_axis_dict
        if not self.parameters['dry_run']:
            print("\n--> Stitching Images...")
            self.find_and_stitch_images()
            print("--> Finished Stitching")

    def write_yaml_params(self):
        try:
            # Create the output directory root and save the parameters.yaml file
            os.makedirs(self.parameters['output_dir'], mode=0o777)
            file_path = os.path.join(self.parameters['output_dir'], 'auto_vertical_stitch_parameters.yaml')
            file_out = open(file_path, 'w')
            yaml.dump(self.parameters, file_out)
            print("Parameters file saved at: " + str(file_path))
            return 0
        except FileExistsError:
            print("--> Output Directory Exists - Delete Before Proceeding")
            return -1

    def find_ct_dirs(self):
        """
        Walks directories rooted at "Input Directory" location
        Appends their absolute path to ct-dir if they contain a directory with same name as "tomo" entry in GUI
        """
        for root, dirs, files in os.walk(self.lvl0):
            for name in dirs:
                if name == "tomo":
                    self.ct_dirs.append(root)
        self.ct_dirs = sorted(list(set(self.ct_dirs)))

    def find_images_and_compute_centre(self):
        """
        We use multiprocessing across all CPU cores to determine the axis values for each zview in parallel
        We get a dictionary of z-directory and axis of rotation key-value pairs in self.ct_axis_dict at the end
        """
        index = range(len(self.ct_dirs))
        pool = mp.Pool(processes=mp.cpu_count())
        exec_func = partial(self.find_center_parallel_proc)
        temp_axis_list = pool.map(exec_func, index)
        # Flatten list of dicts to just be a dictionary of key:value pairs
        for item in temp_axis_list:
            self.ct_axis_dict.update(item)

    def find_center_parallel_proc(self, index):
        """
        Finds the images corresponding to the 0-180, 90-270, 180-360 degree pairs
        These are used to compute the average axis of rotation for each zview in a ct directory
        :return: A key value pair corresponding to the z-view path and its axis of rotation
        """
        zview_path = self.ct_dirs[index]
        # Get list of image names in the directory
        try:
            tomo_path = os.path.join(zview_path, "tomo")
            image_list = sorted(os.listdir(tomo_path))
            num_images = len(image_list)

            # If the number of images is divisible by eight we do eight 180 degree pairs in 45 degree increments
            if num_images % 8 == 0:
                # Get the names of the images in 45 degree increments starting from 0
                zero_degree_image_name = image_list[0]
                one_eighty_degree_image_name = image_list[int(num_images / 2) - 1]
                forty_five_degree_image_name = image_list[int(num_images / 8) - 1]
                two_twenty_five_degree_image_name = image_list[int(num_images * 5 / 8) - 1]
                ninety_degree_image_name = image_list[int(num_images / 4) - 1]
                two_seventy_degree_image_name = image_list[int(num_images * 3 / 4) - 1]
                one_thirty_five_degree_image_name = image_list[int(num_images * 3 / 8) - 1]
                three_fifteen_degree_image_name = image_list[int(num_images * 7 / 8) - 1]
                three_sixty_degree_image_name = image_list[-1]

                # Get the paths for the images
                zero_degree_image_path = os.path.join(tomo_path, zero_degree_image_name)
                forty_five_degree_image_path = os.path.join(tomo_path, forty_five_degree_image_name)
                ninety_degree_image_path = os.path.join(tomo_path, ninety_degree_image_name)
                one_thirty_five_degree_image_path = os.path.join(tomo_path, one_thirty_five_degree_image_name)
                one_eighty_degree_image_path = os.path.join(tomo_path, one_eighty_degree_image_name)
                two_twenty_five_degree_image_path = os.path.join(tomo_path, two_twenty_five_degree_image_name)
                two_seventy_degree_image_path = os.path.join(tomo_path, two_seventy_degree_image_name)
                three_fifteen_degree_image_path = os.path.join(tomo_path, three_fifteen_degree_image_name)
                three_sixty_degree_image_path = os.path.join(tomo_path, three_sixty_degree_image_name)

                axis_list = [self.compute_center(zero_degree_image_path, one_eighty_degree_image_path),
                             self.compute_center(forty_five_degree_image_path, two_twenty_five_degree_image_path),
                             self.compute_center(ninety_degree_image_path, two_seventy_degree_image_path),
                             self.compute_center(one_thirty_five_degree_image_path, three_fifteen_degree_image_path),
                             self.compute_center(one_eighty_degree_image_path, three_sixty_degree_image_path),
                             self.compute_center(two_twenty_five_degree_image_path, forty_five_degree_image_path),
                             self.compute_center(two_seventy_degree_image_path, ninety_degree_image_path),
                             self.compute_center(three_fifteen_degree_image_path, one_thirty_five_degree_image_path)]

            # If the number of images is not divisible by eight we do four 180 degree pairs in 90 degree increments
            elif num_images % 4 == 0:
                # Get the images corresponding to 0, 90, 180, and 270 degree rotations in half-acquisition mode -
                zero_degree_image_name = image_list[0]
                one_eighty_degree_image_name = image_list[int(num_images / 2) - 1]
                ninety_degree_image_name = image_list[int(num_images / 4) - 1]
                two_seventy_degree_image_name = image_list[int(num_images * 3 / 4) - 1]
                three_sixty_degree_image_name = image_list[-1]

                # Get the paths for the images
                zero_degree_image_path = os.path.join(tomo_path, zero_degree_image_name)
                one_eighty_degree_image_path = os.path.join(tomo_path, one_eighty_degree_image_name)
                ninety_degree_image_path = os.path.join(tomo_path, ninety_degree_image_name)
                two_seventy_degree_image_path = os.path.join(tomo_path, two_seventy_degree_image_name)
                three_sixty_degree_image_path = os.path.join(tomo_path, three_sixty_degree_image_name)

                # Determine the axis of rotation for pairs at 0-180, 90-270, 180-360 and 270-90 degrees
                axis_list = [self.compute_center(zero_degree_image_path, one_eighty_degree_image_path),
                             self.compute_center(ninety_degree_image_path, two_seventy_degree_image_path),
                             self.compute_center(one_eighty_degree_image_path, three_sixty_degree_image_path),
                             self.compute_center(two_seventy_degree_image_path, ninety_degree_image_path)]
            # Otherwise, we compute the centre based on 0-180 and 180-360 pairs
            else:
                # Get the images corresponding to 0, 180 and 360 degree rotations in half-acquisition mode -
                zero_degree_image_name = image_list[0]
                one_eighty_degree_image_name = image_list[int(num_images / 2) - 1]
                three_sixty_degree_image_name = image_list[-1]

                # Get the paths for the images
                zero_degree_image_path = os.path.join(tomo_path, zero_degree_image_name)
                one_eighty_degree_image_path = os.path.join(tomo_path, one_eighty_degree_image_name)
                three_sixty_degree_image_path = os.path.join(tomo_path, three_sixty_degree_image_name)

                # Determine the axis of rotation for pairs at 0-180, 90-270, 180-360 and 270-90 degrees
                axis_list = [self.compute_center(zero_degree_image_path, one_eighty_degree_image_path),
                             self.compute_center(one_eighty_degree_image_path, three_sixty_degree_image_path)]

            # Find the average of 180 degree rotation pairs
            print("--> " + str(zview_path))
            print(axis_list)

            # If mode occurs more than 4 times then pick it as axis value, otherwise use geometric mean
            most_common_value = max(set(axis_list), key=axis_list.count)
            if axis_list.count(most_common_value) > 4:
                axis_value = self.col_round(most_common_value)
            else:
                axis_value = self.col_round(gmean(axis_list))

            print("Axis value: " + str(axis_value))
            # Return each zview and its axis of rotation value as key-value pair
            return {zview_path: axis_value}

        except NotADirectoryError:
            print("Skipped - Not a Directory: " + tomo_path)

    def compute_center(self, zero_degree_image_path, one_eighty_degree_image_path):
        """
        Takes two pairs of images in half-acquisition mode separated by a full 180 degree rotation of the sample
        The images are then flat-corrected and cropped to the overlap region
        They are then correlated using fft to determine the axis of rotation
        :param zero_degree_image_path: First sample scan
        :param one_eighty_degree_image_path: Second sample scan rotated 180 degree from first sample scan
        :return: The axis of rotation based on the correlation of two 180 degree image pairs
        """
        if self.parameters['sample_on_right'] is False:
            # Read each image into a numpy array
            first = self.read_image(zero_degree_image_path, False)
            second = self.read_image(one_eighty_degree_image_path, False)
        elif self.parameters['sample_on_right'] is True:
            # Read each image into a numpy array - flip both images
            first = self.read_image(zero_degree_image_path, True)
            second = self.read_image(one_eighty_degree_image_path, True)

        # Do flat field correction on the images
        # Case 1: Using darks/flats/flats2 in each CTdir alongside tomo
        if self.parameters['common_flats_darks'] is False:
            tomo_path, filename = os.path.split(zero_degree_image_path)
            zdir_path, tomo_name = os.path.split(tomo_path)
            flats_path = os.path.join(zdir_path, "flats")
            darks_path = os.path.join(zdir_path, "darks")
            flat_files = self.get_filtered_filenames(flats_path)
            dark_files = self.get_filtered_filenames(darks_path)
        # Case 2: Using common set of flats and darks
        elif self.parameters['common_flats_darks'] is True:
            flat_files = self.get_filtered_filenames(self.parameters['flats_dir'])
            dark_files = self.get_filtered_filenames(self.parameters['darks_dir'])

        flats = np.array([tifffile.TiffFile(x).asarray().astype(np.float) for x in flat_files])
        darks = np.array([tifffile.TiffFile(x).asarray().astype(np.float) for x in dark_files])
        dark = np.mean(darks, axis=0)
        flat = np.mean(flats, axis=0) - dark
        first = (first - dark) / flat
        second = (second - dark) / flat

        # We must crop the first image from first pixel column up until overlap
        first_cropped = first[:, :int(self.parameters['overlap_region'])]
        # We must crop the 180 degree rotation (which has been flipped 180) from width-overlap until last pixel column
        second_cropped = second[:, :int(self.parameters['overlap_region'])]

        axis = self.compute_rotation_axis(first_cropped, second_cropped)
        return axis

    def get_filtered_filenames(self, path, exts=['.tif', '.edf']):
        result = []

        try:
            for ext in exts:
                result += [os.path.join(path, f) for f in os.listdir(path) if f.endswith(ext)]
        except OSError:
            return []

        return sorted(result)

    def compute_rotation_axis(self, first_projection, last_projection):
        """
        Compute the tomographic rotation axis based on cross-correlation technique.
        *first_projection* is the projection at 0 deg, *last_projection* is the projection
        at 180 deg.
        """
        from scipy.signal import fftconvolve
        width = first_projection.shape[1]
        first_projection = first_projection - first_projection.mean()
        last_projection = last_projection - last_projection.mean()

        # The rotation by 180 deg flips the image horizontally, in order
        # to do cross-correlation by convolution we must also flip it
        # vertically, so the image is transposed and we can apply convolution
        # which will act as cross-correlation
        convolved = fftconvolve(first_projection, last_projection[::-1, :], mode='same')
        center = np.unravel_index(convolved.argmax(), convolved.shape)[1]

        return (width / 2.0 + center) / 2

    def write_to_log_file(self):
        '''
        Creates a log file with extension .info at the root of the output_dir tree structure
        Log file contains directory path and axis value
        '''
        if not os.path.isdir(self.parameters['output_dir']):
            os.makedirs(self.parameters['output_dir'], mode=0o777)
        file_path = os.path.join(self.parameters['output_dir'], 'axis_values.info')
        print("Axis values log file stored at: " + file_path)
        try:
            file_handle = open(file_path, 'w')
            # Print input parameters
            file_handle.write("======================== Parameters ========================" + "\n")
            file_handle.write("Input Directory: " + self.parameters['input_dir'] + "\n")
            file_handle.write("Output Directory: " + self.parameters['output_dir'] + "\n")
            file_handle.write("Using common set of flats and darks: " + str(self.parameters['common_flats_darks']) + "\n")
            file_handle.write("Flats Directory: " + self.parameters['flats_dir'] + "\n")
            file_handle.write("Darks Directory: " + self.parameters['darks_dir'] + "\n")
            file_handle.write("Overlap Region Size: " + self.parameters['overlap_region'] + "\n")
            file_handle.write("Sample on right: " + str(self.parameters['sample_on_right']) + "\n")

            # Print z-directory and corresponding axis value
            file_handle.write("\n======================== Axis Values ========================\n")
            for key in self.ct_axis_dict:
                key_value_str = str(key) + " : " + str(self.ct_axis_dict[key])
                print(key_value_str)
                file_handle.write(key_value_str + '\n')

            file_handle.write("\nGreatest axis value: " + str(self.greatest_axis_value))
        except FileNotFoundError:
            print("Error: Could not write log file")

    def correct_outliers(self):
        """
        This function looks at each CTDir containing Z00-Z0N
        If the axis values for successive zviews are greater than 3 (an outlier)
        Then we correct this by tying the outlier to the previous Z-View axis plus one
        self.ct_axis_dict is updated with corrected axis values
        """
        sorted_by_ctdir_dict = defaultdict(dict)
        for key in self.ct_axis_dict:
            path_key, zdir = os.path.split(str(key))
            axis_value = self.ct_axis_dict[key]
            sorted_by_ctdir_dict[path_key][zdir] = axis_value

        for dir_key in sorted_by_ctdir_dict:
            z_dir_list = list(sorted_by_ctdir_dict[dir_key].values())

            # Need to account for the case where the first z-view is an outlier
            min_value = min(z_dir_list)
            if z_dir_list[0] > min_value + 2:
                z_dir_list[0] = min_value

            # Compare the difference of successive pairwise axis values
            # If the difference is greater than 3 then set the second pair value to be 1 more than the first pair value
            for index in range(len(z_dir_list) - 1):
                first_value = z_dir_list[index]
                second_value = z_dir_list[index + 1]
                difference = abs(second_value - first_value)
                if difference > 3:
                    # Set second value to be one more than first
                    z_dir_list[index + 1] = z_dir_list[index] + 1

            # Assigns the values in z_dir_list back to the ct_dir_dict
            index = 0
            for zdir in sorted_by_ctdir_dict[dir_key]:
                corrected_axis_value = z_dir_list[index]
                sorted_by_ctdir_dict[dir_key][zdir] = corrected_axis_value
                index += 1

        # Assigns the corrected values back to self.ct_axis_dict
        for path_key in sorted_by_ctdir_dict:
            for z_key in sorted_by_ctdir_dict[path_key]:
                path_string = os.path.join(str(path_key), str(z_key))
                self.ct_axis_dict[path_string] = sorted_by_ctdir_dict[path_key][z_key]

    def find_greatest_axis_value(self):
        """
        Looks through all axis values and determines the greatest value
        """
        axis_list = list(self.ct_axis_dict.values())
        self.greatest_axis_value = max(axis_list)

    def find_and_stitch_images(self):
        index = range(len(self.ct_dirs))
        pool = mp.Pool(processes=mp.cpu_count())
        exec_func = partial(self.find_and_stitch_parallel_proc)
        # TODO : Try using pool.map or pool.imap_unordered and compare times
        # Try imap_unordered() as see if it is faster - with chunksize len(self.ct_dir) / mp.cpu_count()
        # pool.imap_unordered(exec_func, index, int(len(self.ct_dirs) / mp.cpu_count()))
        pool.map(exec_func, index)

    def find_and_stitch_parallel_proc(self, index):
        z_dir_path = self.ct_dirs[index]
        # Get list of image names in the directory
        try:
            # Want to maintain directory structure for output so we subtract the output-path from z_dir_path
            # Then we append this to the output_dir path
            diff_path = os.path.relpath(z_dir_path, self.parameters['input_dir'])
            out_path = os.path.join(self.parameters['output_dir'], diff_path)
            rotation_axis = self.ct_axis_dict[z_dir_path]

            # If using common flats/darks across all zdirs
            # then use common flats/darks directories as source of images to stitch and save to output zdirs
            if self.parameters['common_flats_darks'] is True:
                self.stitch_180_pairs(rotation_axis, z_dir_path, out_path, "tomo")
                flats_parent_path, garbage = os.path.split(self.parameters['flats_dir'])
                self.stitch_180_pairs(rotation_axis, flats_parent_path, out_path, "flats")
                darks_parent_path, garbage = os.path.split(self.parameters['darks_dir'])
                self.stitch_180_pairs(rotation_axis, darks_parent_path, out_path, "darks")
            # If using local flats/darks to each zdir then use those as source for stitching
            elif self.parameters['common_flats_darks'] is False:
                self.stitch_180_pairs(rotation_axis, z_dir_path, out_path, "tomo")
                # Need to account for case where flats, darks, flats2 don't exist
                if os.path.isdir(os.path.join(z_dir_path, "flats")):
                    self.stitch_180_pairs(rotation_axis, z_dir_path, out_path, "flats")
                if os.path.isdir(os.path.join(z_dir_path, "darks")):
                    self.stitch_180_pairs(rotation_axis, z_dir_path, out_path, "darks")
                if os.path.isdir(os.path.join(z_dir_path, "flats2")):
                    self.stitch_180_pairs(rotation_axis, z_dir_path, out_path, "flats2")

            print("--> " + str(z_dir_path))
            print("Axis of rotation: " + str(rotation_axis))

        except NotADirectoryError as e:
            print("Skipped - Not a Directory: " + e.filename)

    def stitch_180_pairs(self, rotation_axis, in_path, out_path, type_str):
        """
        Finds images in tomo, flats, darks, flats2 directories corresponding to 180 degree pairs
        The first image is stitched with the middle image and so on by using the index and midpoint
        :param rotation_axis: axis of rotation for z-directory
        :param in_path: absolute path to z-directory
        :param out_path: absolute path to output directory
        :param type_str: Type of subdirectory - e.g. "tomo", "flats", "darks", "flats2"
        """
        os.makedirs(os.path.join(out_path, type_str), mode=0o777)
        image_list = sorted(os.listdir(os.path.join(in_path, type_str)))
        midpoint = int(len(image_list) / 2)
        for index in range(midpoint):
            first_path = os.path.join(in_path, type_str, image_list[index])
            second_path = os.path.join(in_path, type_str, image_list[midpoint + index])
            output_image_path = os.path.join(out_path, type_str, type_str + "_stitched_{:>04}.tif".format(index))
            crop_amount = abs(self.greatest_axis_value - round(rotation_axis))
            self.open_images_stitch_write(rotation_axis, crop_amount, first_path, second_path, output_image_path)

    def print_parameters(self):
        """
        Prints parameter values with line formatting
        """
        print()
        print("**************************** Running Auto Horizontal Stitch ****************************")
        print("======================== Parameters ========================")
        print("Input Directory: " + self.parameters['input_dir'])
        print("Output Directory: " + self.parameters['output_dir'])
        print("Using common set of flats and darks: " + str(self.parameters['common_flats_darks']))
        print("Flats Directory: " + self.parameters['flats_dir'])
        print("Darks Directory: " + self.parameters['darks_dir'])
        print("Overlap Region Size: " + self.parameters['overlap_region'])
        print("Sample on right: " + str(self.parameters['sample_on_right']))
        print("============================================================")

    """****** BORROWED FUNCTIONS ******"""

    def read_image(self, file_name, flip_image):
        """
        Reads in a tiff image from disk at location specified by file_name, returns a numpy array
        :param file_name: Str - path to file
        :param flip_image: Bool - Whether image is to be flipped horizontally or not
        :return: A numpy array of type float
        """
        with tifffile.TiffFile(file_name) as tif:
            image = tif.pages[0].asarray(out='memmap')
        if flip_image is True:
            image = np.fliplr(image)
        return image

    def open_images_stitch_write(self, ax, crop, first_image_path, second_image_path, out_fmt):
        if self.parameters['sample_on_right'] is False:
            # Read each image into a numpy array - We flip the second image
            first = self.read_image(first_image_path, flip_image=False)
            second = self.read_image(second_image_path, flip_image=True)
        if self.parameters['sample_on_right'] is True:
            # We pass index and formats as argument - We flip the first image before stitching
            first = self.read_image(first_image_path, flip_image=True)
            second = self.read_image(second_image_path, flip_image=False)

        stitched = self.stitch(first, second, ax, crop)
        tifffile.imwrite(out_fmt, stitched)

    def stitch(self, first, second, axis, crop):
        h, w = first.shape
        if axis > w / 2:
            dx = int(2 * (w - axis) + 0.5)
        else:
            dx = int(2 * axis + 0.5)
            tmp = np.copy(first)
            first = second
            second = tmp
        result = np.empty((h, 2 * w - dx), dtype=first.dtype)
        ramp = np.linspace(0, 1, dx)

        # Mean values of the overlapping regions must match, which corrects flat-field inconsistency
        # between the two projections
        # We clip the values in second so that there are no saturated pixel overflow problems
        k = np.mean(first[:, w - dx:]) / np.mean(second[:, :dx])
        second = np.clip(second * k, np.iinfo(np.uint16).min, np.iinfo(np.uint16).max).astype(np.uint16)

        result[:, :w - dx] = first[:, :w - dx]
        result[:, w - dx:w] = first[:, w - dx:] * (1 - ramp) + second[:, :dx] * ramp
        result[:, w:] = second[:, dx:]

        return result[:, slice(int(crop), int(2 * (w - axis) - crop), 1)]

    def col_round(self, x):
        frac = x - math.floor(x)
        if frac < 0.5: return math.floor(x)
        return math.ceil(x)

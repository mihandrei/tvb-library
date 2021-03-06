# -*- coding: utf-8 -*-
#
#
#  TheVirtualBrain-Scientific Package. This package holds all simulators, and
# analysers necessary to run brain-simulations. You can use it stand alone or
# in conjunction with TheVirtualBrain-Framework Package. See content of the
# documentation-folder for more details. See also http://www.thevirtualbrain.org
#
# (c) 2012-2013, Baycrest Centre for Geriatric Care ("Baycrest")
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License version 2 as published by the Free
# Software Foundation. This program is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
# License for more details. You should have received a copy of the GNU General
# Public License along with this program; if not, you can download it here
# http://www.gnu.org/licenses/old-licenses/gpl-2.0
#
#
#   CITATION:
# When using The Virtual Brain for scientific publications, please cite it as follows:
#
#   Paula Sanz Leon, Stuart A. Knock, M. Marmaduke Woodman, Lia Domide,
#   Jochen Mersmann, Anthony R. McIntosh, Viktor Jirsa (2013)
#       The Virtual Brain: a simulator of primate brain network dynamics.
#   Frontiers in Neuroinformatics (7:10. doi: 10.3389/fninf.2013.00010)
#
#

"""

Framework methods for the TimeSeries datatypes.

.. moduleauthor:: Robert Parcus <betoparcus@gmail.com>
.. moduleauthor:: Ciprian Tomoiaga <ciprian.tomoiaga@codemart.ro>
.. moduleauthor:: Lia Domide <lia.domide@codemart.ro>
.. moduleauthor:: Stuart A. Knock <Stuart@tvb.invalid>
.. moduleauthor:: Marmaduke Woodman <mw@eml.cc>

"""

import json
import numpy
import tvb.datatypes.time_series_data as time_series_data
import tvb.basic.traits.exceptions as exceptions
from tvb.basic.logger.builder import get_logger


LOG = get_logger(__name__)


class TimeSeriesFramework(time_series_data.TimeSeriesData):
    """
    This class exists to add framework methods to TimeSeriesData (base framework functionality).
    """

    __tablename__ = None


    def configure(self):
        """
        After populating few fields, compute the rest of the fields
        """
        super(TimeSeriesFramework, self).configure()
        data_shape = self.read_data_shape()
        self.nr_dimensions = len(data_shape)
        self.sample_rate = 1.0 / self.sample_period

        for i in range(min(self.nr_dimensions, 4)):
            setattr(self, 'length_%dd' % (i + 1), int(data_shape[i]))


    def read_data_shape(self):
        """
        Expose shape read on field data.
        """
        try:
            return self.get_data_shape('data')
        except exceptions.TVBException:
            self.logger.exception("Could not read data shape for TS!")
            raise exceptions.TVBException("Invalid empty TimeSeries!")



    def read_data_slice(self, data_slice):
        """
        Expose chunked-data access.
        """
        return self.get_data('data', data_slice)


    def read_time_page(self, current_page, page_size, max_size=None):
        """
        Compute time for current page.
        :param current_page: Starting from 0
        """
        current_page = int(current_page)
        page_size = int(page_size)

        if max_size is None:
            max_size = page_size
        else:
            max_size = int(max_size)

        page_real_size = page_size * self.sample_period
        start_time = self.start_time + current_page * page_real_size
        end_time = start_time + min(page_real_size, max_size * self.sample_period)

        return numpy.arange(start_time, end_time, self.sample_period)


    def read_channels_page(self, from_idx, to_idx, step=None, specific_slices=None, channels_list=None):
        """
        Read and return only the data page for the specified channels list.

        :param from_idx: the starting time idx from which to read data
        :param to_idx: the end time idx up until to which you read data
        :param step: increments in which to read the data. Optional, default to 1.
        :param specific_slices: optional parameter. If speficied slices the data accordingly.
        :param channels_list: the list of channels for which we want data
        """
        if channels_list:
            channels_list = json.loads(channels_list)

        if channels_list:
            channel_slice = tuple(channels_list)
        else:
            channel_slice = slice(None)

        data_page = self.read_data_page(
            from_idx, to_idx, step, specific_slices)
        # This is just a 1D array like in the case of Global Average monitor.
        # No need for the channels list
        if len(data_page.shape) == 1:
            return data_page.reshape(data_page.shape[0], 1)
        else:
            return data_page[:, channel_slice]


    def read_data_page(self, from_idx, to_idx, step=None, specific_slices=None):
        """
        Retrieve one page of data (paging done based on time).
        """
        from_idx, to_idx = int(from_idx), int(to_idx)

        if isinstance(specific_slices, basestring):
            specific_slices = json.loads(specific_slices)
        if step is None:
            step = 1
        else:
            step = int(step)

        slices = []
        overall_shape = self.read_data_shape()
        for i in xrange(len(overall_shape)):
            if i == 0:
                # Time slice
                slices.append(
                    slice(from_idx, min(to_idx, overall_shape[0]), step))
                continue
            if i == 2:
                # Read full of the main_dimension (space for the simulator)
                slices.append(slice(overall_shape[i]))
                continue
            if specific_slices is None:
                slices.append(slice(0, 1))
            else:
                slices.append(slice(specific_slices[i], min(specific_slices[i] + 1, overall_shape[i]), 1))

        data = self.read_data_slice(tuple(slices))
        if len(data) == 1:
            # Do not allow time dimension to get squeezed, a 2D result need to
            # come out of this method.
            data = data.squeeze()
            data = data.reshape((1, len(data)))
        else:
            data = data.squeeze()

        return data


    def write_time_slice(self, partial_result):
        """
        Append a new value to the ``time`` attribute.
        """
        self.store_data_chunk("time", partial_result, grow_dimension=0, close_file=False)


    def write_data_slice(self, partial_result, grow_dimension=0):
        """
        Append a chunk of time-series data to the ``data`` attribute.
        """
        self.store_data_chunk("data", partial_result, grow_dimension=grow_dimension, close_file=False)


    def get_min_max_values(self):
        """
        Retrieve the minimum and maximum values from the metadata.
        :returns: (minimum_value, maximum_value)
        """
        metadata = self.get_metadata('data')
        return metadata[self.METADATA_ARRAY_MIN], metadata[self.METADATA_ARRAY_MAX]


    def get_space_labels(self):
        """
        It assumes that we want to select in the 3'rd dimension,
        and generates labels for each point in that dimension.
        Subclasses are more specific.
        :return: An array of strings.
        """
        if self.nr_dimensions > 2:
            return ['signal-%d' % i for i in xrange(self._length_3d)]
        else:
            return []


    def get_grouped_space_labels(self):
        """
        :return: A list of label groups. A label group is a tuple (name, [(label_idx, label)...]).
                 Default all labels in a group named ''
        """
        return [('', list(enumerate(self.get_space_labels())))]


    def get_default_selection(self):
        """
        :return: The measure point indices that have to be shown by default. By default show all.
        """
        return range(len(self.get_space_labels()))


    def get_measure_points_selection_gid(self):
        """
        :return: a datatype gid with which to obtain al valid measure point selection for this time series
                 We have to decide if the default should be all selections or none
        """
        return ''


    @staticmethod
    def accepted_filters():
        filters = time_series_data.TimeSeriesData.accepted_filters()
        filters.update({'datatype_class._nr_dimensions': {'type': 'int', 'display': 'No of Dimensions',
                                                          'operations': ['==', '<', '>']},
                        'datatype_class._sample_period': {'type': 'float', 'display': 'Sample Period',
                                                          'operations': ['==', '<', '>']},
                        'datatype_class._sample_rate': {'type': 'float', 'display': 'Sample Rate',
                                                        'operations': ['==', '<', '>']},
                        'datatype_class._title': {'type': 'string', 'display': 'Title',
                                                  'operations': ['==', '!=', 'like']}})
        return filters



class TimeSeriesSensorsFramework(TimeSeriesFramework):
    """
    Add framework related functionality for TS Sensor classes
    """

    def get_space_labels(self):
        """
        :return: An array of strings with the sensors labels.
        """
        if self.sensors is not None:
            return list(self.sensors.labels)
        return []


    def get_measure_points_selection_gid(self):
        if self.sensors is not None:
            return self.sensors.gid
        return ''


    def get_default_selection(self):
        if self.sensors is not None:
            # select only the first 8 channels
            return range(min(8, len(self.get_space_labels())))
        return []



class TimeSeriesRegionFramework(time_series_data.TimeSeriesRegionData, TimeSeriesFramework):
    """
    This class exists to add framework methods to TimeSeriesRegionData.
    """

    def get_space_labels(self):
        """
        :return: An array of strings with the connectivity node labels.
        """
        if self.connectivity is not None:
            return list(self.connectivity.region_labels)
        return []


    def get_grouped_space_labels(self):
        """
        :return: A structure of this form [('left', [(idx, lh_label)...]), ('right': [(idx, rh_label) ...])]
        """
        if self.connectivity is not None:
            return self.connectivity.get_grouped_space_labels()
        else:
            return super(TimeSeriesRegionFramework, self).get_grouped_space_labels()


    def get_default_selection(self):
        """
        :return: If the connectivity of this time series is edited from another
                 return the nodes of the parent that are present in the connectivity.
        """
        if self.connectivity is not None:
            return self.connectivity.get_default_selection()
        else:
            return super(TimeSeriesRegionFramework, self).get_default_selection()


    def get_measure_points_selection_gid(self):
        """
        :return: the associated connectivity gid
        """
        if self.connectivity is not None:
            return self.connectivity.get_measure_points_selection_gid()
        else:
            return super(TimeSeriesRegionFramework, self).get_measure_points_selection_gid()



class TimeSeriesSurfaceFramework(time_series_data.TimeSeriesSurfaceData, TimeSeriesFramework):
    """ This class exists to add framework methods to TimeSeriesSurfaceData. """

    SELECTION_LIMIT = 100

    def get_space_labels(self):
        """
        Return only the first `SELECTION_LIMIT` vertices/channels
        """
        return ['signal-%d' % i for i in xrange(min(self._length_3d, self.SELECTION_LIMIT))]



class TimeSeriesVolumeFramework(time_series_data.TimeSeriesVolumeData, TimeSeriesFramework):
    """
    This class exists to add framework methods to TimeSeriesVolume DataType.
    These methods will be later used by TS-Volume Viewer.
    """

    def get_rotated_volume_slice(self, from_idx, to_idx):
        """
        :param from_idx: int This will be the limit on the first dimension (time)
        :param to_idx: int Also limit on the first Dimension (time)
        :return: Multidimensional matrix (4D). Represents a part from the entire TS, cut over the first
                dimension (time) by the bounds given as inputs, and with the last dimension rotated to get
                a better view of the brain.
        """

        from_idx, to_idx = int(from_idx), int(to_idx)
        overall_shape = self.read_data_shape()

        if from_idx > to_idx or to_idx > overall_shape[0] or from_idx < 0:
            msg = "Bad time indexes: From {0} to {1}".format(from_idx, to_idx)
            raise exceptions.ValidationException(msg)

        slices = (slice(from_idx, to_idx), slice(overall_shape[1]), slice(overall_shape[2]), slice(overall_shape[3]))
        slices = self.read_data_slice(tuple(slices))
        slices = slices[..., ::-1]
        return slices


    def get_volume_view(self, from_idx, to_idx, x_plane, y_plane, z_plane):
        """
        :param from_idx: int This will be the limit on the first dimension (time)
        :param to_idx: int Also limit on the first Dimension (time)
        :param x_plane: int
        :param y_plane: int
        :param z_plane: int

        :return: An array of 3 Matrices 2D, each containing the values to display in planes xy, yz and xy.
        """

        from_idx, to_idx = int(from_idx), int(to_idx)
        x_plane, y_plane, z_plane = int(x_plane), int(y_plane), int(z_plane)
        overall_shape = self.read_data_shape()

        if from_idx > to_idx or to_idx > overall_shape[0] or from_idx < 0:
            msg = "Time indexes out of boundaries: from {0} to {1}".format(from_idx, to_idx)
            raise exceptions.ValidationException(msg)

        if x_plane > overall_shape[1] or y_plane > overall_shape[2] or z_plane > overall_shape[3]:
            msg = "Coordinates out of boundaries: {0}, {1}, {2}".format(x_plane, y_plane, z_plane)
            raise exceptions.ValidationException(msg)

        slices = (slice(from_idx, to_idx), slice(overall_shape[1]), slice(overall_shape[2]), slice(overall_shape[3]))
        slices = self.read_data_slice(tuple(slices))
        slices = slices[..., ::-1]
        slicex = slices[..., z_plane].tolist()
        slicey = slices[:, x_plane, ...].tolist()
        slicez = slices[..., y_plane, :].tolist()
        return [slicex, slicey, slicez]


    def get_voxel_time_series(self, x, y, z):
        """
        :param x: int coordinate
        :param y: int coordinate
        :param z: int coordinate

        :return: A complex dictionary with information about current voxel.
                The main part will be a vector with all the values from the x,y,z coordinates, in time.
        """
        x, y, z = int(x), int(y), int(z)
        overall_shape = self.read_data_shape()

        if x > overall_shape[1] or y > overall_shape[2] or z > overall_shape[3]:
            msg = "Coordinates out of boundaries: [x,y,z] = [{0}, {1}, {2}]".format(x, y, z)
            raise exceptions.ValidationException(msg)

        slices = slice(overall_shape[0]), slice(x, x + 1), slice(y, y + 1), slice(overall_shape[3])
        slices = self.read_data_slice(slices)
        slices = slices[..., ::-1]
        slices = slices[..., z].flatten()

        result = dict(data=slices.tolist(),
                      max=float(max(slices)),
                      min=float(min(slices)),
                      mean=float(numpy.mean(slices)),
                      median=float(numpy.median(slices)),
                      variance=float(numpy.var(slices)),
                      deviation=float(numpy.std(slices)))
        return result

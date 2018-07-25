# -*- coding: utf-8 -*-
"""
This module defines :class:`DataObject`, the abstract base class
used by all :module:`neo.core` classes that can contain data (i.e. are not container classes).
It contains basic functionality that is shared among all those data objects.

"""
import copy

import quantities as pq
import numpy as np

from neo.core.baseneo import BaseNeo, _check_annotations    # TODO: Deos this make sense? Should the _ be removed?
#import neo.core.basesignal # import BaseSignal


# TODO: Add array annotations to all docstrings
# TODO: Documentation
class DataObject(BaseNeo, pq.Quantity):

    # TODO: Do the _new_... functions also need to be changed?
    def __init__(self, name=None, description=None, file_origin=None, array_annotations=None,
                 **annotations):
        """
        This method is called from each data object and initializes the newly created object by adding array annotations
        and calling __init__ of the super class, where more annotations and attributes are processed.
        """

        if array_annotations is None:
            self.array_annotations = {}
        else:
            self.array_annotate(**self._check_array_annotations(array_annotations))

        BaseNeo.__init__(self, name=name, description=description, file_origin=file_origin, **annotations)

    # TODO: Okay to make it bound to instance instead of static like _check_annotations?
    def _check_array_annotations(self, value):  # TODO: Is there anything else that can be checked here?

        """
        Recursively check that value is either an array or list containing only "simple" types (number, string,
        date/time) or is a dict of those.
        """

        # First stage, resolve dict of annotations into single annotations
        if isinstance(value, dict):
            for key in value.keys():
                if isinstance(value[key], dict):
                    raise ValueError("Nested dicts are not allowed as array annotations")  # TODO: Is this really the case?
                value[key] = self._check_array_annotations(value[key])

        elif value is None:
            raise ValueError("Array annotations must not be None")
        # If not array annotation, pass on to regular check and make it a list, that is checked again
        # This covers array annotations with length 1
        # TODO: Should this be like this or just raise an Error?
        elif not isinstance(value, (list, np.ndarray)):
            _check_annotations(value)
            value = self._check_array_annotations(np.array([value]))

        # If array annotation, check for correct length, only single dimension and
        else:
            # TODO: Are those assumptions correct?
            # Number of items is last dimension in current objects
            try:
                own_length = self.shape[-1]
            # FIXME This is because __getitem__[scalar] returns a scalar Epoch/Event/SpikeTrain
            # To be removed when __getitem__[scalar] is 'fixed'
            except IndexError:
                    own_length = 1

            # Escape check if empty array or list and just annotate an empty array
            # TODO: Does this make sense?
            if len(value) == 0:
                if isinstance(value, np.ndarray):
                    # Uninitialized array annotation containing default values (i.e. 0, '', ...)
                    # Quantity preserves units
                    if isinstance(value, pq.Quantity):
                        value = np.zeros(own_length, dtype=value.dtype)*value.units
                    # Simple array only preserves dtype
                    else:
                        value = np.zeros(own_length, dtype=value.dtype)

                else:
                    raise ValueError("Empty array annotation without data type detected. If you "
                                     "wish to create an uninitialized array annotation, please "
                                     "use a numpy.ndarray containing the data type you want.")
                val_length = own_length
            else:
                # Note: len(o) also works for np.ndarray, it then uses the outmost dimension,
                # which is exactly the desired behaviour here
                val_length = len(value)

            if not own_length == val_length:
                raise ValueError("Incorrect length of array annotation: {} != {}".
                                 format(val_length, own_length))

            for element in value:
                # Nested array annotations not allowed currently
                # So if an entry is a list or a np.ndarray, it's not allowed,
                # except if it's a quantity of length 1
                if isinstance(element, list) or \
                        (isinstance(element, np.ndarray) and not
                        (isinstance(element, pq.Quantity) and element.shape == ())):
                    raise ValueError("Array annotations should only be 1-dimensional")

                # Perform regular check for elements of array or list
                _check_annotations(element)

            # Create arrays from lists, because array annotations should be numpy arrays
            if isinstance(value, list):
                value = np.array(value)

        return value

    # TODO: Is it fine to allow them unpacked here and not elsewhere
    def array_annotate(self, **array_annotations):

        """
        Add annotations (non-standardized metadata) as arrays to a Neo data object.

        Example:

        >>> obj.array_annotate(key1=[value00, value01, value02], key2=[value10, value11, value12])
        >>> obj.key2[1]
        value11
        """

        array_annotations = self._check_array_annotations(array_annotations)
        self.array_annotations.update(array_annotations)

    def array_annotations_at_index(self, index):  # TODO: Should they be sorted by key (current) or index?

        """
        Return dictionary of array annotations at a given index or list of indices
        :param index: int, list, numpy array: The index (indices) from which the annotations are extracted
        :return: dictionary of values or numpy arrays containing all array annotations for given index

        Example:
        >>> obj.array_annotate(key1=[value00, value01, value02], key2=[value10, value11, value12])
        >>> obj.array_annotations_at_index(1)
        {key1=value01, key2=value11}
        """

        index_annotations = {}

        # Use what is given as an index to determine the corresponding annotations,
        # if not possible, numpy raises an Error
        for ann in self.array_annotations.keys():
            # NO deepcopy, because someone might want to alter the actual object using this
            index_annotations[ann] = self.array_annotations[ann][index]

        return index_annotations

    def rescale(self, units):

        # Use simpler functionality, if nothing will be changed
        dim = pq.quantity.validate_dimensionality(units)
        if self.dimensionality == dim:
            return self.copy()
        # The following are from BaseSignal.rescale, where I had the same implementation:
        # TODO: Check why it does not work with units=dim (dimensionality)!!!
        # TODO: Find out, how to validate units without altering them:
        # Raised error in validate_dimensionality???
        obj = self.duplicate_with_new_data(signal=self.view(pq.Quantity).rescale(dim), units=units)
        # Expected behavior is deepcopy, so trying this
        obj.array_annotations = copy.deepcopy(self.array_annotations)
        obj.segment = self.segment
        return obj

    # Needed to implement this so array annotations are copied as well, ONLY WHEN copying 1:1
    def copy(self, **kwargs):
        obj = super(DataObject, self).copy(**kwargs)
        obj.array_annotations = self.array_annotations
        return obj

    def as_array(self, units=None):
        """
        Return the object's data as a plain NumPy array.

        If `units` is specified, first rescale to those units.
        """
        if units:
            return self.rescale(units).magnitude
        else:
            return self.magnitude

    def as_quantity(self):
        """
        Return the object's data as a quantities array.
        """
        return self.view(pq.Quantity)

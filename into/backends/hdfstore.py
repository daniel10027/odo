from __future__ import absolute_import, division, print_function

import pandas as pd

import datashape
from datashape import discover
from ..append import append
from ..convert import convert, ooc_types
from ..chunks import chunks, Chunks
from ..resource import resource


HDFDataset = (pd.io.pytables.AppendableFrameTable, pd.io.pytables.FrameFixed)

@discover.register(pd.HDFStore)
def discover_hdfstore(f):
    return discover(dict((k.lstrip('/'), f.get_storer(k)) for k in f.keys()))


@discover.register(pd.io.pytables.Fixed)
def discover_hdfstore_storer(storer):
    f = storer.parent
    n = storer.shape
    measure = discover(f.select(storer.pathname, start=0, stop=10)).measure
    return n * measure


@convert.register(chunks(pd.DataFrame), HDFDataset)
def hdfstore_to_chunks_dataframes(data, chunksize=1000000, **kwargs):
    return chunks(pd.DataFrame)(data.parent.select(data.pathname, chunksize=chunksize))


from collections import namedtuple

EmptyHDFStoreDataset = namedtuple('EmptyHDFStoreDataset', 'parent,pathname,dshape')

@resource.register('hdfstore://.+\.hdf5', priority=11)
def resource_hdfstore(uri, datapath=None, dshape=None, **kwargs):
    # TODO:
    # 1. Support nested datashapes (e.g. groups)
    # 2. Try translating unicode to ascii?  (PyTables fails here)
    fn = uri.split('://')[1]
    f = pd.HDFStore(fn)
    if dshape is None:
        if datapath:
            return f.get_storer(datapath)
        else:
            return f
    dshape = datashape.dshape(dshape)

    # Already exists, return it
    if datapath in f:
        return f.get_storer(datapath)

    # Need to create new datast.
    # HDFStore doesn't support empty datasets, so we use a proxy object.
    return EmptyHDFStoreDataset(f, datapath, dshape)


@append.register((pd.io.pytables.Fixed, EmptyHDFStoreDataset), pd.DataFrame)
def append_dataframe_to_hdfstore(store, df, **kwargs):
    store.parent.append(store.pathname, df, append=True)
    return store.parent.get_storer(store.pathname)


@append.register((pd.io.pytables.Fixed, EmptyHDFStoreDataset),
                 chunks(pd.DataFrame))
def append_chunks_dataframe_to_hdfstore(store, c, **kwargs):
    parent = store.parent
    for chunk in c:
        parent.append(store.pathname, chunk)
    return parent.get_storer(store.pathname)


@append.register((pd.io.pytables.Fixed, EmptyHDFStoreDataset), object)
def append_object_to_hdfstore(store, o, **kwargs):
    return append(store, convert(chunks(pd.DataFrame), o, **kwargs), **kwargs)


ooc_types |= set(HDFDataset)

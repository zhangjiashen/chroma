import hnswlib
import pickle
import time
import os
import numpy as np
from chroma_server.index.abstract import Index
from chroma_server.logger import logger


class Hnswlib(Index):

    _model_space = None
    _index = None
    _index_metadata = {
        'dimensionality': None,
        'elements': None,
        'time_created': None,
    }

    _id_to_uuid = {}
    _uuid_to_id = {}

    def __init__(self):
        pass

    def run(self, model_space, uuids, embeddings):
        # more comments available at the source: https://github.com/nmslib/hnswlib
        dimensionality = len(embeddings[0])
        ids = []
        i = 0

        for uuid in uuids:
            ids.append(i)
            self._id_to_uuid[i] = str(uuid)
            self._uuid_to_id[str(uuid)] = i
            i += 1

        index = hnswlib.Index(space='l2', dim=dimensionality) # possible options are l2, cosine or ip
        index.init_index(max_elements=len(embeddings), ef_construction=100, M=16) 
        index.set_ef(10) 
        index.set_num_threads(4) 
        index.add_items(embeddings, ids)

        self._index = index
        self._model_space = model_space
        self._index_metadata = {
            'dimensionality': dimensionality,
            'elements': len(embeddings) ,
            'time_created': time.time(),
        }
        self.save()
        
    def save(self):
        if self._index is None:
            return
        self._index.save_index(f"/index_data/index_{self._model_space}.bin")

        # pickle the mappers
        with open(f"/index_data/id_to_uuid_{self._model_space}.pkl", 'wb') as f:
            pickle.dump(self._id_to_uuid, f, pickle.HIGHEST_PROTOCOL)
        with open(f"/index_data/uuid_to_id_{self._model_space}.pkl", 'wb') as f:
            pickle.dump(self._uuid_to_id, f, pickle.HIGHEST_PROTOCOL)
        with open(f"/index_data/index_metadata_{self._model_space}.pkl", 'wb') as f:
            pickle.dump(self._index_metadata, f, pickle.HIGHEST_PROTOCOL)

        logger.debug('Index saved to /index_data/index.bin')

    def load(self, model_space):
        # unpickle the mappers
        with open(f"/index_data/id_to_uuid_{model_space}.pkl", 'rb') as f:
            self._id_to_uuid = pickle.load(f)
        with open(f"/index_data/uuid_to_id_{model_space}.pkl", 'rb') as f:
            self._uuid_to_id = pickle.load(f)
        with open(f"/index_data/index_metadata_{model_space}.pkl", 'rb') as f:
            self._index_metadata = pickle.load(f)

        p = hnswlib.Index(space='l2', dim= self._index_metadata['dimensionality'])
        self._index = p
        self._index.load_index(f"/index_data/index_{model_space}.bin", max_elements= self._index_metadata['elements'])

        self._model_space = model_space

    # do knn_query on hnswlib to get nearest neighbors
    def get_nearest_neighbors(self, model_space, query, k, uuids=None):

        if self._model_space != model_space:
            self.load(model_space)

        s2= time.time()
        # get ids from uuids
        ids = []
        for uuid in uuids:
            ids.append(self._uuid_to_id[uuid])

        filter_function = None
        if not ids is None:
            filter_function = lambda id: id in ids

        if len(ids) < k:
            k = len(ids)
        print('time to pre process our knn query: ', time.time() - s2)

        s3= time.time()
        database_ids, distances = self._index.knn_query(query, k=k, filter=filter_function)
        print('time to run knn query: ', time.time() - s3)

        # get uuids from ids    
        uuids = []
        for id in database_ids[0]:
            uuids.append(self._id_to_uuid[id])
        
        return uuids, distances

    def reset(self):
        for f in os.listdir('/index_data'):
            os.remove(os.path.join('/index_data', f))
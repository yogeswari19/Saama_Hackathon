from multiprocessing import Manager
manager = Manager()
stream_queues = manager.dict()

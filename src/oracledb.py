import cx_Oracle
import os
import yaml
from pathlib import Path
home = str(Path.home())

def process_yaml():
	with open("config.yaml") as file:
		return yaml.safe_load(file)


class OracleJSONDatabaseConnection:
    def __init__(self, data=process_yaml()):
        # wallet location (default is HOME/wallets/wallet_X)
        os.environ['TNS_ADMIN'] = '{}/{}'.format(home, process_yaml()['WALLET_DIR'])
        print(os.environ['TNS_ADMIN'])
        self.pool = cx_Oracle.SessionPool(data['db']['username'], data['db']['password'], data['db']['dsn'],
            min=1, max=4, increment=1, threaded=True,
            getmode=cx_Oracle.SPOOL_ATTRVAL_WAIT
        )
        print('Connection successful.')



    def close_pool(self):
        self.pool.close()
        print('Connection pool closed.')



    def insert(self, collection_name, json_object_to_insert):
        connection = self.pool.acquire()
        connection.autocommit = True
        soda = connection.getSodaDatabase()
        x_collection = soda.createCollection(collection_name)

        try:
            x_collection.insertOne(json_object_to_insert)
            print('[DBG] INSERT {} OK'.format(json_object_to_insert))
        except cx_Oracle.IntegrityError:
            print('[DBG] INSERT {} ERR'.format(json_object_to_insert))
            return 0
        self.pool.release(connection)
        return 1



    def delete(self, collection_name, on_column, on_value):
        connection = self.pool.acquire()
        soda = connection.getSodaDatabase()
        x_collection = soda.createCollection(collection_name)
        qbe = {on_column: on_value}
        x_collection.find().filter(qbe).remove()
        self.pool.release(connection)



def test_class():
    object = OracleJSONDatabaseConnection()
    print(object.pool)
    object.close_pool()



if __name__ == '__main__':
    test_class()

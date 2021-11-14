'''
This code connects to the Autonomous DB using TLS (no wallet required) as explained by Todd Sharp here:
https://blogs.oracle.com/developers/post/securely-connecting-to-autonomous-db-without-a-wallet-using-tls
'''

import cx_Oracle
import yaml

def process_yaml():
	with open('../config.yaml') as file:
		return yaml.safe_load(file)



def main():
    data = process_yaml()
    try:
        cx_Oracle.SessionPool(data['db']['username'], data['db']['password'], data['db']['dsn'],
            min=1, max=4, increment=1, threaded=True,
            getmode=cx_Oracle.SPOOL_ATTRVAL_WAIT
        )
    except cx_Oracle.DatabaseError as e:
        print(e)
    print('Connection successful.')



if __name__ == '__main__':
    main()
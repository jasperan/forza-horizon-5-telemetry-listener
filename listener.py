import logging
import socket
import datetime as dt
from src.data_packet import ForzaDataPacket
import argparse
from src.oracledb import OracleJSONDatabaseConnection

cli_parser = argparse.ArgumentParser(
    description="script that grabs data from a Forza Horizon 5 stream and dumps it to a CSV file"
)

cli_parser.add_argument('-p', '--port', type=int, help='port number to listen on', default=65530)
cli_parser.add_argument('-v', '--verbose', action='store_true', help='display logs', default=False)
cli_parser.add_argument('-f', '--output-filename', default='out.log')
cli_parser.add_argument('-m', '--mode', choices=['race', 'always'], help='when to log: always or only during races.', default='always')
args = cli_parser.parse_args()



def to_str(value):
    if isinstance(value, float):
        return('{:f}'.format(value))

    return('{}'.format(value))



def dump_stream(port):

    # Get connection to db.
    dbhandler = OracleJSONDatabaseConnection()
    
    params = ForzaDataPacket.get_props()

    log_wall_clock = False
    if 'wall_clock' in params:
        log_wall_clock = True


    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('', port))

    logging.info('PORT {} LISTEN'.format(port))

    n_packets = 0
    
    while True:
        message, address = server_socket.recvfrom(1024)
        del address
        fdp = ForzaDataPacket(message)
        fdp.wall_clock = dt.datetime.now()

        # Get all properties
        properties = fdp.get_props()
        # Get parameters
        data = fdp.to_list(params)
        assert len(data) == len(properties)
        # Zip into a dictionary
        fd_dict = dict(zip(properties, data))
        # Add timestamp
        fd_dict['timestamp'] = str(fdp.wall_clock)

        # only log if it's in a race.
        if args.mode == 'race':
            if fdp.is_race_on:
                if n_packets == 0:
                    logging.info('{}: in race, logging data'.format(dt.datetime.now()))
                
                #logging.debug(fd_dict)
                dbhandler.insert('data', fd_dict)


                n_packets += 1
                if n_packets % 60 == 0:
                    logging.info('{}: logged {} packets'.format(dt.datetime.now(), n_packets))
            else:
                if n_packets > 0:
                    logging.info('{}: out of race, stopped logging data'.format(dt.datetime.now()))
                n_packets = 0

        elif args.mode == 'always':
            #logging.debug(fd_dict)
            dbhandler.insert('data', fd_dict)



def main():
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    dump_stream(args.port)



if __name__ == "__main__":
    main()
    
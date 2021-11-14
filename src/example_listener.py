
import socket


localIP = "127.0.0.1"
localPort = 65530
bufferSize = 1024

# Create a datagram socket
UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

 

# Bind to address and ip
UDPServerSocket.bind((localIP, localPort)) 

print("UDP server up and listening")

 

# Listen for incoming datagrams

while(True):
    bytesAddressPair = UDPServerSocket.recvfrom(bufferSize)
    message = bytesAddressPair[0]
    address = bytesAddressPair[1]

    print("Message from Client: {} {} {}".format(str(message), type(str(message)), str(message).encode('ascii').decode("utf-8")))
    #print("Client IP Address: {}".format(address))

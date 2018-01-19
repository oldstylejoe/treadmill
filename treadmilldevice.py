#Joe Snider
#4/14
#
#Interface into the treadmill's ForceLink Motion server

import socket
import xml.etree.ElementTree as ET
from collections import OrderedDict
import Queue
import threading
from copy import deepcopy

from time import time

import FLMOCommands

connectionString = "laVNJL0MWIlQYMua17U4Ycrl5bVrQGuDcTjlBzHqPgZl2G6kp+9C3ir9h/3d9JtgsgP6t18HWLFCytjxsgBnLmuPQcEMbDdCsiD9hKOZ/Us0wRHOqjGe7yngK8KTaFiXHPAz5WxcgVbnrIS9OLomxBsJPHNac5OUoBRHkzr0jwyCyQUQR/vTMqEraGB2D1vkOdPZxdvNFndV3mOURMbd39/qQ7LcW2G8hymSynAcHC57KhfTFbKsAbBijWWndt103YlCn7Vz++JQzzabueppPL8a0/7fPfNlDobjpZaQX5C88/2zT3teljxdSnt5Vq1cvaiP15/yLR8VHC1IPxLZ6A=="
#timeout the connection attempt after this long
CONNECTION_TIMEOUT = 5#s

#the connection string is handled separately
MAX_CONNECTION_RESP_LENGTH = 20*4096

#buffer size for the socket read (power of 2 is best)
READSIZE = 4096

#the treadmill goes pretty slow (~20Hz), so no need to sample too fast
SAMPLE_TIME = 0.01#secs 1.0/21.0 #secs

class CommandTreadMill:
    #Create these and put them on the treadmill command queue
    # to run things (T.command.put(...)
    CONNECT, SEND, CLOSE = range(300, 303)
    def __init__(self, command, data=None):
        self.command = deepcopy(command)
        self.data = FLMOCommands.FLMOcr()
        if data is not None:
            try:
                self.data["rq"] = deepcopy(data["rq"])
                self.data["id"] = deepcopy(data["id"])
                self.data["v"] = deepcopy(data["v"])
            except(KeyError):
                print "Warning: data for commands must have access to [] access to rq, d, and v text elements ... defaulting to all zero"
                self.data["rq"] = 0
                self.data["id"] = 0
                self.data["v"] = 0

class CTreadMillDevice(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.address = '137.110.243.239'
        self.port = 8082

        print "Creating socket...",
        self.sc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print "Opening socket...",
        self.sc.connect((self.address, self.port))
        self.sc.setblocking(0)
        print "done"

        self.connected = False
        
        self.eventStop = threading.Event()
        self.eventStop.set()

        self.received = Queue.Queue()
        self.command = Queue.Queue()

        self.handlers = {
            CommandTreadMill.CONNECT : self.__handle_CONNECT,
            CommandTreadMill.SEND : self.__handle_SEND,
            CommandTreadMill.CLOSE : self.__handle_CLOSE,
        }
        
        #use this to echo the commands
        self.verbose = False

    #parse out the values we need for the 

    def __handle_CONNECT(self, dummy):
        if self.connected:
            print "Already connected ... ignoring connection request"
            return

        dc = OrderedDict()
        dc["rq"] = FLMOCommands.FLMO.SendConnectionString
        dc["id"] = "0"
        dc["v"] = "0"
        dc["string"] = connectionString
        self.__send(dc)

        self.sc.settimeout(CONNECTION_TIMEOUT)
        try:
            self.resp = self.sc.recv(MAX_CONNECTION_RESP_LENGTH)
            while self.resp[len(self.resp)-1] != '\x03':
                self.resp += self.sc.recv(MAX_CONNECTION_RESP_LENGTH)
            self.setupValues = ET.fromstring(self.resp[4:(len(self.resp)-1)])
            self.connected = True
        except(socket.timeout):
            self.sendError("Error: connection response timed out ... check that the treadmill is powered.")
        self.sc.settimeout(0)

    def __handle_CLOSE(self, dummy):
        self.connected = False
        self.eventStop.clear()
        self.received.join()
        self.command.join()
        self.sc.shutdown(socket.SHUT_RDWR)

    def run(self):
        while self.eventStop.isSet():
            #testing only
            t = time()
            
            #check for read
            try:
                out = ""
                while len(out)==0 or out[len(out)-1] != '\x03':
                    out += self.sc.recv(READSIZE)
                    #TODO: throw some error if out gets too big
                vals = out[4:(len(out)-1)].split('\x03\x02')
                for v in vals:
                    #not sure where the \0's are coming from (transmit errors??)
                    vv = v.replace("\x00", "")
                    if len(vv) > 0:
                        self.received.put(vv)
            except(socket.error):
                pass #nothing to read

            try:
                cmd = self.command.get(True, SAMPLE_TIME)
                self.handlers[cmd.command](cmd.data)
            except(Queue.Empty):
                pass
            except(KeyError):
                self.sendError("Error: unkown command"+str(cmd.command))
                
            q = time()-t
            if q > 2.0 * SAMPLE_TIME:
                self.sendError("Warning (treadmilldevice.py): TCP/IP read thread is bogging down ... occasional sitings of this error can be ignored")
            #print "treadmilldevice.py thread time:",q

    def join(self, timeout=None):
        self.eventStop.clear()
        threading.Thread.join(self, timeout)
            
    def __handle_SEND(self, data):
        #nothing to do if not connected (could throw and error?)
        if not self.connected:
            return
        
        #data should be a valid FLMOcr object
        self.__send(data)
        

    def __send(self, dc):
        tosend = ET.Element("FLMOcr")
        #only need one level
        for tag,content in dc.iteritems():
            if content != None:
                ET.SubElement(tosend, tag).text=content
        self.out = "\x02\xef\xbb\xbf"+ET.tostring(tosend)+"\x03"
        self.sc.sendall(self.out)
        if self.verbose:
            print "Sent command:", self.out

    #handle errors (could be QT popup)
    def sendError(self, err):
        print err
        
        
if __name__ == "__main__":
    TM1 = CTreadMillDevice()
    #TM1.connect()
    #TM1.disconnect()
    TM1.start()
    
    print "Command line testing: commandTM1(<char>), where <char> is"
    print "  c to connect, x to quit, r to check messages, w to test: "
    print "Have to run connect first to do much of anything"
    def commandTM1(s):
        if s == "x":
            TM1.command.put(CommandTreadMill(CommandTreadMill.CLOSE))
            print "Joining treadmill thread ... "
            TM1.join()
            print "Threadmill thread done"
        if s == "r":
            try:
                print TM1.received.get(False)
            except(Queue.Empty):
                pass

        if s == "c":
            cm = CommandTreadMill(CommandTreadMill.CONNECT)
            TM1.command.put(cm, False)


    

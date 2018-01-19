#Joe Snider
#5/14
#
#Send and receive commands (this could be in Vizard?)
#This is specialized for the Poizner lab treadmill

import xml.etree.ElementTree as ET
import treadmilldevice
import FLMOCommands as F
import Queue
#from xmltodict import parse, ParsingInterrupted

CTM = treadmilldevice.CommandTreadMill
ETF = ET.fromstring

#this is to help parse the reads
#Note that it is specialized for the plab treadmill
class Measurement:
    def __init__(self):
        self.time = 0.
        self.value = 0.
class MotionObject:
    def __init__(self):
        self.leftBeltPosition = Measurement()
        self.leftBeltSpeed = Measurement()
        self.rightBeltPosition = Measurement()
        self.rightBeltSpeed = Measurement()

class Treadmill:
    def __init__(self):
        print "Starting the treadmill thread ...",
        self.TM = treadmilldevice.CTreadMillDevice()
        self.TM.start()
        print "done"
        
        #this is for sending commands
        self.Motors = {}
        #this is for receiving commands (map from 'id' to appropriate treadmill value)
        #specialized for plab
        self.plabTreadmill = MotionObject()
        self.MotorResponses = {}

        cm = CTM(CTM.CONNECT)
        self.TM.command.put(cm, False)
        
        self.device_to_si = 0.0


    def parseConfig(self):
        for d in self.TM.setupValues.findall(".//FLMODevice"):
            name = d.find("mFLMO")
            if name is not None and name.text == "TreadMill":
                self.ID = d.find("mID").text
                print "Found Treadmill ID", self.ID
        
        for a in self.TM.setupValues.findall(".//FLMOAxis"):
            self.Motors[a.find("Name").text] = F.Axis()
            self.Motors[a.find("Name").text].ID = a.find("mID").text
            for b in a.findall(".//FLMOParameter"):
                #everything else has some id, but this flag, & with the following to get flag values
                # 1 -> 0 for output, 1 for input
                # 2 -> AskToCorrect - check the default value (pops up a window)
                # 4 -> IsActive
                # 8 -> IsSetPoint?
                # 16 -> AlwaysUpdate?
                # 32 -> ShowValueInStatus?
                flag = 0
                try:
                    flag = int(b.find("Flags").text)
                except(ValueError):
                    pass

                #for converting to/from si units (meters, radians?)
                si = 1.0
                try:
                    si = float(b.find("FromDeviceToSI").text)
                except(ValueError):
                    pass
                
                #what we look for here is specialized for the plab treadmill (hackish)
                if b.find("FLMOParameterUse").text == "speed" and (flag&1)==1:
                    self.Motors[a.find("Name").text].setSpeedID = b.find("mID").text
                    self.Motors[a.find("Name").text].SI_to_speed = 1.0/si
                    self.device_to_si = si
                    if a.find("Name").text == "LeftBelt":
                        self.MotorResponses[b.find("mID").text] = self.plabTreadmill.leftBeltSpeed
                    elif a.find("Name").text == "RightBelt":
                        self.MotorResponses[b.find("mID").text] = self.plabTreadmill.rightBeltSpeed
                elif b.find("FLMOParameterUse").text == "speed" and (flag&1)==0:
                    self.Motors[a.find("Name").text].getSpeedID = b.find("mID").text
                    if a.find("Name").text == "LeftBelt":
                        self.MotorResponses[b.find("mID").text] = self.plabTreadmill.leftBeltSpeed
                    elif a.find("Name").text == "RightBelt":
                        self.MotorResponses[b.find("mID").text] = self.plabTreadmill.rightBeltSpeed
                elif b.find("FLMOParameterUse").text == "accelleration":
                    self.Motors[a.find("Name").text].setAccelerationID = b.find("mID").text
                elif b.find("FLMOParameterUse").text == "position"  and (flag&1)==0:
                    self.Motors[a.find("Name").text].getPositionID = b.find("mID").text
                    if a.find("Name").text == "LeftBelt":
                        self.MotorResponses[b.find("mID").text] = self.plabTreadmill.leftBeltPosition
                    elif a.find("Name").text == "RightBelt":
                        self.MotorResponses[b.find("mID").text] = self.plabTreadmill.rightBeltPosition

    #def readResponse(self):
    #    #mostly testing version
    #    try:
    #        self.lastResponse = self.TM.received.get(False)
    #        print "test response",self.lastResponse
    #    except(Queue.Empty):
    #        pass
    #will block until the queue is empty
    def readAllResponse(self):
        ret = []
        try:
            while True:
                self.lastResponse = self.TM.received.get(False)
                #this may be slow??
                try:
                    q = ET.fromstring(self.lastResponse)
                    ret.append(q)
                except(ET.ParseError):
                    print "Warning (treadmill): could not parse"
                    print "   ",self.lastResponse
                    print "into valid XML ... ignoring"
        except(Queue.Empty):
            pass
        return ret
        
    def LiftSuspend(self):
        cmd = F.FLMOcr()
        cmd["rq"] = F.FLMO.DeviceCommand
        cmd["id"] = self.ID
        cmd["v"] = F.DeviceCommands.LiftSuspend
        self.TM.command.put(CTM(CTM.SEND,cmd))
    def Suspend(self):
        cmd = F.FLMOcr()
        cmd["rq"] = F.FLMO.DeviceCommand
        cmd["id"] = self.ID
        cmd["v"] = F.DeviceCommands.Suspend
        self.TM.command.put(CTM(CTM.SEND,cmd))
    def StartAll(self):
        cmd = F.FLMOcr()
        cmd["rq"] = F.FLMO.DeviceCommand
        cmd["id"] = self.ID
        cmd["v"] = F.DeviceCommands.StartAll
        self.TM.command.put(CTM(CTM.SEND,cmd))
    def Reset(self):
        cmd = F.FLMOcr()
        cmd["rq"] = F.FLMO.DeviceCommand
        cmd["id"] = self.ID
        cmd["v"] = F.DeviceCommands.Reset
        self.TM.command.put(CTM(CTM.SEND,cmd))
    def Synchronize(self):
        cmd = F.FLMOcr()
        cmd["rq"] = F.FLMO.Synchronize
        cmd["id"] = self.ID
        cmd["v"] = '0'
        self.TM.command.put(CTM(CTM.SEND,cmd))

    def stop(self):
        self.TM.command.put(CTM(CTM.CLOSE))

    #use these to drive the belts
    def MoveBothBelts(self, spd=0):
        self.Motors['LeftBelt'].SetSpeed(spd)
        self.Motors['RightBelt'].SetSpeed(spd)
        self.TM.command.put(CTM(CTM.SEND, self.Motors['LeftBelt']))
        self.TM.command.put(CTM(CTM.SEND, self.Motors['RightBelt']))
    def MoveLeftBelt(self, spd=0):
        self.Motors['LeftBelt'].SetSpeed(spd)
        self.TM.command.put(CTM(CTM.SEND, self.Motors['LeftBelt']))
    def MoveRightBelt(self, spd=0):
        self.Motors['RightBelt'].SetSpeed(spd)
        self.TM.command.put(CTM(CTM.SEND, self.Motors['RightBelt']))
        
    #for some reason this is not in si units. 900 is the default        
    def SetLeftBeltAcceleration(self, mpss=900):
        self.Motors['LeftBelt'].SetAcceleration(mpss)
        self.TM.command.put(CTM(CTM.SEND, self.Motors['LeftBelt']))
    def SetRightBeltAcceleration(self, mpss=900):
        self.Motors['RightBelt'].SetAcceleration(mpss)
        self.TM.command.put(CTM(CTM.SEND, self.Motors['RightBelt']))

    #these seem to be ok if called no more than once every treadmill frame
    # strange results otherwise (use subscription below to keep them up to date)
    def ReadBothBeltsSpeed(self):
        self.Motors['LeftBelt'].ReadSpeed()
        self.Motors['RightBelt'].ReadSpeed()
        self.TM.command.put(CTM(CTM.SEND, self.Motors['LeftBelt']))
        self.TM.command.put(CTM(CTM.SEND, self.Motors['RightBelt']))
    def ReadBothBeltsPosition(self):
        self.Motors['LeftBelt'].ReadPosition()
        self.Motors['RightBelt'].ReadPosition()
        self.TM.command.put(CTM(CTM.SEND, self.Motors['LeftBelt']))
        self.TM.command.put(CTM(CTM.SEND, self.Motors['RightBelt']))

    def SubscribeBothBeltsSpeed(self):
        self.Motors['LeftBelt'].SubscribeSpeed()
        self.Motors['RightBelt'].SubscribeSpeed()
        self.TM.command.put(CTM(CTM.SEND, self.Motors['LeftBelt']))
        self.TM.command.put(CTM(CTM.SEND, self.Motors['RightBelt']))
    def SubscribeBothBeltsPosition(self):
        self.Motors['LeftBelt'].SubscribePosition()
        self.Motors['RightBelt'].SubscribePosition()
        self.TM.command.put(CTM(CTM.SEND, self.Motors['LeftBelt']))
        self.TM.command.put(CTM(CTM.SEND, self.Motors['RightBelt']))
        

if __name__ == "__main__":
    T1 = Treadmill()

    #these require delays, but will start up the machine
    #wait for sounds (TODO: should be able to read status and continue when ready)
    resp = raw_input("any key to read status")
    T1.parseConfig()

    resp = raw_input("hit s to start motors (any else to skip)")
    if resp == "s":
        T1.StartAll()

    print "Wait a bit, then commands can be sent"
    
    import viz
    viz.go()


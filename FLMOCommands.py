#Joe Snider
#5/14
#
#Store interface for commands to send to the treadmill

from collections import OrderedDict

#just store the commands
class FLMO:
    GetConfiguration = "10"
    SendConnectionString = "11"
    ReqActualValue = "12"
    SetNewValue = "13"
    SetIDCFile = "13"
    SetHpMode = "15"
    DeviceCommand = "16"
    AxisCommand = "17"
    Synchronize = "18"
    Subscribe = "19"
    #nothing = "20" ??
    KickDog = "21" #?? what is this

class AxisCommands:
    Nothing = "0"
    Enable = "1"
    Disable = "2"
    NewSetPoint = "3"
    Home = "4"

class DeviceCommands:
    Nothing = "0"
    Reset = "1"
    Suspend = "2"
    LiftSuspend = "3"
    StartAll = "4"
    Diagnose = "5"
    
class ServerMessages:
    Configuration = "10"
    ActualValue = "11"
    StatusUpdate = "12"
    ErrorMessage = "13"
    SetValue = "14"
    Synchronize = "18"

class FLMOcr(OrderedDict):
    def __init__(self, RQ="0", ID="0", V="0"):
        OrderedDict.__init__(self)
        #this is the general format
        self["rq"] = RQ
        self["id"] = ID
        self["v"] = V
        #self["ob"] = None #not yet implemented by ForceLink?

    def GetConfiguration(self):
        self["rq"] = FLMO.GetConfiguration
        self["id"] = 0
        self["v"] = 0

#this class just builds commands
#actual send should occur elsewhere (just send this to the threaded
# device interface).
class Axis(FLMOcr):
    def __init__(self):
        FLMOcr.__init__(self)
        self.name = ""
        self.good = False

        self.ID = '0'
        
        self.setSpeedID = '0'
        self.getSpeedID = '0'
        self.setAccelerationID = '0'
        self.getPositionID = '0'
        
        self.SI_to_speed = 0.0
        #self.speed_to_SI = 0.0

        self.lastRead = '0'

    #start and stop
    def Enable(self):
        self["rq"] = FLMO.AxisCommand
        self["id"] = self.ID
        self["v"] = AxisCommands.Enable
    def Disable(self):
        self["rq"] = FLMO.AxisCommand
        self["id"] = self.ID
        self["v"] = AxisCommands.Disable
    def NewSetPoint(self):
        self["rq"] = FLMO.AxisCommand
        self["id"] = self.ID
        self["v"] = AxisCommands.NewSetPoint
    def Home(self):
        self["rq"] = FLMO.AxisCommand
        self["id"] = self.ID
        self["v"] = AxisCommands.Home

    #value is in meters per second
    def SetSpeed(self, mps=0):
        self["rq"] = FLMO.SetNewValue
        self["id"] = self.setSpeedID
        self["v"] = str(int(round(mps*self.SI_to_speed)))

    def ReadSpeed(self):
        self["rq"] = FLMO.ReqActualValue
        self["id"] = self.getSpeedID
        self["v"] = '0'

    #not in SI? not sure what this does
    #900 is the default (wimpy) acceleration
    def SetAcceleration(self, mpss=0):
        self["rq"] = FLMO.SetNewValue
        self["id"] = self.setAccelerationID
        self["v"] = str(mpss)
        
    #read the position in meters
    def ReadPosition(self):
        self["rq"] = FLMO.ReqActualValue
        self["id"] = self.getPositionID
        self["v"] = '0'
        
    def SubscribePosition(self):
        self["rq"] = FLMO.Subscribe
        self["id"] = self.getPositionID
        self["v"] = '20'
    def SubscribeSpeed(self):
        self["rq"] = FLMO.Subscribe
        self["id"] = self.setSpeedID
        self["v"] = '20'
        
        

#Joe Snider
#7/14
#
#read in the treadmill foreplate data

import viz
import u6
import math
import viztask
import numpy as np

MIN_WEIGHT_NEWTONS = -100# ~20 lbs, negetive for downward gravity

LEFT_OFF_TREADMILL = viz.getEventID('LEFT_OFF_TREADMILL')
LEFT_ON_TREADMILL = viz.getEventID('LEFT_ON_TREADMILL')
RIGHT_OFF_TREADMILL = viz.getEventID('RIGHT_OFF_TREADMILL')
RIGHT_ON_TREADMILL = viz.getEventID('RIGHT_ON_TREADMILL')

class CTreadmillForcePlate():
	def __init__(self):
		self.device = u6.U6()
		print self.device.configU6()
		
		#for the labjack
		self.numChannels = 12
		self.firstChannel = 2
		self.resolutionIndex = 4
		self.gainIndex = 0
		self.settlingFactor = 0
		self.differential = False
		
		self.latestAinValues = np.array([0]*self.numChannels, dtype='float')
		self.lastForceMoments = np.array([0]*self.numChannels, dtype='float')
		self.latestForceMoments = np.array([0]*self.numChannels, dtype='float')
		self.zero = np.array([0]*self.numChannels, dtype='float')
		
		self.lastTime = 0
		self.latestTime = 0
		
		self.lastLeftOn = False
		self.latestLeftOn = False
		self.lastLeftCOP = [0, 0]
		self.latestLeftCOP = [0, 0]

		self.lastRightOn = False
		self.latestRightOn = False
		self.lastRightCOP = [0, 0]
		self.latestRightCOP = [0, 0]
		
		FIOEIOAnalog = ( 2 ** self.numChannels ) - 1;
		fios = FIOEIOAnalog & (0xFF)
		eios = FIOEIOAnalog/256
		self.device.getFeedback(u6.PortDirWrite(Direction = [0, 0, 0], WriteMask = [0, 0, 15]))
		self.feedbackArguments = []
		self.feedbackArguments.append(u6.DAC0_8(Value = 125))
		self.feedbackArguments.append(u6.PortStateRead())
		for i in range(self.firstChannel, self.numChannels+self.firstChannel):
			self.feedbackArguments.append( u6.AIN24(i, self.resolutionIndex, self.gainIndex, self.settlingFactor, self.differential) )
			
		self.task = viztask.schedule(self.__update)
		self.going = True
		self.history = []
		self.recording = False
		
		#magic numbers to turn volts into Newtons and Newton.meters
		#left is stored in first 6 (x,y,z,mx,my,mz) and right in second 6
		self.M = np.array([[0, -2.309900 , 0.000000 , 1.308000 , 0.000000 , 2.306800 , 0.000000 , -495.780000 , 0.000000 , -494.040000 , 0.000000 , -2.034400],\
			[0, 6.308900 , 0.000000 , 5.913600 , 0.000000 , 11.633000 , 0.000000 , -2.295700 , 0.000000 , -13.079000 , 0.000000 , 499.990000],\
			[0, -491.360000 , 0.000000 , -488.510000 , 0.000000 , -488.270000 , 0.000000 , 5.064000 , 0.000000 , 6.732400 , 0.000000 , 0.391790],\
			[0, 48.162000 , 0.000000 , -298.930000 , 0.000000 , 299.410000 , 0.000000 , -1.565600 , 0.000000 , 4.956800 , 0.000000 , 54.786000],\
			[0, -254.760000 , 0.000000 , -26.647000 , 0.000000 , -25.153000 , 0.000000 , 42.462000 , 0.000000 , 42.087000 , 0.000000 , 1.601900],\
			[0, -7.032800 , 0.000000 , 1.345700 , 0.000000 , -1.140100 , 0.000000 , -243.640000 , 0.000000 , 354.550000 , 0.000000 , -4.020500],\
			[-2.688400 , 0.000000 , -0.083334 , 0.000000 , 1.258500 , 0.000000 , 491.220000 , 0.000000 , -495.750000 , 0.000000 , -6.723600 , 0],\
			[-7.642900 , 0.000000 , -5.959700 , 0.000000 , -3.659100 , 0.000000 , 15.847000 , 0.000000 , -12.401000 , 0.000000 , 507.580000 , 0],\
			[-490.840000 , 0.000000 , -490.690000 , 0.000000 , -492.520000 , 0.000000 , -6.428000 , 0.000000 , 3.723600 , 0.000000 , 4.807000 , 0],\
			[300.830000 , 0.000000 , -300.260000 , 0.000000 , 48.265000 , 0.000000 , -5.152500 , 0.000000 , -1.434500 , 0.000000 , 49.278000 , 0],\
			[26.955000 , 0.000000 , 27.005000 , 0.000000 , 253.680000 , 0.000000 , -40.116000 , 0.000000 , 41.703000 , 0.000000 , -1.501700 , 0],\
			[-1.380200 , 0.000000 , -2.450800 , 0.000000 , -1.349500 , 0.000000 , -348.250000 , 0.000000 , -245.680000 , 0.000000 , 10.366000 , 0]],\
			dtype='float')

	def __update(self):
		msg = viz.addText("", parent=viz.SCREEN)
		t0 = 0 #for testing
		self.device.softReset()
		yield viztask.waitTime(1)
		print "Zeroing treadmill ... ",
		self.doZero()
		print "done"
		print "Started treadmill forceplates read"
		while self.going:
			results = self.device.getFeedback( self.feedbackArguments )
			for j in range(self.numChannels):
				self.latestAinValues[j] = self.device.binaryToCalibratedAnalogVoltage(self.gainIndex, results[2+j])
			self.lastForceMoments = list(self.latestForceMoments)
			self.latestForceMoments = self.M.dot(self.latestAinValues+self.zero)
			self.lastLeftOn = self.latestLeftOn
			self.lastRightOn = self.latestRightOn
			self.lastLeftCOP = list(self.latestLeftCOP)
			self.lastRightCOP = list(self.latestRightCOP)
			self.lastTime = self.latestTime
			self.latestTime = viz.tick()
			try:
				self.latestLeftOn = (self.latestForceMoments[2] < MIN_WEIGHT_NEWTONS)
				self.latestLeftCOP[0] = -1.0*self.latestForceMoments[4]/self.latestForceMoments[2]
				self.latestLeftCOP[1] = self.latestForceMoments[3]/self.latestForceMoments[2]
				self.latestRightOn = (self.latestForceMoments[8] < MIN_WEIGHT_NEWTONS)
				self.latestRightCOP[0] = -1.0*self.latestForceMoments[10]/self.latestForceMoments[8]
				self.latestRightCOP[1] = self.latestForceMoments[9]/self.latestForceMoments[8]
			except(ZeroDivisionError):
				print "div zero caught in ForcePlate ... ignoring"
				pass
			if self.recording:
				#self.data.append([viz.tick(), [x for x in self.latestAinValues]])
				self.data.append([viz.tick(), [x for x in self.latestForceMoments]])
				
			if self.lastLeftOn and not self.latestLeftOn:
				viz.sendEvent(LEFT_OFF_TREADMILL)
			if not self.lastLeftOn and self.latestLeftOn:
				viz.sendEvent(LEFT_ON_TREADMILL)
			if self.lastRightOn and not self.latestRightOn:
				viz.sendEvent(RIGHT_OFF_TREADMILL)
			if not self.lastRightOn and self.latestRightOn:
				viz.sendEvent(RIGHT_ON_TREADMILL)
				
			#testing
			t1 = t0
			t0 = viz.tick()
			#msg.message("%3.3fs"%(t0-t1))
			#msg.message("%6.3f %6.3f"%(self.latestLeftCOP[0], self.latestLeftCOP[1]))
			#if self.lastLeftOn:
			#	msg.message("Left on")
			#elif self.lastRightOn:
			#	msg.message("Right on")
			yield None
			
	def doZero(self, samples=100):
		self.zero = np.array([0]*self.numChannels, dtype='float')
		for i in range(samples):
			results = self.device.getFeedback( self.feedbackArguments )
			for j in range(self.numChannels):
				self.latestAinValues[j] = self.device.binaryToCalibratedAnalogVoltage(self.gainIndex, results[2+j])
			self.zero += self.latestAinValues
		self.zero /= -1.0*float(samples)

	
	#junk is needed for compatibility with logutil
	def startRecording(self,junk=1):
		self.clearRecording()
		self.recording = True
	def stopRecording(self):
		self.recording = False
	def dumpRecording(self,fname="recording.txt"):
		f = open(fname, 'w')
		for k in self.data:
			f.write("%10.9g "%(k[0]))
			for v in k[1]:
				f.write("%10.9g "%(v))
			f.write("\n")
	def clearRecording(self):
		self.data = []

		
if __name__ == '__main__':
	viz.go()
	viz.MainView.setPosition(0,5.5, -22)
	c1 = CTreadmillForcePlate()
	
	"""balls = []
	for i in range(c1.numChannels):
		b = viz.addTexQuad(pos=(0,i,1), color=viz.GRAY)
		viz.addText3D(str(i), parent=b, scale=(0.5,0.5, 1), pos=(0,0,-0.1))
		balls.append(b)
	
	def test1():
		while True:
			qq = c1.latestAinValues + c1.zero
			for i in range(c1.numChannels):
				balls[i].setPosition(qq[i],i,1)
			yield None
	viztask.schedule(test1)"""
	leftFoot = viz.add('white_ball.wrl', color=viz.GREEN)
	rightFoot = viz.add('white_ball.wrl', color=viz.RED)
	def test2():
		while True:
			left = c1.latestLeftCOP
			leftFoot.setPosition(left[0], left[1]+5.5, -17)
			right = c1.latestRightCOP
			rightFoot.setPosition(right[0], right[1]+5.5, -17)
			#for i in range(c1.numChannels):
			#	balls[i].setPosition(100,i,1)
			yield None
	viztask.schedule(test2)
	
	import vizact
	def leftoff():
		leftFoot.alpha(0)
	def lefton():
		leftFoot.alpha(1)
	def rightoff():
		rightFoot.alpha(0)
	def righton():
		rightFoot.alpha(1)
	viz.callback(LEFT_OFF_TREADMILL, leftoff)
	viz.callback(LEFT_ON_TREADMILL, lefton)
	viz.callback(RIGHT_OFF_TREADMILL, rightoff)
	viz.callback(RIGHT_ON_TREADMILL, righton)
		

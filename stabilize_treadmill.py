#Joe Snider
#7/14
#
#Stabilize the position of a subject on the treadmill.
#Uses the forceplates for the position measurement
#
#TODO: this needs cleaning. Current algorithm just moves the belt at a constant
#  speed when the foot is down and far enough forward. Simple, but seems pretty good.
#  There is tweaking with the acceleration and speed of the belt to make it feel realstic.
#  Could probably improve on this.

import viz
import viztask
from VTreadmill import *
from treadmill_force_plate import *
import numpy as np

#keep the center of mass heading toward here (on each belt seperately)
DESIRED_POSITION = -0.3#m from the treadmill center
BACK_MAX = -0.3#m from the treadmill center, deceleration starts here

#max speed
MAX_SPEED = 1#m/s

#foot occasionally bounces (not a step)
MIN_STRIDE_TIME = 100000#stick with the initial guess 0.2#s
#foot occasionally stands still (not a step)
MAX_STRIDE_TIME = 1.5#s

#this is probably different per subject, and the code should learn it
#0.7s works for Joe
STRIDE_TIME_GUESS = 0.7#s

#acceleration and deceleration values (should be pretty fast)
#range is 0 to 18000, 900 is initial
DECELERATION = 1200
ACCELERATION = 1200
#decelleration for going off the back is larger (so the foot doesn't hit the light switch and cause a suspend)
BACK_DECELERATION = 2000

#correct the left plate position by this much
CORRECT_LEFT = 0.01776 #m

#at least for testing, just turn it on
MIN_DIST_TO_DESIRED = 0.2#m
FIXED_SPEED = 0.4#m/s

REQUEST_FEET_ALIGNMENT_TREADMILL = viz.getEventID('REQUEST_FEET_ALIGNMENT_TREADMILL')
DONE_FEET_ALIGNMENT_TREADMILL = viz.getEventID('DONE_FEET_ALIGNMENT_TREADMILL')

class StabilizeTreadmill:
	def __init__(self, tmill, forceplates):
		#use enable to prevent the belts from moving/view updating
		self.enable = False
		
		self.tmill = tmill
		self.forceplates = forceplates
		
		self.leftStrideLength = 0.#m, this is only an initial estimate, it will be measured
		self.rightStrideLength = 0.#m
		
		self.leftDistToDesired = 0.0#m
		self.rightDistToDesired = 0.0#m
		
		self.numSamples = 10 #average over this many stride times
		self.leftStrideTime = np.array([STRIDE_TIME_GUESS]*self.numSamples, dtype='float')#s, 1 is initial guess
		self.rightStrideTime = np.array([STRIDE_TIME_GUESS]*self.numSamples, dtype='float')#s, 1 is initial guess
		
		self.leftSpeed = self.leftStrideLength / np.median(self.leftStrideTime)
		self.rightSpeed = self.rightStrideLength / np.median(self.rightStrideTime)
		
		self.leftDownTime = 0.0#s
		self.leftUpTime = 0.0#s
		self.rightDownTime = 0.0#s
		self.rightUpTime = 0.0#s
		
		self.leftDownPos = [0.,0.]#m
		self.leftUpPos = [0.,0.]#m
		self.rightDownPos = [0.,0.]#m
		self.rightUpPos = [0.,0.]#m
		
		self.history = []
		
		viztask.schedule(self.__update)
		viztask.schedule(self.__stride)
		viztask.schedule(self.__ZeroSpacing)
		
	#this will attempt to zero the spacing between the feet
	#takes data for 'samples' frames
	#subject should hold as still as possible on that time frame
	def __ZeroSpacing(self, samples=60):
		while True:
			yield viztask.waitEvent(REQUEST_FEET_ALIGNMENT_TREADMILL)
			print "Starting zero ... ",
			yield None
			self.left = []
			self.right = []
			for i in range(samples):
				self.left.append(self.forceplates.latestLeftCOP[1])
				self.right.append(self.forceplates.latestRightCOP[1])
				yield None
			print "done"
			self.left = np.array(self.left)
			self.right = np.array(self.right)
			global CORRECT_LEFT
			CORRECT_LEFT = np.mean(self.right) - np.mean(self.left)
			print "Adjusting left ", CORRECT_LEFT, " meters to match right"
			print "Variability was ", np.std(self.left), " on the left"
			print "Variability was ", np.std(self.right), " on the right"
			viz.sendEvent(DONE_FEET_ALIGNMENT_TREADMILL)
			
		
	def __update(self):
		msg = viz.addText("", parent = viz.SCREEN, pos=(0.75, 0.9,0), scale=(0.25,0.25,0))
		msg.setBackdrop(viz.BACKDROP_OUTLINE)
		while True:
			if self.tmill.going and self.forceplates.going and self.enable:
				#catch the foot before it goes off the end
				if self.forceplates.latestLeftOn and self.forceplates.latestLeftCOP[1] < BACK_MAX and self.leftSpeed > 0:
					self.leftSpeed = 0
					self.tmill.moveLeftBelt(spd=0, mpss=BACK_DECELERATION)
				if self.forceplates.latestRightOn and self.forceplates.latestRightCOP[1] < BACK_MAX and self.rightSpeed > 0:
					self.rightSpeed = 0
					self.tmill.moveRightBelt(spd=0, mpss=BACK_DECELERATION)
				if self.forceplates.lastLeftOn:
					self.leftGSM = self.forceplates.latestForceMoments[1]
				if self.forceplates.lastRightOn:
					self.rightGSM = self.forceplates.latestForceMoments[7]
				msg.message("left dist, spd: %3.3f, %3.3f\nright dist,spd: %3.3f, %3.3f"%(\
					self.leftDistToDesired, self.leftSpeed, \
					self.rightDistToDesired, self.rightSpeed))
			yield None
	
	def __stride(self):
		leftDown = viztask.waitEvent(LEFT_ON_TREADMILL)
		leftUp = viztask.waitEvent(LEFT_OFF_TREADMILL)
		rightDown = viztask.waitEvent(RIGHT_ON_TREADMILL)
		rightUp = viztask.waitEvent(RIGHT_OFF_TREADMILL)
		while True:
			d = yield viztask.waitAny([leftDown, leftUp, rightDown, rightUp])
			if self.enable:
				if d.condition is leftDown:
					self.leftDownTime = viz.tick()
					self.leftDownPos[0] = self.forceplates.latestLeftCOP[0]
					self.leftDownPos[1] = self.forceplates.latestLeftCOP[1] + CORRECT_LEFT
					st = self.leftDownTime - self.leftUpTime
					if st > MIN_STRIDE_TIME and st < MAX_STRIDE_TIME:
						self.leftStrideTime[0] = st
						self.leftStrideTime = np.roll(self.leftStrideTime, 1)
					self.leftStrideLength = math.sqrt((self.leftDownPos[0] - self.leftUpPos[0])**2 +\
						(self.leftDownPos[1] - self.leftUpPos[1])**2)
					self.leftDistToDesired = self.leftDownPos[1] - DESIRED_POSITION
					if self.leftDistToDesired > MIN_DIST_TO_DESIRED:
						#set the left speed to be fast enough to get the foot back to the 'desired' while the right is up
						self.leftSpeed = FIXED_SPEED
						#self.leftSpeed = self.leftDistToDesired/np.mean(self.rightStrideTime + 1.e-6) #avoid 1/0
						self.tmill.moveLeftBelt(spd=min([self.leftSpeed, MAX_SPEED]), mpss=ACCELERATION)
						self.history.append("%10.9g %10.9g leftdown"%(viz.tick(), min([self.leftSpeed, MAX_SPEED])))
				elif d.condition is leftUp:
					self.tmill.moveLeftBelt(spd=0, mpss=DECELERATION)
					self.history.append("%10.9g %10.9g leftup"%(viz.tick(), 0))
					self.leftUpTime = viz.tick()
					self.leftUpPos[0] = self.forceplates.latestLeftCOP[0]
					self.leftUpPos[1] = self.forceplates.latestLeftCOP[1] + CORRECT_LEFT
				if d.condition is rightDown:
					self.rightDownTime = viz.tick()
					self.rightDownPos[0] = self.forceplates.latestRightCOP[0]
					self.rightDownPos[1] = self.forceplates.latestRightCOP[1]
					st = self.rightDownTime - self.rightUpTime
					if st > MIN_STRIDE_TIME and st < MAX_STRIDE_TIME:
						self.rightStrideTime[0] = st
						self.rightStrideTime = np.roll(self.rightStrideTime, 1)
					self.rightStrideLength = math.sqrt((self.rightDownPos[0] - self.rightUpPos[0])**2 +\
						(self.rightDownPos[1] - self.rightUpPos[1])**2)
					self.rightDistToDesired = self.rightDownPos[1] - DESIRED_POSITION
					if self.rightDistToDesired > MIN_DIST_TO_DESIRED:
						self.rightSpeed = FIXED_SPEED
						#self.rightSpeed = self.rightDistToDesired/np.mean(self.leftStrideTime + 1.e-6) #avoid 1/0
						self.tmill.moveRightBelt(spd=min([self.rightSpeed, MAX_SPEED]), mpss=ACCELERATION)
						self.history.append("%10.9g %10.9g rightdown"%(viz.tick(), min([self.rightSpeed, MAX_SPEED])))
				elif d.condition is rightUp:
					self.tmill.moveRightBelt(spd=0, mpss=DECELERATION)
					self.history.append("%10.9g %10.9g rightup"%(viz.tick(), 0))
					self.rightUpTime = viz.tick()
					self.rightUpPos[0] = self.forceplates.latestRightCOP[0]
					self.rightUpPos[1] = self.forceplates.latestRightCOP[1]
					
	#for logutil compatibility
	def startRecording(self,junk):
		self.clearRecording()
		self.recording = True
	def stopRecording(self):
		self.recording = False
	def clearRecording(self):
		self.history = []
	def dumpRecording(self,filename):
		fil = open(filename, 'w')
		fil.write("time speed event\n")
		for t in self.history:
			fil.write(t+"\n")
		fil.close()

if __name__ == '__main__':
	#class TMDummy:
	#	going = True
	#TM1 = TMDummy()
	TM1 = VTreadmill()
	FP1 = CTreadmillForcePlate()
	
	STM1 = StabilizeTreadmill(TM1, FP1)
	
	place = viz.add('piazza.osgb')
	
	viz.go()
	
	lnk = viz.link(TM1.track, viz.MainView)
	lnk.postTrans([0,1,-10])

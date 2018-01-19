#Joe Snider
#7/14
#
#Run the treadmill from Vizard (wraps treadmill.py)

import viz
import treadmill
import FLMOCommands
import vizact
import viztask
import math

#this is sent whenever a new value is read from the treadmill
# It should mainly come from subscribed values (things the treadmill is sending as fast as it can)
TREADMILL_STATE_UPDATED = viz.getEventID('TREADMILL_STATE_UPDATED')

#register a quit call back to shutdown the treadmill properly
STOP_TREADMILL = viz.getEventID('STOP_TREADMILL')
TREADMILL_STOPPED = viz.getEventID('TREADMILL_STOPPED')
def doShutdownTreadmill():
	yield viztask.waitKeyDown('q')
	viz.sendEvent(STOP_TREADMILL)
	yield viztask.waitEvent(TREADMILL_STOPPED)
	print "pause ...",
	yield viztask.waitTime(1)
	print "done"
	viz.quit()
viztask.schedule(doShutdownTreadmill)

class VTreadmill:
	#verbose sets display of the belts' speed and position
	def __init__(self, verbose=True):
		self.T1 = treadmill.Treadmill()
		
		#linkables that keep track of the current position
		self.track = viz.add('box.wrl', alpha=0)
		self.separation = 0.05#meters between the feet (approx is probably ok, or get it from force plates)
		
		self.going = False
		viztask.schedule(self.__start)
		viztask.schedule(self.__stop)
		viztask.schedule(self.__trackResponse)

		viztask.schedule(self.updatePos)
		
		self.verbose = verbose
		
		#for logutil
		self.history = []
		self.recording = False
		
	#call these to control the treadmill
	#  spd is speed in m/s
	#  mpss is acceleration in unknown units (900 is wimpy)
	def moveLeftBelt(self,spd=0, mpss=3600):
		self.T1.SetLeftBeltAcceleration(mpss)
		self.T1.MoveLeftBelt(spd)
		self.T1.SetLeftBeltAcceleration(mpss)
		self.T1.MoveLeftBelt(spd)
	def moveRightBelt(self,spd=0, mpss=3600):
		self.T1.SetRightBeltAcceleration(mpss)
		self.T1.MoveRightBelt(spd)
		self.T1.SetRightBeltAcceleration(mpss)
		self.T1.MoveRightBelt(spd)
		
	#this puts the trackable node back to 0,0,0 and facing north
	def resetTrack(self):
		self.track.clearActions()
		self.track.setPosition(0,0,0)
		self.track.setEuler(0,0,0)
		
	#the rest is lower level control
	#this will update the position/speed of the belts
	def updatePos(self):
		rad_to_deg = math.pi / 180.0
		msg = viz.addText("", parent=viz.SCREEN, pos=(0.05, 0.9,0), scale=(0.25,0.25,0))
		msg.setBackdrop(viz.BACKDROP_OUTLINE)
		self.readTime = 0
		t0 = viz.tick()
		while True:
			if self.going:
				#self.T1.ReadBothBeltsPosition()
				#self.T1.ReadBothBeltsSpeed()
				self.lbp = self.T1.plabTreadmill.leftBeltPosition.value
				self.rbp = self.T1.plabTreadmill.rightBeltPosition.value
				self.lbs = self.T1.plabTreadmill.leftBeltSpeed.value
				self.rbs = self.T1.plabTreadmill.rightBeltSpeed.value
				if self.verbose:
					self.message = "Left: %6.6f, %6.6f\nRight: %6.6f, %6.6f\nReadTime: %6.6f ms"%(\
						self.lbp, self.lbs, self.rbp, self.rbs, 1000.0*self.readTime)
				else:
					self.message = ""
				msg.message(self.message)
				
				dt = viz.tick() - t0
				dtheta_dt = (self.lbs-self.rbs)/self.separation
				dr_dt = 0.5*(self.lbs+self.rbs)
				spinner = vizact.spin(0,1,0,dtheta_dt,dt)
				mover = vizact.move(0,0,dr_dt, dt)
				spinmove = vizact.parallel(spinner, mover)
				#print "gh1",dr_dt, dt
				self.track.addAction(spinmove)
				yield viztask.waitActionEnd(self.track, spinmove)
				t0 = viz.tick()
				
				#for the recording
				if self.recording:
					#time, left pos, left speed, right pos, right speed, head pos (xyz, dir)
					pp = self.track.getPosition()
					self.history.append((viz.tick(), self.lbp, self.lbs, self.rbp, self.rbs, pp[0], pp[1], pp[2], self.track.getEuler()[0]))
			#yield viztask.waitTime(1.0/19.0)
			yield viztask.waitEvent(TREADMILL_STATE_UPDATED)
		
	def __start(self):
		if not self.going:
			print "pause ... ",
			yield viztask.waitTime(1)
			print "done"
			self.parseConfig()
			print "pause ... ",
			yield viztask.waitTime(1)
			print "done"
			self.startMotors()
			print "pause ... ",
			yield viztask.waitTime(1)
			print "done"
			self.going = True
			print "pause ... ",
			yield viztask.waitTime(1)
			print "done"
			
			#subscribe to the position/speed reads
			self.T1.SubscribeBothBeltsPosition()
			self.T1.SubscribeBothBeltsSpeed()
		else:
			print "Error (VTreadmill): attempted to reconnect, but that is not allowed ... ignoring"
			
	def __stop(self):
		yield viztask.waitEvent(STOP_TREADMILL)
		if self.going:
			self.stopMotors()
			yield viztask.waitTime(1)
			print "Closing socket ...",
			self.T1.stop()
			print "done"
			viz.sendEvent(TREADMILL_STOPPED)
	
	def parseConfig(self):
		print "Parsing configuration string ...",
		self.T1.parseConfig()
		print "done"
	
	def startMotors(self):
		print "Starting motors (should hear them) ... ",
		self.T1.StartAll()
		print "done"
		
	def stopMotors(self):
		print "Stopping motors (should no longer hear them) ... ",
		self.T1.Reset()
		print "done"
		
	#its a little awkward, but we do the parsing here to make sure we can access viz.tick
	def __trackResponse(self):
		readStart = 0
		while True:
			if self.going:
				resp = self.T1.readAllResponse()
				for r in resp:
					sm = r.find('sm')
					if sm is not None and sm.text == FLMOCommands.ServerMessages.ActualValue:
						try:
							q = self.T1.MotorResponses[r.find('id').text]
							q.time = viz.tick()
							q.value = self.T1.device_to_si * float(r.find('v').text)
							self.readTime = viz.tick() - readStart
							readStart = viz.tick()
							viz.sendEvent(TREADMILL_STATE_UPDATED)
						except(ValueError):
							print "Warning (VTreadmill: could not parse value from"
							print "   ",treadmill.ET.tostring(r)
							print "continuing"
						except(KeyError):
							print "Warning (VTreadmill: could not locate id from"
							print "   ",treadmill.ET.tostring(r)
							print "   id was: ", r.find('id').text
							print "   available ids are:"
							for k,v in self.T1.MotorResponses.iteritems():
								print "        ",k
							print "continuing"
					elif sm is not None and sm.text == FLMOCommands.ServerMessages.ErrorMessage:
						viz.logWarn("Warning (VTreadmill): Treadmill returned an error:\n   ", treadmill.ET.tostring(r), "\n    ", r.find('string').text)
			yield None

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
		fil.write("time left_pos left_speed right_pos right_speed viewX viewY viewZ viewDir\n")
		for t in self.history:
			fil.write('%10.9g %10.9g %10.9g %10.9g %10.9g %10.9g %10.9g %10.9g %10.9g\n'%t)
		fil.close()

if __name__ == "__main__":
	viz.go()
	
	place = viz.add('piazza.osgb')
	
	VTM = VTreadmill()
	lnk = viz.link(VTM.track, viz.MainView)
	lnk.preTrans([0,1,0])
	


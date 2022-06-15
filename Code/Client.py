from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3

	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0

	# THIS GUI IS JUST FOR REFERENCE ONLY, STUDENTS HAVE TO CREATE THEIR OWN GUI
	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		self.setup = Button(self.master, width=20, padx=3, pady=3)
		self.setup.config(text="Setup", command=self.setupMovie, state=DISABLED)
		self.setup.grid(row=1, column=0, padx=2, pady=2)

		# Create Play button
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start.config(text="Play", command=self.playMovie, state=DISABLED)
		self.start.grid(row=1, column=1, padx=2, pady=2)

		# Create Pause button
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause.config(text="Pause", command=self.pauseMovie, state=DISABLED)
		self.pause.grid(row=1, column=2, padx=2, pady=2)

		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown.config(text="Teardown", command=self.exitClient, state=DISABLED)
		self.teardown.grid(row=1, column=3, padx=2, pady=2)

		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

	def updateWidgetsState(self):
		"""Update widgets' state."""
		if self.state == self.INIT:
			self.setup.config(state=NORMAL)
			self.start.config(state=DISABLED)
			self.pause.config(state=DISABLED)
			self.teardown.config(state=DISABLED)
		elif self.state == self.READY:
			self.setup.config(state=DISABLED)
			self.start.config(state=NORMAL)
			self.pause.config(state=DISABLED)
			self.teardown.config(state=NORMAL)
		elif self.state == self.PLAYING:
			self.setup.config(state=DISABLED)
			self.start.config(state=DISABLED)
			self.pause.config(state=NORMAL)
			self.teardown.config(state=NORMAL)

	def setupMovie(self):
		"""Setup button handler."""
		print('Setting up...\n')
		self.sendRtspRequest(self.SETUP)

	def exitClient(self):
		"""Teardown button handler."""
		if self.requestSent == self.SETUP:
			print('Session not yet setup, exiting')
			print('Clearing cache...\n')
			os.remove(f'{CACHE_FILE_NAME}{self.sessionId}{CACHE_FILE_EXT}')
			self.state = self.INIT
			self.updateWidgetsState()
		else:
			print('Closing session...\n')
			self.sendRtspRequest(self.TEARDOWN)

	def pauseMovie(self):
		"""Pause button handler."""
		print('Pausing...\n')
		self.sendRtspRequest(self.PAUSE)

	def playMovie(self):
		"""Play button handler."""
		print('Playing...\n')
		self.sendRtspRequest(self.PLAY)

	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		imageFile = f'{CACHE_FILE_NAME}{self.sessionId}{CACHE_FILE_EXT}'
		with open(imageFile, 'wb') as image:
			image.write(data)
			image.close()
		return imageFile

	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		image = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.config(image = image, height=400)
		self.label.image = image

	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""

		try:
			self.rtspSocket = {
				'socket' : socket.socket(socket.AF_INET, socket.SOCK_STREAM),
				'worker' : threading.Thread(target=self.recvRtspReply),
				'runEvent' : threading.Event(),
				'stopEvent' : threading.Event(),
			}
			self.rtspSocket['socket'].connect((self.serverAddr, self.serverPort))
			self.rtspSocket['runEvent'].clear()
			self.rtspSocket['stopEvent'].clear()
			self.rtspSocket['worker'].start()

			self.updateWidgetsState()

			print('Successfully connected to the server\n')
		except:
			tkinter.messagebox.showwarning('Client.py', f'Failed to connect to Server at {self.serverAddr}:{self.serverPort}')

	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""

		self.rtspSocket['runEvent'].set()

		if requestCode == self.SETUP:
			self.rtspSeq = 1
			packetData = (
				f'SETUP {self.fileName} RTSP/1.0',
				f'CSeq: {self.rtspSeq}',
				f'Transport: RTP/UDP; client_port= {self.rtpPort}',
			)
		elif requestCode == self.PLAY:
			self.rtspSeq += 1
			packetData = (
				f'PLAY {self.fileName} RTSP/1.0',
				f'CSeq: {self.rtspSeq}',
				f'Session: {self.sessionId}',
			)
		elif requestCode == self.PAUSE:
			self.rtspSeq += 1
			packetData = (
				f'PAUSE {self.fileName} RTSP/1.0',
				f'CSeq: {self.rtspSeq}',
				f'Session: {self.sessionId}',
			)
		elif requestCode == self.TEARDOWN:
			self.rtspSeq += 1
			packetData = (
				f'TEARDOWN {self.fileName} RTSP/1.0',
				f'CSeq: {self.rtspSeq}',
				f'Session: {self.sessionId}',
			)

		self.rtspSocket['socket'].send(bytes('\n'.join(packetData), 'utf-8'))
		self.requestSent = requestCode

	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""

		while not self.rtspSocket['stopEvent'].is_set():
			if self.rtspSocket['runEvent'].is_set():
				try:
					reply = self.rtspSocket['socket'].recv(1024)
					if reply:
						self.parseRtspReply(reply.decode("utf-8"))
				except:
					pass
			else:
				self.rtspSocket['runEvent'].wait(0.01)

	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""

		lines = data.split('\n')
		statusCode = int(lines[0].split(' ')[1])
		sequenceNumber = int(lines[1].split(' ')[1])
		sessionNumber = int(lines[2].split(' ')[1])

		if self.requestSent != self.SETUP and sessionNumber != self.sessionId:
			return

		if sequenceNumber != self.rtspSeq:
			return

		if self.rtspSocket['runEvent'].is_set():
			self.rtspSocket['runEvent'].clear()
		else:
			return

		if statusCode == 500:
			tkinter.messagebox.showwarning('Client.py', 'Connection error')
		elif statusCode == 404:
			tkinter.messagebox.showwarning('Client.py', 'File not found')
		elif statusCode != 200:
			return

		if self.requestSent == self.SETUP:
			self.state = self.READY
			self.sessionId = sessionNumber
			open(f'{CACHE_FILE_NAME}{self.sessionId}{CACHE_FILE_EXT}', 'x').close()
			self.openRtpPort()
		elif self.requestSent == self.PLAY:
			self.state = self.PLAYING
			self.rtpSocket['runEvent'].set()
		elif self.requestSent == self.PAUSE:
			self.state = self.READY
			self.rtpSocket['runEvent'].clear()
		elif self.requestSent == self.TEARDOWN:
			self.state = self.INIT
			self.teardownAcked = 1
			self.rtpSocket['runEvent'].clear()
			self.rtpSocket['stopEvent'].set()
			self.rtpSocket['worker'].join()

			try:
				self.rtpSocket['socket'].shutdown(socket.SHUT_RDWR)
			except:
				pass
			self.rtpSocket['socket'].close()

			print('Clearing cache...')
			os.remove(f'{CACHE_FILE_NAME}{self.sessionId}{CACHE_FILE_EXT}')

		self.updateWidgetsState()

	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		#-------------
		# TO COMPLETE
		#-------------
		# Create a new datagram socket to receive RTP packets from the server
		self.rtpSocket = {
			'socket' : socket.socket(socket.AF_INET, socket.SOCK_DGRAM),
			'runEvent' : threading.Event(),
			'stopEvent' : threading.Event(),
			'worker' : threading.Thread(target=self.listenRtp)
		}
		self.rtpSocket['socket'].bind(('', self.rtpPort))

		# Set the timeout value of the socket to 0.5sec
		self.rtpSocket['socket'].settimeout(0.5)

		self.rtpSocket['runEvent'].clear()
		self.rtpSocket['stopEvent'].clear()
		self.rtpSocket['worker'].start()

	def listenRtp(self):
		"""Listen for RTP packets."""
		while not self.rtpSocket['stopEvent'].is_set():
			if self.rtpSocket['runEvent'].is_set():
				try:
					data, addr = self.rtpSocket['socket'].recvfrom(65536)
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					if rtpPacket.version() != 2 or rtpPacket.payloadType() != 26 or rtpPacket.seqNum() <= self.frameNbr:
						continue

					self.frameNbr = rtpPacket.seqNum()
					self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
				except:
					pass
			else:
				self.rtpSocket['runEvent'].wait(0.01)

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		if self.state == self.PLAYING:
			self.pauseMovie()

		try:
			if tkinter.messagebox.askokcancel("Client.py", "Are you sure you want to quit?") == False:
				return
		except:
			return

		if self.state != self.INIT:
			self.exitClient()

		if self.rtspSocket['worker'].is_alive():
			self.rtspSocket['runEvent'].clear()
			self.rtspSocket['stopEvent'].set()
			self.rtspSocket['worker'].join()

		try:
			self.rtspSocket['socket'].shutdown(socket.SHUT_RDWR)
		except:
			pass
		self.rtspSocket['socket'].close()

		self.master.destroy()

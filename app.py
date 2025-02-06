#!bin/python3

import watchdog.events
import watchdog.observers
import time
import logging
import os
import random, string

from pathlib import Path

from flask import Flask, request, Response
from flask_socketio import SocketIO, disconnect, emit


from threading import Thread, Event


#########################################################################################################


def log(message):
	logging.warning(message)


def gen_key(length):
   letters = string.ascii_lowercase
   return ''.join(random.choice(letters) for i in range(length))


app = Flask(__name__)
app.config['SECRET_KEY'] = gen_key(32)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')


DIRNAMES = dict()
SCHEDULERS = dict()


#########################################################################################################


class Handler(watchdog.events.PatternMatchingEventHandler):

	def __init__(self):
		# Set the patterns for PatternMatchingEventHandler
		watchdog.events.PatternMatchingEventHandler.__init__(self, ignore_directories=True, case_sensitive=False)
		Thread(target=socketio.run, args=(app,), kwargs=dict(allow_unsafe_werkzeug=True, debug=False, use_reloader=False, host='0.0.0.0', port=8899)).start()
	
	
	@app.route("/socket.io.min.js.map") 
	def socketio_map():
		content = []
		
		with open('socket.io.min.js.map', 'r') as file:
			data = file.read().replace('\n', '')
			content.append(data)
			
		return Response("\n".join(content), mimetype='text/javascript')
		
		
		
	@app.route("/reloader") 
	def reloader():
		content = []
		
		with open('socket.io.min.js', 'r') as file:
			data = file.read().replace('\n', '')
			content.append(data)
    
		content.append("function observe(url, dirname) {")
		content.append(" socket = io.connect(url);")
		content.append(" socket.on('connect', function () { socket.emit('observe', dirname); });")
		content.append(" socket.on('update', function () { location.reload(); });")
		content.append(" socket.on('message', function (message) { console.log(message); });")
		content.append("}")
		
		return Response("\n".join(content), mimetype='text/javascript')


	@socketio.on('connect')
	def handle_connect():
		sid = request.sid
		log("Client [ %s ] has connected..." % sid)
		socketio.emit('message', 'connected...')
		

	@socketio.on('disconnect')
	def handle_disconnect():
		sid = request.sid
		log("Client [ %s ] has disconnected..." % sid)


		for subscribed_dirnames in list(DIRNAMES):
			
			
			try:
				DIRNAMES[subscribed_dirnames].remove(sid)
			except:
				pass
			
			if len(DIRNAMES[subscribed_dirnames]) == 0:
				
				log("Remove scheduler for [ %s ] dir..." % subscribed_dirnames)
				observer.unschedule(SCHEDULERS[subscribed_dirnames])
				del(SCHEDULERS[subscribed_dirnames])
				del(DIRNAMES[subscribed_dirnames])


	
	@socketio.on('observe')
	def handle_observe(dirname):
		sid = request.sid
		log("Client [ %s ] wants to observe [ %s ] dir" % (sid, dirname))

		
		if dirname not in DIRNAMES:
			DIRNAMES[dirname] = [ sid ]
			log("Create new scheduler for the [ %s ] dir..." % dirname)
			new_scheduler = observer.schedule(event_handler, path=dirname, recursive=True)
			SCHEDULERS[dirname] = new_scheduler
		else:
			DIRNAMES[dirname].append(sid)
			
		
		

	def on_created(self, event):
		log("Watchdog received created event - % s" % event.src_path)
		# socketio.emit('message', 'on_created')



	def on_modified(self, event):
		log("Watchdog received modified event - % s" % event.src_path)
		# socketio.emit('message', 'on_modified')

		if not event.is_directory:	## file has been updated
			updated_dirname = os.path.dirname(event.src_path)	## extract folder path
			for subscribed_dirnames in list(DIRNAMES):	## get every observed dirname
				if subscribed_dirnames == updated_dirname:
					for sid in DIRNAMES[subscribed_dirnames]:	## get every sid subscribed to the observed dirname
						socketio.emit('update', to=sid)		## send update
				
				# if subscribed_dirnames == updated_dirname or Path(updated_dirname).is_relative_to(subscribed_dirnames):	## check if it is in observed or is a child of observed
					# for sid in DIRNAMES[subscribed_dirnames]:	## get every sid subscribed to the observed dirname
						# socketio.emit('update', to=sid)		## send update
		

	def on_deleted(self, event):
		log("Watchdog received deleted event - % s" % event.src_path)
		# socketio.emit('message', 'on_deleted')



#########################################################################################################

if __name__ == "__main__":

	event_handler = Handler()
	observer = watchdog.observers.Observer()
	observer.start()

	try:
		while True:
			time.sleep(1)
	except KeyboardInterrupt:
		observer.stop()
	observer.join()

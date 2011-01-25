from dmd import *

class FrameLayer(Layer):
	"""Displays a single frame."""
	
	blink_frames = None # Number of frame times to turn frame on/off
	blink_frames_counter = 0
	frame_old = None
	
	def __init__(self, opaque=False, frame=None):
		super(FrameLayer, self).__init__(opaque)
		self.frame = frame
	def next_frame(self):
		if self.blink_frames > 0:
			if self.blink_frames_counter == 0:
				self.blink_frames_counter = self.blink_frames
				if self.frame == None:
					self.frame = self.frame_old
				else:
					self.frame_old = self.frame
					self.frame = None
			else:
				self.blink_frames_counter -= 1
		return self.frame

class AnimatedLayer(Layer):
	"""Collection of frames displayed sequentially, as an animation.  Optionally holds the last frame on-screen."""
	def __init__(self, opaque=False, hold=True, repeat=False, frame_time=1, frames=None, callback=None):
		super(AnimatedLayer, self).__init__(opaque)
		self.hold = hold
		self.repeat = repeat
		if frames == None:
			self.frames = list()
		else:
			self.frames = frames
				
		self.frame_time = frame_time # Number of frames each frame should be displayed for before moving to the next.
		self.frame_time_counter = self.frame_time
		
		self.frame_listeners = []
		if callback:
			self.add_frame_listener(len(self.frames)-1, callback)
		
		self.reset()
		
	def reset(self):
		self.frame_pointer = 0
		
	def add_frame_listener(self, frame_index, handler):
		self.frame_listeners += [[frame_index, handler]]
		
	def next_frame(self):
		"""Returns the frame to be shown, or None if there is no frame."""
		if self.frame_pointer >= len(self.frames):
			return None

		frame = self.frames[self.frame_pointer]
		self.frame_time_counter -= 1
		if (self.hold == False or len(self.frames) > 1) and (self.frame_time_counter == 0):
			if (self.frame_pointer == len(self.frames)-1):
				if self.repeat:
					self.frame_pointer = 0
				elif (self.hold == False):
					self.frame_pointer += 1
					frame = None
			else:
				self.frame_pointer += 1

		if self.frame_time_counter == 0:
			self.frame_time_counter = self.frame_time
			
		# Check frame listeners
		for frame_listener in self.frame_listeners:
			if self.frame_pointer == frame_listener[0]:
				frame_listener[1]()
		
		return frame


class FrameQueueLayer(Layer):
	"""Queue of frames displayed sequentially, as an animation.  Optionally holds the last frame on-screen.
	Destroys the frame list as it displays frames.  In that respect this class implements the old behavior
	of :class:`AnimatedLayer`.
	"""
	def __init__(self, opaque=False, hold=True, repeat=False, frame_time=1, frames=None):
		super(FrameQueueLayer, self).__init__(opaque)
		self.hold = hold
		self.repeat = repeat
		if frames == None:
			self.frames = list()
		else:
			self.frames = frames
		self.frame_time = frame_time # Number of frames each frame should be displayed for before moving to the next.
		self.frame_time_counter = self.frame_time
	
	def next_frame(self):
		"""Returns the frame to be shown, or None if there is no frame."""
		if len(self.frames) == 0:
			return None
		frame = self.frames[0] # Get the first frame in this layer's list.
		self.frame_time_counter -= 1
		if (self.hold == False or len(self.frames) > 1) and (self.frame_time_counter == 0):
			if self.repeat:
				f = self.frames[0]
				del self.frames[0]
				self.frames += [f]
			else:
				del self.frames[0] # Pop off the frame if there are others
		if self.frame_time_counter == 0:
			self.frame_time_counter = self.frame_time
		return frame


class TextLayer(Layer):
	"""Layer that displays text."""
	def __init__(self, x, y, font, justify="left", opaque=False):
		super(TextLayer, self).__init__(opaque)
		self.set_target_position(x, y)
		self.font = font
		self.started_at = None
		self.seconds = None # Number of seconds to show the text for
		self.frame = None # Frame that text is rendered into.
		self.frame_old = None
		self.justify = justify
		self.blink_frames = None # Number of frame times to turn frame on/off
		self.blink_frames_counter = 0
		
	def set_text(self, text, seconds=None, blink_frames=None):
		"""Displays the given message for the given number of seconds."""
		self.started_at = None
		self.seconds = seconds
		self.blink_frames = blink_frames
		self.blink_frames_counter = self.blink_frames
		if text == None:
			self.frame = None
		else:
			(w, h) = self.font.size(text)
			self.width = w
			self.height = h
			self.frame = Frame(w, h)
			self.font.draw(self.frame, text, 0, 0)
			if self.justify == "left":
				(self.target_x_offset, self.target_y_offset) = (0,0)
			elif self.justify == "right":
				(self.target_x_offset, self.target_y_offset) = (-w,0)
			elif self.justify == "center":
				(self.target_x_offset, self.target_y_offset) = (-w/2,0)
		return self

	def next_frame(self):
		if self.started_at == None:
			self.started_at = time.time()
		if (self.seconds != None) and ((self.started_at + self.seconds) < time.time()):
			self.frame = None
		elif self.blink_frames > 0:
			if self.blink_frames_counter == 0:
				self.blink_frames_counter = self.blink_frames
				if self.frame == None:
					self.frame = self.frame_old
				else:
					self.frame_old = self.frame
					self.frame = None
			else:
				self.blink_frames_counter -= 1
		return self.frame
	
	def is_visible(self):
		return self.frame != None

class ScriptedLayer(Layer):
	"""Displays a set of layers based on a simple script.
	
	**Script Format**
	
	The script is an list of dictionaries.  Each dictionary contains two keys: ``seconds`` and
	``layer``.  ``seconds`` is the number of seconds that ``layer`` will be displayed before 
	advancing to the next script element.
	
	If ``layer`` is ``None``, no frame will be returned by this layer for the duration of that script
	element.
	
	Example script::
	
	  [{'seconds':3.0, 'layer':self.game_over_layer}, {'seconds':3.0, 'layer':None}]
	
	"""
	def __init__(self, width, height, script):
		super(ScriptedLayer, self).__init__()
		self.buffer = Frame(width, height)
		self.script = script
		self.script_index = 0
		self.frame_start_time = None
		self.force_direction = None
		self.on_complete = None
		self.is_new_script_item = True
		self.last_layer = None
	
	def next_frame(self):
		# This assumes looping.  TODO: Add code to not loop!
		if self.frame_start_time == None:
			self.frame_start_time = time.time()
		
		script_item = self.script[self.script_index]
		
		time_on_frame = time.time() - self.frame_start_time
		
		# If we are being forced to the next frame, or if the current script item has expired:
		if self.force_direction != None or time_on_frame > script_item['seconds']:
			
			self.last_layer = script_item['layer']
			
			# Update the script index:
			if self.force_direction == False:
				if self.script_index == 0:
					self.script_index = len(self.script)-1 
				else:
					self.script_index -= 1
			else:
				if self.script_index == len(self.script):
					self.script_index = 0
				else:
					self.script_index += 1
			
			# Only force one item.
			self.force_direction = None
			
			# If we are at the end of the script, reset to the beginning:
			if self.script_index == len(self.script):
				self.script_index = 0
				if self.on_complete != None:
					self.on_complete()
			
			# Assign the new script item:
			script_item = self.script[self.script_index]
			self.frame_start_time = time.time()
			layer = script_item['layer']
			if layer:
				layer.reset()
			self.is_new_script_item = True
		
		# Composite the current script item's layer:
		layer = script_item['layer']
		
		transition = None
		if layer and layer.transition:
			if self.is_new_script_item:
				layer.transition.start()
		
		self.is_new_script_item = False
		
		if layer:
			self.buffer.clear()
			
			# If the layer is opaque we can composite the last layer onto our buffer
			# first.  This will allow us to do transitions between script 'frames'.
			if self.last_layer and self.opaque:
				self.last_layer.composite_next(self.buffer)
			
			layer.composite_next(self.buffer)
			return self.buffer
		else:
			# If this script item has None set for its layer, return None (transparent):
			return None

	def force_next(self, forward=True):
		"""Advances to the next script element in the given direction."""
		self.force_direction = forward


class GroupedLayer(Layer):
	""":class:`.Layer` subclass that composites several sublayers (members of its :attr:`layers` list attribute) together."""
	
	layers = None
	"""List of layers to be composited together whenever this layer's :meth:`~Layer.next_frame` is called.
	
	Layers are composited first to last using each layer's
	:meth:`~procgame.dmd.Layer.composite_next` method.  Compositing is ended after a layer that returns
	non-``None`` from :meth:`~Layer.composite_next` is :attr:`~Layer.opaque`."""
	
	def __init__(self, width, height, layers=None):
		super(GroupedLayer, self).__init__()
		self.buffer = Frame(width, height)
		if layers == None:
			self.layers = list()
		else:
			self.layers = layers

	def reset(self):
		for layer in self.layers:
			layer.reset()

	def next_frame(self):
		self.buffer.clear()
		composited_count = 0
		for layer in self.layers:
			frame = None
			if layer.enabled:
				frame = layer.composite_next(self.buffer)
			if frame != None:
				composited_count += 1
			if frame != None and layer.opaque: # If an opaque layer doesn't draw anything, don't stop.
				break
		if composited_count == 0:
			return None
		return self.buffer

class PanningLayer(Layer):
	"""Pans a frame about on a 128x32 buffer, bouncing when it reaches the boundaries."""
	def __init__(self, width, height, frame, origin, translate, bounce=True):
		super(PanningLayer, self).__init__()
		self.buffer = Frame(width, height)
		self.frame = frame
		self.origin = origin
		self.original_origin = origin
		self.translate = translate
		self.bounce = bounce
		self.tick = 0
		# Make sure the translate value doesn't cause us to do any strange movements:
		if width == frame.width:
			self.translate = (0, self.translate[1])
		if height == frame.height:
			self.translate = (self.translate[0], 0)

	def reset(self):
		self.origin = self.original_origin
	
	def next_frame(self):
		self.tick += 1
		if (self.tick % 6) != 0:
			return self.buffer
		Frame.copy_rect(dst=self.buffer, dst_x=0, dst_y=0, src=self.frame, src_x=self.origin[0], src_y=self.origin[1], width=self.buffer.width, height=self.buffer.height)
		if self.bounce and (self.origin[0] + self.buffer.width + self.translate[0] > self.frame.width) or (self.origin[0] + self.translate[0] < 0):
			self.translate = (self.translate[0] * -1, self.translate[1])
		if self.bounce and (self.origin[1] + self.buffer.height + self.translate[1] > self.frame.height) or (self.origin[1] + self.translate[1] < 0):
			self.translate = (self.translate[0], self.translate[1] * -1)
		self.origin = (self.origin[0] + self.translate[0], self.origin[1] + self.translate[1])
		return self.buffer


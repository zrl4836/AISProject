# -*- coding: utf-8 -*-
"""Controller.

This module is used to send commands to the AirSim simulation in Unreal Engine
from the network.

Authors:
    Maximilian Roth
    Nina Pant
    Yvan Satyawan <ys88@saturn.uni-freiburg.de>

"""
import airsim
import cv2
import pygame
import numpy as np
from timer import Timer
from pygame.locals import K_KP4
from pygame.locals import K_KP6
from pygame.locals import K_KP8
from pygame.locals import K_q
from pygame.locals import K_SPACE


# Define global variables
AIRSIM_WIDTH = 320
AIRSIM_HEIGHT = 64
ADDITIONAL_CROP_TOP = 0

WINDOW_WIDTH = AIRSIM_WIDTH
WINDOW_HEIGHT = AIRSIM_HEIGHT + 50  # Space to put text below the camera view

GRAB_IMAGE_DISTANCE = 0.1  # Meters


class Controller:
    def __init__(self, network):
        """Acts as a controller object that sends and receives data from AirSim.

            This class acts as the interface between the network and the AirSim
            simulation inside of Unreal Engine. It is able to receive camera
            images from AirSim as well as send the driving commands to it and
            is responsible for running the network.

            Control Scheme:
                NUM_4   : Left
                NUM_8   : Forwards
                NUM_6   : Right
                Q       : Quit
                SPACE   : Reset

        Args:
            network (runner.Runner): A PyTorch network wrapped by a runner.
        """
        # Initialize AirSim connection
        self.client = airsim.CarClient()
        self.client.confirmConnection()
        self.client.enableApiControl(True)

        # Set up the network
        self.network = network

        # Set up timers for fps counting
        self._timer = Timer()
        self.save_timer = None
        self._counter = 0

        # Set up display variables
        self._display = None
        self._main_image = None

        # Directions:
        # -1 : Left
        # 0 : Forwards
        # 1 : Right
        self._direction = 0  # Direction defaults to forwards

        # Drive restrictions
        self._max_steering = 0.4
        self._max_throttle = 0.3

        # Quitting
        self._request_quit = False

    def execute(self):
        """"Launch PyGame."""
        pygame.init()
        self.__init_game()
        while not self._request_quit:
            self.__on_loop()
            self.__on_render()

        if self._request_quit:
            pygame.display.quit()
            pygame.quit()
            self.client.enableApiControl(False)  # Give control back to user
            return

    def __init_game(self):
        """Initializes the PyGame window and creates a new episode.

            This is separate from the main init method because the init is
            intended to create an instance of the class, but not to start
            the game objects yet.
        """
        self.__on_reset()

        self._display = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT),
                                                pygame.HWSURFACE
                                                | pygame.DOUBLEBUF)
        # TODO Make PyGame print the text
        print("PyGame started")

    def __on_reset(self):
        """Resets the state of the client."""
        # TODO Make PyGame print the text
        # print("Resetting client")
        self.client.reset()
        self._timer = Timer()
        self.save_timer = Timer()

    def __on_loop(self):
        """Commands to execute on every loop."""
        # Make time tick
        self._timer.tick()
        self.save_timer.tick()

        # Get an image from Unreal
        response = self.client.simGetImage("0",
                                           airsim.ImageType.Scene,
                                           False)
        rgb = None
        if response:
            rgb = self.__response_to_cv(response, 3)
            self._main_image = rgb

        # Get key presses and parse them
        events = pygame.event.get()

        for event in events:
            self.__parse_event(event)

        out = self.network.run_model(self.__to_tensor(rgb), self._direction)
        out = tuple(out.detach.numpy())

        self.__send_command((out[0], 0.35))  # Currently locked throttle to 0.3
        self.counter += 1

        # Print FPS and direction
        # TODO Make this print inside of the PyGame window
        if self._timer.elapsed_seconds_since_lap() > 1.0:
            if self._direction == 0:
                direction = "Forward"
            elif self._direction == -1:
                direction = "Left"
            else:
                direction = "Right"
            print("FPS: {0}, Drive direction: {1}".
                  format(self.counter,
                         direction))
            self.counter = 0
            self._timer.lap()

        pygame.display.update()  # Finally, update the display.

    def __on_render(self):
        return None

    @staticmethod
    def __response_to_cv(r, channels):
        if r.compress:
            image = cv2.imdecode(np.fromstring(r.image_data_uint8,
                                               dtype=np.uint8),
                                 1)
            image = image.reshape(r.height, r.width, channels)
            image = cv2.cvtColor(image[:, :, 0:channels], cv2.COLOR_RGB2BGR)

        else:
            image = np.frombuffer(r.image_data_uint8, dtype=np.uint8)
            image = image.reshape(r.height, r.width, channels + 1)
            image = image[:, :, 0:channels]
        return image

    def __parse_event(self, event):
        """Parses PyGame events.

        Args:
            event (pygame.Event): The PyGame event to be parsed.
        """
        # TODO For each event print what was pressed in the window
        if event.key == K_KP8:
            self._direction = 0
        elif event.key == K_KP4:
            self._direction = -1
        elif event.key == K_KP6:
            self._direction = 1
        elif event.key == K_SPACE:
            self.__on_reset()
        elif event.key == K_q:
            self._request_quit = True

    def __send_command(self, command):
        """Sends driving commands over the AirSim API.

        Args:
            command (tuple): A tuple in the form (steering, throttle).
        """
        car_control = airsim.CarControls()
        car_control.steering = command[0]
        car_control.throttle = command[1]
        self.client.setCarControls(car_control)

    @staticmethod
    def __to_tensor(image):
        """Turns an image into a tensor

        Args:
            image: The image to be converted

        Returns:
            (torch.Tensor) the image as a tensor.
        """
        raise NotImplementedError
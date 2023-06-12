from cProfile import label
import sys
import os
from turtle import color
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from PyQt5 import QtWidgets, QtCore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from Model.Model import Model


class LiveFigureCanvas(FigureCanvas):
    '''
    This is the FigureCanvas in which the live plot is drawn.

    '''
    def __init__(self, x_len:int, y_range, interval:int, model:Model) -> None:
        '''
        :param x_len:       The nr of data points shown in one plot.
        :param y_range:     Range on y-axis.
        :param interval:    Get a new datapoint every .. milliseconds.

        '''
        super().__init__(mpl.figure.Figure())
        # Range settings
        self._x_len_ = x_len
        self._y_range_ = y_range
        self.model = model

        # Store two lists _x_ and _y_
        self._x_ = list(range(0, x_len))
        self._y_ = [0] * x_len
        self._y2_ = [0] * x_len

        # Store a figure ax
        self.figure.set_size_inches(10, 9, forward=True)
        self._ax_ = self.figure.subplots()
        self._ax_.set_ylim(ymin=0, ymax=525) 
        self._ax_.set_ylabel("Power (W)")
        self._ax_.set_xlabel("Data Point")
        self._ax_.set_title("Commanded (Orange) and Received Power (Blue)")
        

        self._line_, = self._ax_.plot(self._x_, self._y_, label="Power Data")     
        self._line2_, = self._ax_.plot(self._x_, self._y2_, label="Commanded Power") 
      
        self.draw()                                                        

        # Initiate the timer
        self._timer_ = self.new_timer(interval, [(self._update_canvas_, (), {})])
        self._timer_.start()
        return

    def _update_canvas_(self, ) -> None:
        '''
        This function gets called regularly by the timer.

        '''
        self._y_ = [np.nan if dataPoint==0 else dataPoint for dataPoint in self.model.getLaserPowerData()][0:self._x_len_]   # Add new datapoint
        self._y2_= [np.nan if dataPoint==0 else dataPoint for dataPoint in self.model.getCurrentLaserPower()][0:self._x_len_]    # Add new datapoint
        self._line_.set_ydata(self._y_)
        self._line_.set_color("blue")
        self._line2_.set_ydata(self._y2_)
        self._line2_.set_color("orange")
        self._ax_.draw_artist(self._ax_.patch)
        self._ax_.draw_artist(self._line_)
        self._ax_.draw_artist(self._line2_)
        self.update()
        self.flush_events()
        return
    
    def updateScale(self, x_len, y_range):
        self._x_len_ = x_len
        self._x_ = list(range(0, x_len))
        self._y_ = [0] * x_len
        self._y2_ = [0] * x_len 
        self._line_, = self._ax_.plot(self._x_, self._y_, label="Power Data")     
        self._line2_, = self._ax_.plot(self._x_, self._y2_, label="Commanded Power") 
        self._ax_.set_ylim(ymin=0, ymax=y_range[1] + 10)
        self._ax_.set_xlim(xmin=0, xmax=x_len)
        self.draw()
        


    def _disconnect(self):
        self._y_ = [0] * self._x_len_
        self._y2_ = [0] * self._x_len_
        self._timer_.stop()



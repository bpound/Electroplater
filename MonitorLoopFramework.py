from datetime import datetime
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation
from random import randrange
import time
import tkinter as tk

class monitorApp(tk.Frame):
    def __init__(self,parent):
        tk.Frame.__init__(self,parent,width="100",height="100")
        self.timer =  ' '
        self.label = tk.Label(parent)
        self.label.pack()
        self.sbutton=tk.Button(parent,text="Start", command=self.startMonitor)
        self.sbutton.pack()
        self.pbutton=tk.Button(parent,text="Pause", command=self.pauseMonitor,
                               state=tk.DISABLED)
        self.pbutton.pack()
        self.pauseState = 0
        self.fromPause = 0

        self.startPauseTime = 0
        self.stopPauseTime = 0
        self.pauseDiff = 0

        self.animation = ''

        self.startTime = time.time()
        self.x_data, self.y_data = [], []
        self.tPlot, self.aPlot, self.bPlot = [], [], []
        self.figure = plt.figure()
        self.p1 = self.figure.add_subplot(111)
        self.line1, = plt.plot(self.tPlot, self.aPlot, '-')
        self.line2, = plt.plot(self.tPlot,self. bPlot, '-')

    def updateG(self,frame):
        self.nowTime = time.time()
        toPlotTime = self.nowTime - self.startTime - (self.pauseDiff)
        self.tPlot.append(toPlotTime)

        self.aPlot.append(randrange(0, 100))
        self.bPlot.append(randrange(0, 100))

        self.line1.set_data(self.tPlot, self.aPlot)
        self.line2.set_data(self.tPlot, self.bPlot)
        self.figure.gca().relim()
        self.figure.gca().autoscale_view()

        try:
            # total elapsed time in hh:mm:ss
            hr, rem = divmod(self.tPlot[-1] - self.tPlot[0], 3600)

            mins, sec = divmod(rem, 60)
            time_axis_title = "Time (s): Elapsed time is {:0>2} hours, {:0>2} minutes, {:d} seconds".format(int(hr),
                                                                                                            int(mins),
                                                                                                            int(sec))
        except:
            time_axis_title = "Time (s)"

        plt.xlabel(time_axis_title)

        return self.line1,

    def startMonitor(self):
        self.sbutton['state'] = tk.DISABLED
        self.pbutton['state'] = tk.NORMAL
        self.startTime = time.time()
        plt.show()
        self.loopThing()


    def pauseMonitor(self):
        if self.pauseState == 0:
            #self.after_cancel(self.timer)
            self.pbutton.config(text="Unpause")
            self.pauseState = 1
            self.startPauseTime = time.time()

            return
        if self.pauseState == 1:
            print(self.startTime)
            self.pbutton.config(text="Pause")
            self.pauseState = 0
            self.fromPause = 1
            self.stopPauseTime = time.time()
            self.pauseDiff += self.stopPauseTime - self.startPauseTime

            #self.loopThing()
            return

    def stopMonitor(self):
        # Do some stuff of saving the graph and turning off the power supply
        return

    def loopThing(self):
        self.nowTime = time.time()
        toPlotTime = self.nowTime - self.startTime
        self.tPlot.append(toPlotTime)

        if self.pauseState == 1:
            self.aPlot.append(0)
            self.bPlot.append(0)
        else:
            self.aPlot.append(randrange(0, 100))
            self.bPlot.append(randrange(0, 100))


        self.line1.set_data(self.tPlot, self.aPlot)
        self.line2.set_data(self.tPlot, self.bPlot)
        self.figure.gca().relim()
        self.figure.gca().autoscale_view()

        try:
            # total elapsed time in hh:mm:ss
            hr, rem = divmod(self.tPlot[-1] - self.tPlot[0], 3600)

            mins, sec = divmod(rem, 60)
            time_axis_title = "Time (s): Elapsed time is {:0>2} hours, {:0>2} minutes, {:d} seconds".format(int(hr),
                                                                                                            int(mins),
                                                                                                            int(sec))
        except:
            time_axis_title = "Time (s)"

        plt.xlabel(time_axis_title)

        self.timer = self.after(1000, self.loopThing)
            
if __name__ == '__main__':
   root = tk.Tk()
   tapp = monitorApp(root)
   root.mainloop()
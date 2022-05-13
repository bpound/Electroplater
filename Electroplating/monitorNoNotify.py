import tkinter as tk
import time

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from datetime import datetime

import base64
import logging
import os
import os.path
import pickle
import random

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient import errors
from googleapiclient.discovery import build

screenshotPath = "C:\\Users\\Gabriele Domingo\\Pictures\\potato.png"
#pathToLogs may need to be done smarter
curDir = os.getcwd()
pathToLogs = curDir + "\\logFiles"

class monitorApp(tk.Frame):
    ## Important problem
    # Incorporating the pause difference into things inside the loop

    def __init__(self, parent, ps, Notify, V_set, I_set, ps_checking_interval, infuseInterval, infuseRate,
                 okNotifyIntervalMin,
                 error_notify_interval_def, sp, Solenoid, OxySensor, numReads, solenoidLowBound, solenoidHighBound,
                 psName):
        tk.Frame.__init__(self, parent, width="100", height="100")

        self.platingType = ""
        self.useSolenoidandOxy = False

        ## Important subobjects
        self.ps = ps
        self.sp = sp
        self.Notify = Notify
        self.Solenoid = Solenoid
        self.OxySensor = OxySensor

        ## Parameters for the power supply
        self.vTar = V_set[0]
        self.iTar = I_set
        self.vHigh = V_set[2]
        self.vLow = V_set[1]
        self.ps_checking_interval = ps_checking_interval  ## MAIN Time interval for a lot of the code, a lot of other
        ## actions will be dependent on this (def: 5)
        self.psName = psName


        ## Parameters for the syringe pump
        self.infuseInterval = infuseInterval
        self.infuseRate = infuseRate
        self.infusionDone = False
        self.startInfusionTime = 10  # Time when we want to start the infusion in something

        ## Parameters for 02 sensor
        self.numReads = numReads

        ## Parameters for the solenoid
        self.solenoidStartTime = 0
        self.solenoidLowBound = solenoidLowBound  # Percentages
        self.solenoidHighBound = solenoidHighBound

        ## Parameters for the notifyClass
        self.okNotifyIntervalMin = okNotifyIntervalMin  # Minutes between standard notifications
        self.errorNotifyInterval = error_notify_interval_def  # Minimum minutes between the monitorApp sending an error notificiation
        self.error_notify_count = 0  # Total number of errors occured during a run
        self.error_notify_cnt_MAX = 8  # Max TOTAL number of errors, not sure if I'm even gonna use this
        self.lastStandardNotifyTime = 0  # Last STANDARD notification time
        self.lastErrorNotifyTime = 0
        self.failLast20Min = 0
        self.failLast20Threshold = 20

        ## Parameters for internal timing
        self.startTime = time.time()
        self.pauseState = 0
        self.fromPause = 0
        self.startPauseTime = 0
        self.stopPauseTime = 0
        self.pauseDiff = 0

        self.doReplenishment = False
        self.sendReplenishUpdates = False

        ## Parameters for plotting the voltage and current
        self.x_data, self.y_data = [], []
        self.tPlot, self.aPlot, self.bPlot = [], [], []
        self.figure = plt.figure()
        self.p1 = self.figure.add_subplot(111)
        self.line1, = plt.plot(self.tPlot, self.aPlot, '-')
        self.line2, = plt.plot(self.tPlot, self.bPlot, '-')

    def __str__(self):
        return "I am alive, is nice."

    def __repr__(self):
        return "I am alive, is nice"

    def printParams(self):
        print("\nPRINTING CURRENT PARAMETERS \n")
        print("TARGET VOLTAGE (Volts): " + str(self.vTar))
        print("TARGET CURRENT (Amps): " + str(self.iTar))
        print("HIGH VOLTAGE BOUND (Volts): " + str(self.vHigh))
        print("LOW VOLTAGE BOUND (Volts): " + str(self.vLow))
        print("POWER SUPPLY CHECKING INTERVAL (Seconds): " + str(self.ps_checking_interval))
        print("SYRINGE INFUSION INTERVAL (Hours): " + str(self.infuseInterval))
        print("SYRINGE INFUSION RATE ([some prefix]L/s): " + str(self.infuseRate))
        print("NUMBER OF OXYGEN READS TO CALIBRATE: " + str(self.numReads))
        print("SOLENOID LOW BOUND (%): " + str(self.solenoidLowBound))
        print("SOLENOID HIGH BOUND (%): " + str(self.solenoidHighBound))
        print("STANDARD NOTIFY INTERVAL (minutes): " + str(self.okNotifyIntervalMin))
        print("ERROR NOTIFY INTERVAL (minutes): " + str(self.errorNotifyInterval))
        print("")
        print("Plating type: " + self.platingType)
        print("Use Solenoid and Oxygen Sensor? " + str(self.useSolenoidandOxy))

    def setParams(self,
                  vTar,
                  iTar,
                  vHigh,
                  vLow,
                  ps_checking_interval,
                  infuseInterval,
                  infuseRate,
                  replenishUpdateInterval,
                  numReads,
                  solenoidLowBound,
                  solenoidHighBound,
                  okNotifyIntervalMin,
                  errorNotifyInterval,
                  plateOption,
                  solenoidOn):
        # Power Supply
        self.vTar = vTar
        self.iTar = iTar
        self.vHigh = vHigh
        self.vLow = vLow
        self.ps_checking_interval = ps_checking_interval

        # Syringe Pump
        self.infuseInterval = infuseInterval
        self.infuseRate = infuseRate
        self.replenishUpdateInterval = replenishUpdateInterval

        # O2 Sensor
        self.numReads = numReads

        # Solenoid
        self.solenoidLowBound = solenoidLowBound
        self.solenoidHighBound = solenoidHighBound

        self.solenoidClosedFlag = False  # Flags triggered when the solenoid is closed or open in order to prevent Solenoid code from being repeated
        self.solenoidOpenedFlag = False

        # Notify Class
        self.okNotifyIntervalMin = okNotifyIntervalMin
        self.errorNotifyInterval = errorNotifyInterval

        self.platingType = plateOption

        if solenoidOn == 1:
            self.useSolenoidandOxy = True
        if solenoidOn == 0:
            self.useSolenoidandOxy = False

    def openSolenoid(self):
        self.Solenoid.open_solenoid()
        self.Solenoid.open_solenoid()

    def closeSolenoid(self):
        self.Solenoid.close_solenoid()

    def getPauseDiff(self):
        return self.pauseDiff

    def getPauseState(self):
        return self.pauseState

    def testMonitorFunctions(self):
        #Calls every function in the
        return

    def startMonitor(self):
        ## Parameters updated one last time in the main file under startElectroplating()
        self.ps.run(self.vTar, self.iTar)

        self.startTime = time.time()
        self.oldTime = self.startTime
        self.lastInfuseTime = self.startTime
        self.lastStandardNotifyTime = self.startTime
        self.lastErrorNotifyTime = self.startTime
        self.nowTime = self.startTime
        self.totalI = 0

        self.vOld = self.vTar
        self.iOld = self.iTar

        self.solenoidState = "Open"
        self.solenoidClosedFlag = False

        now = datetime.now().strftime("%m_%d_%Y %H_%M_%S")
        self.runLog = open(pathToLogs+"\\"+self.psName+" "+now+".txt","w+")
        self.runLog.write("### ELECTROPLATING PARAMETERS ###\n")
        self.runLog.write("#Plating Start Time (month_day_year hr_min_sec): \t" + now + "\n")
        self.runLog.write("#Power Supply: \t\t" + self.psName + "\n")
        self.runLog.write("#Max Voltage: \t\t" + str(self.vHigh) + "\n")
        self.runLog.write("#Set Current: \t\t" + str(self.iTar) + "\n")
        self.runLog.write("#N2 Purge (Use Solenoid)?: \t\t" + "\n")
        self.runLog.write("\n\n")

        self.loopThing()


    def pauseMonitor(self):
        if self.pauseState == 0:
            self.pauseState = 1
            self.startPauseTime = time.time()

            self.ps.run(0, 0)

            self.callback
            return
        if self.pauseState == 1:
            self.pauseState = 0
            self.fromPause = 1

            self.stopPauseTime = time.time()

            self.pauseDiff += self.stopPauseTime - self.startPauseTime

            self.ps.run(self.vTar, self.iTar)

            self.callback
            return

    def stopMonitor(self):
        print("Stopping Electroplating")
        self.ps.stop()
        # Do some stuff of saving the graph and turning off the power supply
        st = datetime.now()

        # self.figure.savefig("IV_Plot_",st)
        self.infusionDone = False
        self.currentInfusions = 0

        self.after_cancel(self.callback)
        self.runLog.close()
        return

    def loopThing(self):
        '''
        Pseudocode:
        Save old time
        Get new time
        save important time deltas

        toPlotTime: Time to be sent to the plotting routine (DOES NOT ACCOUNT FOR WHEN THE monitorAPP is paused)
        tempTimeDelta = the time since our last point of reference (ACCOUNTS FOR WHEN THE monitorAPP is paused)
        solenoidOpened/Closed Flag: Flags that trigger when the solenoid switches state. Used to make sure they don't accidently trigger the other case

        Power supply checking, error case flow:

            -Attempt to read from power supply
                -Couldn't read from power supply?
                    -Add a fail to the last20Min count
                    -Are we above our threshold?
                        *NOTIFY CASE: FAIL THRESHOLD REACHED

                -Succesfully read power supply
                    -Check if our voltage is out of bounds
                        -Add a fail to last20Min count
                        -Are we above our threshold?
                            *NOTIFY CASE: FAIL THRESHOLD REACHED
                        -Has it been more than errorNotifyInterval minutes since we last complained?
                            *NOTIFY CASE: VOLTAGE READING OUT OF BOUNDS
                    -Check if our current is out of bounds
                        -Add a fail to last20Min count
                        -Are we above our threshold?
                            *NOTIFY CASE: FAIL THRESHOLD REACHED
                        -Has it been more than errorNotifyInterval minutes since we last complained?
                            *NOTIFY CASE: VOLTAGE READING OUT OF BOUNDS

                    -Else we good, continue to the rest of the loop

        '''

        self.oldTime = self.nowTime
        self.nowTime = time.time()
        toPlotTime = self.nowTime - self.startTime

        # Check if it is time to send a notification
        tempTimeDelta = self.nowTime - self.lastStandardNotifyTime - self.pauseDiff
        tempInfusedamtq = 0

        # PERMALLOY & IF its checkbox is ticked
        ### Check if we need to close or open the solenoid
        # Read 02 sensor

        if self.platingType == "PERMALLOY" and self.useSolenoidandOxy == True:
            newVOxy, newO2 = self.OxySensor.read_O2_conc(self.solenoidState)
            # if 02 > 2%
            if newO2 > self.solenoidHighBound and self.solenoidOpenedFlag == False:
                #   Run open solenoid
                print("Opening Solenoid")
                self.solenoidState = "Open"
                self.Solenoid.open_solenoid()
                self.solenoidStartTime = time.time()

                self.solenoidClosedFlag = False
                self.solenoidOpenedFlag = True

                now = datetime.now().strftime("%m_%d_%Y %H_%M_%S")
                self.runLog.write(now + "\t\t Solenoid Opened")

            # if 02 < 0.5% or ran for more than 5 minutes
            if newO2 < self.solenoidLowBound or (
                    self.nowTime - self.solenoidStartTime) / 60.0 > 5 and self.solenoidClosedFlag == False:
                #   Run close solenoid
                print("Closing Solenoid")
                self.solenoidState = "Closed"
                self.Solenoid.close_solenoid()

                self.solenoidClosedFlag = True
                self.solenoidOpenedFlag = False

                now = datetime.now().strftime("%m_%d_%Y %H_%M_%S")
                self.runLog.write(now + "\t\t Solenoid Closed")

        successfulRead = True
        # Something wrong with timeErrorDelta. Constantly being 5 which is just the time gap between reads.
        # Logic Error. nowTime only updates every 5 seconds at the start of the tick while the lastErrorNotifyTime
        # updates itself at the end of every tick. Therefore if we have an error, we will only know about it
        # 5 seconds later after it has happened (also units on Time since last error message is wrong)

        def calcTimeErrorDelta():
            return self.nowTime - self.lastErrorNotifyTime - self.pauseDiff

        print("")
        print("Now Time: " + str(self.nowTime))
        print("Old Time: " + str(self.oldTime))
        print("Last Error Notification: " + str(self.lastErrorNotifyTime))
        print("tempTimeDelta: " + str(tempTimeDelta))

        # Attempt to read the power supply
        if self.pauseState == 0:
            try:
                vNew, iNew = self.ps.read_V_I()
                now = datetime.now().strftime("%m_%d_%Y %H_%M_%S")
                self.runLog.write(now + "\t Power Supply Queried\t V: " +str(vNew) + "\t I: " + str(iNew) + "\n")

            except:
                # Save time of power supply read error
                self.lastErrorNotifyTime = time.time()
                vNew = self.vOld
                iNew = self.iOld

                self.failLast20Min = self.failLast20Min + 1
                successfulRead = False
                print("Failed to get measurment - sleeping and skipping to next iteration hoping that the problem was not fatal")

                now = datetime.now().strftime("%m_%d_%Y %H_%M_%S")
                self.runLog.write(now + "\t Power Supply Read Failed\n")

                if float(calcTimeErrorDelta()/ 60) > float(self.errorNotifyInterval):
                    print("Reading Failed Notify")
                    #self.Notify.notify("Reading Failed", vNew, iNew, tempInfusedamtq, '', [0, 0])
                if self.failLast20Min > self.failLast20Threshold:
                    print("Fail Threshold Notify")
                    #self.Notify.notify("Fail Threshold Reached", vNew, iNew, tempInfusedamtq, '', [0, 0])
                    # NOTIFY CASE: FAIL THRESHOLD REACHED
                    pass

        self.vOld = vNew
        self.iOld = iNew

        # print("Current out of bounds? " + str(iNew < (self.iTar - self.iTar * 0.1) or iNew > (self.iTar + self.iTar * 0.1)))

        if successfulRead == True and self.pauseState == 0:
            print("Checking notify cases")
            if self.failLast20Min > self.failLast20Threshold:
                print("Fail Threshold Notify")
                #self.Notify.notify("Fail Threshold Reached", vNew, iNew, tempInfusedamtq, '', [0, 0],
                            #       self.failLast20Min)
                now = datetime.now().strftime("%m_%d_%Y %H_%M_%S")
                self.runLog.write(now + "\t Fail Threshold Reached\n")

            if tempTimeDelta / 60 >= 20 and self.pauseState == 0:
                self.lastStandardNotifyTime = time.time()  # Place a time new reference to create notifications from
                self.failLast20Min = 0
                print("Standard Notify")
                #self.Notify.notify("Standard", vNew, iNew, tempInfusedamtq, '', [0, 0], self.failLast20Min)

                now = datetime.now().strftime("%m_%d_%Y %H_%M_%S")
                self.runLog.write(now + "\t Standard Notification Sent\n")

                # NOTIFY CASE: STANDARD CASE

            if tempTimeDelta / 60 >= self.okNotifyIntervalMin and self.pauseState == 0:
                self.lastStandardNotifyTime = time.time()
                # NOTIFY CASE: STANDARD 20 MIN
                print("Standard Notify")
                #self.Notify.notify("Standard", vNew, iNew, tempInfusedamtq, '', [0, 0], self.failLast20Min)
                self.failLast20Min = 0

            if vNew > self.vHigh or vNew < self.vLow:
                if self.failLast20Min == 0:  # Send a notification error for the first time in 20 minutes regardless
                    # NOTIFY CASE: VOLTAGE OUT OF BOUNDS
                    self.lastErrorNotifyTime = time.time()
                    print("Sending 1st Out of Bounds Message")
                    print("Voltage bound notify")
                    #self.Notify.notify("Voltage Out of Bounds", vNew, iNew, tempInfusedamtq, '', [0, 0],
                                      # self.failLast20Min)
                    now = datetime.now().strftime("%m_%d_%Y %H_%M_%S")
                    self.runLog.write(now + "\t Voltage Out of Bounds: 1st in 20 min.\n")

                    pass
                if (self.nowTime - self.lastErrorNotifyTime) / 60 >= self.errorNotifyInterval:
                    # NOTIFY CASE: VOLTAGE OUT OF BOUNDS
                    print("Sending 2nd+ Out of Bounds Message")
                    print("Voltage Bound Notify")
                    #self.Notify.notify("Voltage Out of Bounds", vNew, iNew, tempInfusedamtq, '', [0, 0],
                                     #  self.failLast20Min)
                    self.lastErrorNotifyTime = time.time()

                    now = datetime.now().strftime("%m_%d_%Y %H_%M_%S")
                    self.runLog.write(now + "\t Voltage Out of Bounds: Repeated in 20 min.\n")

                    pass
                self.failLast20Min = self.failLast20Min + 1

            if iNew < (self.iTar - self.iTar * 0.1) or iNew > (self.iTar + self.iTar * 0.1):
                print("Current out of Range")
                self.lastErrorNotifyTime = time.time()
                if self.failLast20Min == 0:
                    # NOTIFY CASE: CURRENT OUT OF BOUNDS
                    self.lastErrorNotifyTime = time.time()
                    print("Current Notify")
                    #self.Notify.notify("Current outside range", vNew, iNew, tempInfusedamtq, '', [0, 0],
                                      # self.failLast20Min)
                    pass
                if (self.nowTime - self.lastErrorNotifyTime) / 60 >= self.errorNotifyInterval:
                    # NOTIFY CASE: CURRENT OUT OF BOUNDS
                    self.lastErrorNotifyTime = time.time()
                    print("Current Notify")
                    #self.Notify.notify("Current outside range", vNew, iNew, tempInfusedamtq, '', [0, 0],
                                 #      self.failLast20Min)
                    pass
                self.failLast20Min = self.failLast20Min + 1

        print("Time since last error message (sec): " + str(calcTimeErrorDelta()))
        print("Fail last 20 min: " + str(self.failLast20Min))

        # RUN IF COPPER ONLY. TURN OFF FOR PERMALLOY
        # Assumption: Infusion time is max 5 seconds (to not break power supply checking interval)
        # Check if it is time to run the infusion (ONLY WHEN WE ARE DOING... nickel?)

        if (self.nowTime - self.lastInfuseTime - self.pauseDiff) / 3600.0 > 1:
            self.doReplenishment = True

        if self.platingType == "COPPER":
            # After 1 hours, do replenishment
            # Turn on flag to send replenishment status updates
            if self.doReplenishment == True and (
                    self.nowTime - self.lastInfuseTime - self.pauseDiff) / 3600.0 > self.infuseInterval and self.pauseState == 0:
                self.sendReplenishUpdates = True
                self.lastReplenishUpdateTime = self.nowTime

                totalT = self.nowTime - self.lastInfuseTime - self.pauseDiff

                # take the total I and divide it by the total time to get the average current over the time period
                try:
                    I_avg = (self.total_I) / totalT
                except:
                    I_avg = 0

                # reset the reference timer and total_I
                self.total_I = 0

                # set the infuse parameters and run the pump
                self.sp.set_parameters(I_avg, self.infuseRate, self.infuseInterval)
                time.sleep(0.1)
                self.sp.infuse()
                time.sleep(0.1)
            else:
                self.totalI = self.totalI + iNew * (self.nowTime - self.oldTime)

            now = datetime.now().strftime("%m_%d_%Y %H_%M_%S")
            self.runLog.write(now + "\t\t Syringe Replenishment Done")

            # After we have finished the number of infusions we want, we now monitor it
            # if sendReplenish Updates flag is true
            if (self.sendReplenishUpdates == True and (
                    self.nowTime - self.lastReplenishUpdateTime - self.pauseDiff) / 3600.0 > self.replenishUpdateInterval):
                infused_volume, infuse_rate = self.sp.check_rate_volume()
                curr_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                new_infusion = '%s : infused %.3f uL replenisher after %.2f hours at %.3f uL/s with %.3f A average current.' % (
                    curr_time, infused_volume, self.infuseInterval, infuse_rate, I_avg)

                if self.sp.use_flag is True:  # Check what use_flag does
                    self.sp.infusion_list.append(new_infusion)
                    print("# infusions: ", len(self.sp.infusion_list))

        ## Add the new voltage and current readings into the plot
        plt.ion()
        self.tPlot.append(toPlotTime)
        self.aPlot.append(vNew)
        self.bPlot.append(iNew)
        self.line1.set_data(self.tPlot, self.aPlot)
        self.line2.set_data(self.tPlot, self.bPlot)
        plt.draw()
        #self.figure.draw()
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
        plt.legend(['Voltage', 'Current'])
        plt.xlabel(time_axis_title)
        plt.show()
        ## Wait 5 seconds (or probably change depending on the entry to the power supply checking interval) then run again
        print("Looped\n\n")
        self.callback = self.after(5000, self.loopThing)

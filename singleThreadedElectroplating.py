#Talk to outside things modules and adjusting Python Interpreter
from datetime import datetime
from twilio.rest import Client
import time,pyvisa

import matplotlib.pyplot as plt

import base64
import logging
import mimetypes
import os
import os.path
import pickle
import uuid
import threading
import serial


#import board
#import busio
#import adafruit_ads1x15.ads1115 as ADS
#from adafruit_ads1x15.analog_in import AnalogIn


import pyvisa_py
import cgi,html
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.image     import MIMEImage
from email.header         import Header


from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient import errors
from googleapiclient.discovery import build

#GUI modules
import tkinter as tk
import matplotlib.pyplot as plt
from tkinter import scrolledtext

try:
    import RPi.GPIO as GPIO
except:
    import Mock.GPIO as GPIO

class O2_Sensor():
    def __init__(self, numReads):

        ### setup the adc to read the O2 sensor
        # create the I2C bus
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            # create the adc object using the I2C bus
            ads = ADS.ADS1115(i2c)
            # set the gain (2/3,1,2,4,8,16); probably doesn't do anything since we use the voltage reading directly
            ads.gain = 1
        except:
            print("Something went wrong with 02 Sensor Intialization")

        # create differential input chetween channel 0 and 1. No need to set the gain, we will use the voltage directly.
        try:
            self.chan = AnalogIn(ads, ADS.P0, ADS.P1)
        except:
            print("Something went wrong with O2 Sensor Initialization")

        # put default values for calibration here
        self.o2_percent = 20.9  # percentage of O2 in plating lab; since we are close to sea level, I use 20.9
        self.o2_b = 0  # [V] "base" value that the O2 sensor outputs in 0% O2
        self.o2_a = 0.011  # [V] "atmospheric" value, that the O2 sensor outputs in normal air, which is 20.9% O2 at sea level

        # calculate conversion factor
        self.conversion_factor = 0
        self._calculate_conversion_factor()  # assigns value directly to self.conversion_factor

        # number of reads to do during calibration
        self.numReads = numReads

    def updateNumReads(self,numReads):
        self.numReads = numReads

    def _calculate_conversion_factor(self):
        # conversion factor to convert volts to O2 concentration
        print('old conversion factor: %.6f [percent/V]' % (self.conversion_factor))
        self.conversion_factor = self.o2_percent / (
                    self.o2_a - self.o2_b)  # divide by 1000 to convert o2_a/b from [mV] to [V]
        print('new conversion factor: %.6f [percent/V]' % (self.conversion_factor))

    def calibrate(self):

        # take ten measurements in normal atmostphere, average, and assign value of 20.9% O2
        print('old value of o2_a: %.6f [V]' % (self.o2_a))
        o2_a = 0
        for ii in range(self.numReads):
            o2_a += self.chan.voltage

        self.o2_a = o2_a / self.numReads  # get new averaged o2_a value

        print('new value of o2_a: %.6f [V]' % (self.o2_a))
        self._calculate_conversion_factor()  # calculate new conversion factor

    def read_O2_conc(self):

        newV_settled = 0
        newO2perc_settled = 0
        for ii in range(self.numReads):
            newV = self.chan.voltage
            new_O2_perc_value = newV * self.conversion_factor

            newV_settled += newV
            newO2perc_settled += new_O2_perc_value
            time.sleep(0.01)

        # gets average
        newV_settled = newV_settled / self.numReads
        newO2perc_settled = newO2perc_settled / self.numReads

        return newV_settled, newO2perc_settled

class Solenoid_Controller():
    def __init__(self):
        ## initial setup
        self.control_pin = 37
        self.status = 0  # 0 is closed, 1 is open

        # set the board pin number address scheme. We want to use pin 37 for signal. The ground is plugged into pin 39 (doesn't need to be controlled, obviously)
        GPIO.setmode(GPIO.BOARD)

        # set up pin 37 as output
        GPIO.setup(self.control_pin, GPIO.OUT)

    def open_solenoid(self):
        GPIO.output(self.control_pin, GPIO.HIGH)
        self.status = 1

    def close_solenoid(self):
        GPIO.output(self.control_pin, GPIO.LOW)
        self.status = 0

    def cleanup(self):
        if self.status == 1:  # if its open, shut it before continuing
            self.close_solenoid()
        GPIO.cleanup()


class monitorApp(tk.Frame):
    ## Important problem
    # Incorporating the pause difference into things inside the loop

    def __init__(self,parent,ps,Notify,V_set,I_set,ps_checking_interval,infuseInterval,infuseRate,okNotifyIntervalMin,
                 error_notify_interval_def,sp,Solenoid,OxySensor,numReads,solenoidLowBound,solenoidHighBound):
        tk.Frame.__init__(self,parent,width="100",height="100")

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
        self.vHigh = V_set[1]
        self.vLow = V_set[2]
        self.ps_checking_interval = ps_checking_interval ## MAIN Time interval for a lot of the code, a lot of other
                                                         ## actions will be dependent on this (def: 5)

        ## Parameters for the syringe pump
        self.infuseInterval = infuseInterval
        self.infuseRate = infuseRate
        self.infusionDone = False
        self.startInfusionTime = 10 # Time when we want to start the infusion in something

        ## Parameters for 02 sensor
        self.numReads = numReads

        ## Parameters for the solenoid
        self.solenoidStartTime = 0
        self.solenoidLowBound = solenoidLowBound # Percentages
        self.solenoidHighBound = solenoidHighBound

        ## Parameters for the notifyClass
        self.okNotifyIntervalMin = okNotifyIntervalMin # Minutes between standard notifications
        self.errorNotifyInterval = error_notify_interval_def # Minimum minutes between the monitorApp sending an error notificiation
        self.error_notify_count = 0 # Total number of errors occured during a run
        self.error_notify_cnt_MAX = 8 # Max TOTAL number of errors, not sure if I'm even gonna use this
        self.lastStandardNotifyTime = 0 # Last STANDARD notification time
        self.lastErrorNotifyTime = 0
        self.failLast20Min = 0
        self.failLast20Threshold = 10

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
        self.line2, = plt.plot(self.tPlot,self.bPlot, '-')

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

    def closeSolenoid(self):
        self.Solenoid.close_solenoid()

    def getPauseDiff(self):
        return self.pauseDiff

    def getPauseState(self):
        return self.pauseState

    def startMonitor(self):
        self.ps.run(self.vTar,self.iTar)

        self.startTime = time.time()
        self.oldTime = self.startTime
        self.lastInfuseTime = time.time()
        self.nowTime = time.time()
        self.totalI = 0

        self.loopThing()

    def pauseMonitor(self):
        if self.pauseState == 0:
            self.pauseState = 1
            self.startPauseTime = time.time()

            self.ps.run(0,0)

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
        self.ps.stop()
        # Do some stuff of saving the graph and turning off the power supply
        st = datetime.now()

        #self.figure.savefig("IV_Plot_",st)
        self.infusionDone = False
        self.currentInfusions = 0

        self.after_cancel(self.callback)
        return

    def loopThing(self):
        '''
        Pseudocode:
        Save old time
        Get new time
        save important time deltas

        toPlotTime: Time to be sent to the plotting routine (DOES NOT ACCOUNT FOR WHEN THE monitorAPP is paused)
        tempTimeDelta = the time since our last point of reference (ACCOUNTS FOR WHEN THE monitorAPP is paused)

        '''

        self.oldTime = self.nowTime
        self.nowTime = time.time()
        toPlotTime = self.nowTime - self.startTime

        # Check if it is time to send a notification
        tempTimeDelta = self.nowTime - self.lastStandardNotifyTime - self.pauseDiff
        print(tempTimeDelta)

        tempInfusedamtq = 0

        # Think about the time that the thing is paused affecting notify time
        ## Check if it is time to send a normal notification


        #Attempt to read the power supply
        '''
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

        # PERMALLOY & IF its checkbox is ticked
        ### Check if we need to close or open the solenoid
        # Read 02 sensor

        if self.platingType == "PERMALLOY" and self.useSolenoidandOxy:
            newVOxy, newO2 = self.OxySensor.read_O2_conc()
            # if 02 > 2%
            if newO2 > self.solenoidHighBound:
                #   Run open solenoid
                self.Solenoid.open_solenoid()
                self.solenoidStartTime = time.time()
            # if 02 < 0.5% or ran for more than 5 minutes
            if newO2 < self.solenoidLowBound or self.nowTime - self.solenoidStartTime / 60.0 > 5:
                #   Run close solenoid
                self.Solenoid.close_solenoid()

        successfulRead = True
        timeErrorDelta = self.nowTime - self.lastErrorNotifyTime
        if self.pauseState == 0:
            try: vNew, iNew = self.ps.read_V_I()
            except:
                self.failLast20Min = self.failLast20Min + 1
                successfulRead = False
                print("Failed to get measurment - sleeping and skipping to next iteration hoping that the problem was not fatal")

                if timeErrorDelta/60 > self.errorNotifyInterval:
                    self.Notify.notify("Reading Failed",vNew,iNew,tempInfusedamtq,'',[0, 0])
                if self.failLast20Min > self.failLast20Threshold:
                    self.Notify.notify("Fail Threshold Reached", vNew,iNew,tempInfusedamtq,'',[0,0])
                    # NOTIFY CASE: FAIL THRESHOLD REACHED
                    pass

        if successfulRead == True and self.pauseState == 0:
            if tempTimeDelta / 60 >= 20 and self.pauseState == 0:
                self.lastStandardNotifyTime = time.time()  # Place a time new reference to create notifications from
                self.failLast20Min = 0
                self.Notify.notify("Standard", vNew, iNew, tempInfusedamtq, '', [0, 0])
                # NOTIFY CASE: STANDARD CASE

            if tempTimeDelta / 60 >= self.okNotifyIntervalMin and self.pauseState == 0:
                # NOTIFY CASE: STANDARD 20 MIN
                self.Notify.notify("Standard", vNew, iNew, tempInfusedamtq, '', [0, 0])

                self.failLast20 = 0

            if vNew > self.vHigh or vNew < self.vLow:
                self.failLast20Min = self.failLast20Min + 1
                if self.failLast20Min == 0:  # Send a notification error for the first time in 20 minutes regardless
                    # NOTIFY CASE: VOLTAGE OUT OF BOUNDS
                    self.Notify.notify("Voltage Out of Bounds", vNew, iNew, tempInfusedamtq, '', [0, 0])
                    pass
                if tempTimeDelta-self.lastErrorNotifyTime/60 >= self.errorNotifyInterval:
                    # NOTIFY CASE: VOLTAGE OUT OF BOUNDS
                    self.Notify.notify("Voltage Out of Bounds", vNew, iNew, tempInfusedamtq, '', [0, 0])
                    pass

            if iNew < (self.iTar - self.iTar * 0.1) or iNew > (self.iTar + self.iTar * 0.1):
                self.failLast20Min = self.failLast20Min + 1
                if self.failLast20Min == 0:
                    # NOTIFY CASE: CURRENT OUT OF BOUNDS
                    self.Notify.notify("Current Out of Bounds", vNew, iNew, tempInfusedamtq, '', [0, 0])
                    pass
                if tempTimeDelta-self.lastErrorNotifyTime/60 >= self.errorNotifyInterval:
                    # NOTIFY CASE: CURRENT OUT OF BOUNDS
                    self.Notify.notify("Current Out of Bounds", vNew, iNew, tempInfusedamtq, '', [0, 0])
                    pass

        # RUN IF COPPER ONLY. TURN OFF FOR PERMALLOY
        # Assumption: Infusion time is max 5 seconds (to not break power supply checking interval)
        # Check if it is time to run the infusion (ONLY WHEN WE ARE DOING... nickel?)

        if (self.nowTime - self.lastInfuseTime- self.pauseDiff)/3600.0 > 1:
            self.doReplenishment = True

        if self.platingType == "COPPER":
            # After 1 hours, do replenishment
                # Turn on flag to send replenishment status updates
            if self.doReplenishment == True and (self.nowTime - self.lastInfuseTime - self.pauseDiff)/3600.0 > self.infuseInterval and self.pauseState == 0:
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

            # After we have finished the number of infusions we want, we now monitor it
            # if sendReplenish Updates flag is true
            if (self.sendReplenishUpdates == True and (self.nowTime - self.lastReplenishUpdateTime - self.pauseDiff)/3600.0 > self.replenishUpdateInterval):
                infused_volume, infuse_rate = self.sp.check_rate_volume()
                curr_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                new_infusion = '%s : infused %.3f uL replenisher after %.2f hours at %.3f uL/s with %.3f A average current.' % (
                    curr_time, infused_volume, self.infuseInterval, infuse_rate, I_avg)

                if self.sp.use_flag is True: #Check what use_flag does
                    self.sp.infusion_list.append(new_infusion)
                    print("# infusions: ", len(self.sp.infusion_list))

        ## Add the new voltage and current readings into the plot
        self.tPlot.append(toPlotTime)
        self.aPlot.append(vNew)
        self.bPlot.append(iNew)
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
        plt.legend(['Voltage', 'Current'])
        plt.xlabel(time_axis_title)

        ## Wait 5 seconds (or probably change depending on the entry to the power supply checking interval) then run again
        print("Looped")
        self.callback = self.after(5000, self.loopThing)


class CreateToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.waittime = 500     #miliseconds
        self.wraplength = 180   #pixels
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None
    def enter(self, event=None):
            self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = tk.Toplevel(self.widget)
        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background="#ffffff", relief='solid', borderwidth=1,
                       wraplength = self.wraplength)
        label.pack(ipadx=1)
    def hidetip(self):
        tw = self.tw
        self.tw= None
        if tw:
            tw.destroy()

class NotifyCSingle():
    '''
    Changes to multithreated version:
    There seems to be no reliance on multicore processing in the class
    What most likely will need to be looked at at the v_new, i_new parameters in the notify function, but that
    will be dependent on how the read power supply values will be handled. Overall, no changes to the internal
    NotifyC class may be needed, mainly just how it is used in the actual code.

    Main concerns:
    V_bounds and I_bounds

        Since the bounds of v and i are to be dynamically chosen (put in the GUI) would it be wiser to initialize
        the notifyC class ONCE we start electroplating?

        FIX: Literally make a getter and setter for the v and i bounds to be able to change whenever those bounds
        are edited in the GUI

    error_notify_interval and notify_interval

        Ok yeah these will need to be dynamically changed from the gui as well. Probably just need to do a
        setter and getter like for the bounds and just bind the entries to execute those functions when they exit

    Changing emailing protocol

        Need to change how the emails are sent to google's api for a more secure, less annoying user experience
        Implementing the GoogleEmailAPI appears to have two important problems:
            1) How the hell are we getting the screenshot
            2) How the hell are we creating the message

        Hmm... ok 2 might actually be way easier than I thought as the emailBody will just be created once. Hopefully
        the string variable that is created just... works.

    '''
    # Create hard coded parameters for the googleEmailAPI

    # Now put in the previous version's code
    def __init__(self, SID, AUTH, TO_NUM, FROM_NUM, V_bounds, I_target, error_notify_interval,
                 error_notify_cnt_MAX, notify_interval, notifyType, use_text_only_for_bad_news):

        # create SMS client, and save parameters to dictionary
        sms_client = Client(SID, AUTH)
        twilio_dict = {'client': sms_client, 'to_num': TO_NUM, 'from_num': FROM_NUM}
        self.td = twilio_dict
        self.notifyType = notifyType
        self.notify_interval = notify_interval
        self.V_bounds = V_bounds
        self.I_target = I_target
        self.error_notify_count = 0 # Current amount of errors
        self.error_notify_cnt_MAX = error_notify_cnt_MAX
        self.error_notify_interval = error_notify_interval
        self.error_notify_timer = 0
        self.error_notify_ref = 0 # Start of sending errors?

        self.use_text_only_for_bad_news = use_text_only_for_bad_news

        self.infused_volume = 0
        self.msg = '' #Sends status of motors and stuff in case things break

        # Hardcoded things
        self.fromEmail = "stl.electroplating@gmail.com"
        self.toEmail = ["spokosison@gmail.com"]
        self.pathToScreenshot = "C:\\Users\\Thomas Sison\\Pictures"
        self.nameScreenshot = 'platingCheck.png'
        self.pathToCredentials = "C:\\Users\\Thomas Sison\\Desktop\\credentials.json"
        self.dirToPickle = "C:\\Users\\Thomas Sison\\Desktop"

    # Create googleEmailAPI functions for message protocol. Won't need to be used outside of this class? (Hopefully)
    def get_service(self,pathToCredentials, dirToPickle):
        """Gets an authorized Gmail API service instance.

        pathToCredentials: path, including name, of the credentials .json file

        Returns:
            An authorized Gmail API service instance..
        """

        # If modifying these scopes, delete the file token.pickle.
        SCOPES = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
        ]

        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        picklePath = os.path.join(dirToPickle, 'token.pickle')
        if os.path.exists(picklePath):
            with open(picklePath, 'rb') as token:
                creds = pickle.load(token)

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    pathToCredentials, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(picklePath, 'wb') as token:
                pickle.dump(creds, token)

        service = build('gmail', 'v1', credentials=creds)
        return service

    def send_message(self,service, sender, message):
        """Send an email message.

        Args:
        service: Authorized Gmail API service instance.
        user_id: User's email address. The special value "me"
        can be used to indicate the authenticated user.
        message: Message to be sent.

        Returns:
        Sent Message.
        """
        try:
            sent_message = (service.users().messages().send(userId=sender, body=message).execute())
            logging.info('Message Id: %s', sent_message['id'])
            return sent_message
        except errors.HttpError as error:
            logging.error('An HTTP error occurred: %s', error)

    def create_message(self,sender, to_list, subject, message_text, img1):
        """Create a message for an email.

        Args:
        sender: Email address of the sender.
        to: Email address of the receiver.
        subject: The subject of the email message.
        message_text: The text of the email message.

        Returns:
        An object containing a base64url encoded email object.
        """

        message = MIMEMultipart('related')

        msg_content = '''
        <html><body><p>%s</p><p><img src="cid:screenshot" width="250" height="250"></p></body></html>''' % (
            message_text)
        message.attach(MIMEText((msg_content), 'html'))

        #"img1["path"], 'rb'"

        with open(img1["path"], 'rb') as image_file:
            image = MIMEImage(image_file.read())
        image.add_header('Content-ID', '<screenshot>')
        image.add_header('Content-Disposition', 'inline', filename=img1["path"])
        message.attach(image)

        message['From'] = sender
        message['To'] = ','.join(to_list)
        message['Subject'] = subject

        s = message.as_string()
        b = base64.urlsafe_b64encode(s.encode('utf-8'))
        return {'raw': b.decode('utf-8')}

    # Setters and getters should work the same
    def getIVBounds(self):
        return self.I_bounds,self.V_bounds

    def setIVBounds(self,newIBounds,newVBounds):
        # Sets a new boundary for the current and the voltage in the form of
        # [Low warning, high warning]

        self.I_bounds = newIBounds # [Set current]
        self.V_bounds = newVBounds # [Set (higher), high warning]
        return

    # Probably where most of the things will need to be changed
    def notify(self,case,vNew,iNew,infused_amt_q,msg,notify_list):
        '''

        :param V_new:
        :param I_new:
        :param notify_list:
        :param msg:
        :param infused_amt_q:
        :param typeD:
        :return:

        This function will need to rewritten slightly such that instead of checking the power supply values within it,
        it will rely on cases sent from the monitorApp Class to determine what message to send. For simplicity, we'll
        use strings for the cases:

        "fine"
        "Voltage Low Reading"
        "Voltage High Reading"
        "Reading Failed"
        "Threshold reached"

        It'll probably be best to create a bunch of switch statements


        We will assume that the power supply out of bounds case is independent on the case of current being out of bounds,
        with power supply bounds taking priority
        '''

        # unpack list
        # Totally forgot what this notify list is supposed to do
        notify_time_ref = notify_list[0]
        notify_time = notify_list[1]

        if msg != '':
            self.msg = msg

        # get current time
        current_date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # get infused volume
        infused_vl = self.infused_volume
        for ii in range(infused_amt_q.qsize()):
            infused_vl = infused_vl + infused_amt_q.get()
        self.infused_volume = infused_vl

        if case == "Standard":
            emailBody = '%s. Good.%s V: %.3f V, I: %.3f .A Inf: %.3f uL.' % (
                current_date_time, self.msg, vNew, iNew, infused_vl)
            pass
        if case == "Voltage Out of Bounds":
            emailBody = '%s. Voltage Out of Bounds.%s V: %.3f V, I: %.3f .A Inf: %.3f uL.' % (
                current_date_time, self.msg, vNew, iNew, infused_vl)
            pass
        if case == "Current outside range":
            emailBody = '%s. Current Out of Range.%s V: %.3f V, I: %.3f .A Inf: %.3f uL.' % (
                current_date_time, self.msg, vNew, iNew, infused_vl)
            pass
        if case == "Reading Failed":
            emailBody = '%s. ERROR-%s.%s Warn %d. V: %.3f V, I: %.3f A. Inf: %.3f uL.' % (
                current_date_time, self.msg, self.error_notify_count, vNew, iNew, infused_vl)
            print(emailBody)
        if case == "Fail Threshold Reached":
            emailBody = "Reached more than 20 errors in the last 20 minutes. Most likely due to a problem with the power supply at this point"
            pass

        ## Basic part of the code, will be sent every time

        ## Send text message

        if self.notifyType in [1,3] and self.use_text_only_for_bad_news is False:
            try:
                self.td['client'].messages.create(to=self.td['to_num'], from_=self.td['from_num'], body=emailBody)
            except:
                print("Could not send text message notification, going to hope that the error was not fatal")


        # Get a screenshot the the system?
        fn = os.getcwd() + '/screenshot.png'
        os.system('scrot %s -q 75' % fn)

        pathToScreenshot = fn
        nameScreenshot = "screenshot.png"
        img1 = dict(title='desktop screenshot', path=os.path.join(pathToScreenshot, nameScreenshot))

        try:
            service = self.get_service(self.pathToCredentials, self.dirToPickle)
        except:
            print("Could not establish service")
            return
        try:
            message = self.create_message(self.fromEmail, self.toEmail, "Test subject", emailBody, img1)
        except:
            print("Could not create the test message")
        self.send_message(service, self.fromEmail, message)

        return [notify_time_ref, notify_time]


class E3631A_PS():
    def __init__(self, channel, ps_port, ps_ident):

        # save identification
            self.ident = ps_ident

        # open up Resource Manager
            rm = pyvisa.ResourceManager('@py')

        # open up the right channel
        # the USB resource needs to be figured out beforehand, there is no way to figure out which power supply is
        #try:
            ps = rm.open_resource(ps_port)

            # set address and protocol
            ps.write('++addr %i' % channel)
            ps.write('++eos 0')
            time.sleep(0.01)

            # try to get a response from power supply, in this case its identity
            ps.write('*IDN?')
            ps.write('++read')
            print('Power supply identity: %s , %s' % (ps_port, ps.read().strip()))

            # save communication instance into class variable
            self.ps = ps
        #except:
            print('Something went wrong with power supply initialization.')
            self.ps = None

    def run(self, V, I):

        if self.ps is not None:
            # take output off, set new voltage and current, then turn output back on
            # ps.write('OUTPUT OFF')
            self.ps.write('APPL P6V, %f, %f' % (V, I))

            # check if output is already on
            self.ps.write('OUTPUT?')
            self.ps.write('++read')
            on_flag = self.ps.read().strip()

            if on_flag == '0':
                self.ps.write('OUTPUT ON')

            print('Started power supply output.')
        else:
            print('Cannot run power supply; power supply did not initialize properly.')

    def read_V_I(self):

        if self.ps is not None:
            # query power supply for voltage
            self.ps.write('MEAS:VOLT? P6V')
            self.ps.write('++read')
            voltage = float(self.ps.read().strip())

            # query power supply for current
            self.ps.write('MEAS:CURR? P6V')
            self.ps.write('++read')
            current = float(self.ps.read().strip())
        else:
            print('Cannot measure voltage/current; power supply did not initialize properly.')
            voltage = 1
            current = 1

        return voltage, current

    def stop(self):
        if self.ps is not None:
            self.ps.write('OUTPUT OFF')
            print('Power supply is turned off.')
        else:
            print('Power supply did not initialize properly, so it cannot be turned off if on.')

    def disconnect(self):
        if self.ps is not None:
            self.ps.close()
            print('Power supply has been disconnected.')
        else:
            print('Power supply was not initialized properly, but hopefully is disconnected anyway.')


class E3634A_PS():
    def __init__(self, channel, ps_port, ps_ident):

        # save identification
        self.ident = ps_ident

        # open up Resource Manager
        rm = pyvisa.ResourceManager('@py')

        # open up the right channel
        # the USB resource needs to be figured out beforehand, there is no way to figure out which power supply is
        try:
            ps = rm.open_resource(ps_port)

            # set address and protocol
            ps.write('++addr %i' % channel)
            ps.write('++eos 0')
            time.sleep(0.01)

            # try to get a response from power supply, in this case its identity
            ps.write('*IDN?')
            ps.write('++read')
            print('Power supply identity: %s , %s' % (ps_port, ps.read().strip()))

            # save communication instance into class variable
            self.ps = ps
        except:
            print('Something went wrong with power supply initialization.')
            self.ps = None

    def run(self, V, I):

        if self.ps is not None:
            # take output off, set new voltage and current, then turn output back on
            # ps.write('OUTPUT OFF')
            self.ps.write('VOLTage:RANGe P25V')
            self.ps.write('APPL %f, %f' % (V, I))

            # turn on the output
            self.ps.write('OUTPUT ON')
            print('Started power supply output.')
        else:
            print('Cannot run power supply; power supply did not initialize properly.')

    def read_V_I(self):

        if self.ps is not None:
            # query power supply for voltage
            self.ps.write('MEASURE:VOLTAGE?')
            self.ps.write('++read')
            voltage = float(self.ps.read().strip())

            # query power supply for current
            self.ps.write('MEASURE:CURRENT?')
            self.ps.write('++read')
            current = float(self.ps.read().strip())
        else:
            print('Cannot measure voltage/current; power supply did not initialize properly.')
            voltage = 1
            current = 1

        return voltage, current

    def stop(self):
        if self.ps is not None:
            self.ps.write('OUTPUT OFF')
            print('Power supply is turned off.')
        else:
            print('Power supply did not initialize properly, so it cannot be turned off if on.')

    def disconnect(self):
        if self.ps is not None:
            self.ps.close()
            print('Power supply has been disconnected.')
        else:
            print('Power supply was not initialized properly, but hopefully is disconnected anyway.')

class E36105B_PS():
    def __init__(self, channel, ps_port, ps_ident):

        # save identification
        self.ident = ps_ident

        # open up Resource Manager
        # rm = pyvisa.ResourceManager('@py')

        # open up the right channel
        # the USB resource needs to be figured out beforehand, there is no way to figure out which power supply is
        try:
            ps = usbtmc.Instrument(ps_port)

            # set address and protocol
            # ps.write('++addr %i'%channel)
            # ps.write('++eos 0') #Append CR+LF (ASCII 13 & 10 respectively) to instrument commands
            time.sleep(0.01)

            # try to get a response from power supply, in this case its identity
            idn = ps.ask('*IDN?\n')
            # ps.write('++read')
            print('Power supply identity: %s , %s' % (ps_port, idn))

            # save communication instance into class variable
            self.ps = ps
        except:
            print('Something went wrong with power supply initialization.')
            self.ps = None

    def run(self, V, I):

        if self.ps is not None:
            # take output off, set new voltage and current, then turn output back on
            # ps.write('OUTPUT OFF\n')
            # self.ps.write('VOLTage:RANGe P25V\n')
            self.ps.write('APPL %f, %f\n' % (V, I))

            # turn on the output
            self.ps.write('OUTPUT ON\n')
            print('Started power supply output.')
        else:
            print('Cannot run power supply; power supply did not initialize properly.')

    def read_V_I(self):

        if self.ps is not None:
            # query power supply for voltage
            # self.ps.write('MEASURE:VOLTAGE?')
            measV = self.ps.ask('MEASURE:VOLTAGE?\n')
            # self.ps.write('++read')
            voltage = float(measV)

            # query power supply for current
            # self.ps.write('MEASURE:CURRENT?')
            measI = self.ps.ask('MEASURE:CURRENT?\n')
            # self.ps.write('++read') # Reads until timeout. So what might be happening is that its reading more than one value?
            current = float(measI)
        else:
            print('Cannot measure voltage/current; power supply did not initialize properly.')
            voltage = -1
            current = -1

        return voltage, current

    def stop(self):
        if self.ps is not None:
            self.ps.write('OUTPUT OFF\n')
            print('Power supply is turned off.')
        else:
            print('Power supply did not initialize properly, so it cannot be turned off if on.')

    def disconnect(self):
        if self.ps is not None:
            self.stop()
            self.ps.close()
            print('Power supply has been disconnected.')
        else:
            print('Power supply was not initialized properly, but hopefully is disconnected anyway.')

    def selftest(self):

        # winsound.Beep(440,500)
        input('put the test resistor on the terminals')
        print('watch the power supply, see if the voltage or current reaches the specified levels')
        v = 1;
        i = 0.005
        self.run(v, i)
        print('Desired V, I: %f , %f' % (v, i))
        time.sleep(3)
        # winsound.Beep(440,500)
        v, i = self.read_V_I();
        print('Actual V, I: %f , %f' % (v, i))
        time.sleep(3)
        # winsound.Beep(440,500)
        nv = 0.4
        ni = 0.005
        self.run(nv, ni)
        print('Desired V, I: %f , %f' % (nv, ni))
        time.sleep(3)
        # winsound.Beep(440,500)
        v, i = self.read_V_I();
        print('Actual V, I: %f , %f' % (v, i))
        time.sleep(3)
        # winsound.Beep(440,500)
        ps.stop()
        print('output stopped')
        time.sleep(3)
        # winsound.Beep(440,500)
        v = 1;
        i = 0.005
        self.run(v, i)
        print('Desired V, I: %f , %f' % (v, i))
        time.sleep(3)
        # winsound.Beep(440,500)
        v, i = self.read_V_I();
        print('Actual V, I: %f , %f' % (v, i))
        self.stop()

class Legato100_SP():
    def __init__(self, sp_port, s_manufacturer, s_volume, factor, use_syringe_pump):

        self.use_flag = use_syringe_pump

        self.motorStalled = False

        if use_syringe_pump is False:

            self.sp = None

        else:

            try:
                rm = pyvisa.ResourceManager()
                self.sp = rm.open_resource(sp_port)
                self.sp.query('echo on')
                self.sp.query('ver')
                print('Syringe pump identity: %s , %s' % (sp_port, self.sp.read().strip()))
            except:
                print('something went wrong with syringe pump identification.')
                self.sp = None

            if self.sp is not None:
                # do the tilt calibration
                self.sp.query('tilt')
                print(self.sp.read().strip())
                print(self.sp.read().strip())
                self.sp.read()

                # set the force
                self.sp.query('force %i' % factor)

                # set the syringe volume, manufacturer. May need to do this manually, depending on syringe on hand. See manual.
                self.sp.query('syrm %s %s' % (s_manufacturer, s_volume))
                self.sp.query('syrm')
                print('Syringe type: %s' % self.sp.read().strip())

    def switch_use_syringe_pump(self,input):
        self.use_flag = input

    def updateFactor(self,input):
        # NOTE: Check the input AT the text boxes trigger. Then input it into here.
        self.factor = input

    def set_parameters(self, current_A, infuse_rate, infuse_interval):

        if self.sp is not None:
            # get pump ready for operation by clearing some counters
            self.sp.query('civolume')
            self.sp.query('ctvolume')
            self.sp.query('citime')
            self.sp.query('cttime')

            # this is the factor, in mL/(A hr), to find the replenisher.
            # its hard-coded in so that people don't mess it up on accident.

            factor_A_hr_mL = 0.085  # real value

            # get the limits of the machine for the chosen syringe
            self.sp.query('irate lim')
            limits = self.sp.read()
            limits = limits.split()

            # lim = [numerical value, volume unit, time unit]
            # official good units: uL/second
            low_lim = [float(limits[0])] + limits[1].split('/')
            high_lim = [float(limits[3])] + limits[4].split('/')

            # convert limits of pump with chosen syringe to ul/sec
            lims = []
            for lim in [low_lim, high_lim]:

                if lim[1] == 'ml':
                    factor_v = 10 ** 3
                elif lim[1] == 'ul':
                    factor_v = 1
                elif lim[1] == 'l':
                    factor_v = 10 ** 6
                elif lim[1] == 'nl':
                    factor_v = 10 ** -3
                elif lim[1] == 'pl':
                    factor_v = 10 ** -6
                else:
                    factor_v = 1
                    print('unknown volume units in limit')

                if lim[2] == 'hr':
                    factor_t = 3600
                elif lim[2] == 'min':
                    factor_t = 60
                elif lim[2] == 's':
                    factor_t = 1
                else:
                    factor_t = 1
                    print('unknown time units in limit')

                lims.append(lim[0] * factor_v / factor_t)

            # how much to infuse every {interval} hours. infuse_volume is in nL.
            # native units are mL, 10**3 converts to uL
            infuse_volume = current_A * infuse_interval * factor_A_hr_mL * 1.0 * 10 ** 3
            print('\nNeed replenisher volume (uL) per interval: %f' % infuse_volume)
            print('Infuse limits: [ %f, %f ] uL/sec' % (lims[0], lims[1]))
            print('Desired: infuse rate %f uL/s over %f seconds every %f hours.' % (
            infuse_rate, 1.0 * infuse_volume / infuse_rate, infuse_interval))

            if infuse_rate > lims[0] and infuse_rate < lims[1]:
                # print('Desired infuse rate OK')
                pass
            elif infuse_rate <= lims[0]:
                # print('Desired infuse rate too low. Setting infuse rate to lower limit.')
                infuse_rate = lims[0] * 1.01

            elif infuse_rate >= lims[1]:
                # print('Desired infuse rate too high. Setting infuse rate to upper limit.')
                infuse_rate = lims[1] * 0.99

            infuse_time = 1.0 * infuse_volume / infuse_rate
            print('Set:     infuse rate %f uL/s over %f seconds every %f hours.' % (
            infuse_rate, infuse_time, infuse_interval))

            # set the parameters
            self.sp.query('irate %f ul/s' % infuse_rate)
            self.sp.query('tvolume %f ul' % infuse_volume)
        else:

            if self.use_flag is True:
                print('Cannot set parameters; syringe pump was not initialized correctly.')

    def check_rate_volume(self):

        if self.sp is not None:
            continue_flag = True

            while continue_flag is True:

                time.sleep(1)

                # parse out the status promp
                self.sp.query('status')
                status = self.sp.read().strip().split()

                # parsing the integer part
                curr_rate = float(status[0]) * 1.0 * 10 ** -9  # converting from fL/s to uL/s
                t = int(status[1]) / 1000.0
                already_infused_volume = float(status[2]) * 1.0 * 10 ** -9

                # parsing the flag part
                flag = status[3]
                if flag[5] == 'T':
                    print('Pump done. Total infused volume: %.2f uL' % already_infused_volume)
                    break
                else:
                    print('Elapsed time (s): %.2f. Infused volume (uL): %.2f. Rate (uL/s): %.2f.' % (
                    t, already_infused_volume, curr_rate))

                if flag[2] == 'S':
                    print('Motor has stalled.')
                    self.motorStalled = True
                    break

                # get rid of all the built-up reads from the buffer, if any
                try:
                    while True:
                        self.sp.read()
                except:
                    pass
        else:
            if self.use_flag is True:
                print('Cannot check rate or volume; syringe pump was not correctly initialized.')
            already_infused_volume = 0
            curr_rate = 0

        return already_infused_volume, curr_rate

    def infuse(self):

        if self.sp is not None:
            # this gets rid of the pesky "T*" status commands that randomly pop up and screw everything up.
            self.sp.query('poll on')

            # runs the pump
            self.sp.query('run')
        else:
            if self.use_flag is True:
                print('Cannot run syringe pump; syringe pump was not initialized properly.')

    def set_rate_volume_directly(self, rate_i, volume_i):

        if self.sp is not None:
            self.sp.query('irate %f ul/sec' % rate_i)
            time.sleep(0.1)
            self.sp.query('tvolume %f ul' % volume_i)
            time.sleep(0.1)
        else:
            if self.use_flag is True:
                print('Cannot run syringe pump; syringe pump was not initialized properly.')

    def clearbuffer(self):

        if self.sp is not None:
            try:
                while True:
                    self.sp.read()
            except:
                pass

    def disconnect(self):
        if self.sp is not None:
            self.sp.close()
            print('Syringe pump has been disconnected.')
        else:

            if self.use_flag is True:
                print('Syringe pump was not initialized properly, but hopefully is disconnected anyway.')

# def ps_monitorSingle(ps,Notify,
#                      V_set,I_set,
#                      ps_checking_interval,infuseInterval,infuseRate,notifyIntervalMin,sp):
#     ps.run(V_set,I_set)
#     plt.show()
#     time.sleep(0.2)
#
#     ## Setup reference times
#     startTime = time.time()
#
#     infuseTimerReference = time.time()
#
#     lastReadTime = startTime
#     lastPlotTime = startTime
#     lastNotifyTime = startTime
#
#     ## Setup arrays to plot our power supply data to
#     tPlot = []
#     vPlot = []
#     iPlot = []
#
#     totalI = 0 #What this do?
#
#     stopFlag = False #Not sure how to use this yet but will probably be useful
#                     # Still not sure how I'm gonna use this
#
#
#     level1FailLast20 = 0
#     level1Threshold = 50
#
#     pauseFlag = 0
#     # Start new def here for the loops
#     def runloop():
#         while not stopFlag:
#
#             if pauseFlag:
#                 time.sleep(0.01)
#                 continue
#
#
#             # Get our new times
#             oldTime = newTime
#             newTime = time.time()
#             totalTime = newTime - startTime
#
#             # Check if it is time to send a notification
#             tempTimeDelta = newTime - lastNotifyTime
#             if tempTimeDelta.total_seconds()/60 >= notifyIntervalMin:
#                 # Check the number of level 1 errors in the last 20 minutes
#                 if level1FailLast20 > level1Threshold:
#                     #Send a message
#                     msg = "We have X number of level 1 errors"
#                     Notify.notify()
#                     print("Bad notification")
#                 else:
#                     # Send notification that everything is fine
#                     print("Good notificiation")
#
#                 level1FailLast20 = 0
#
#             #Attempt to read the power supply
#             try: vNew, iNew = ps.read_V_I()
#             except:
#                 failLast20Min = failLast20Min + 1
#                 print("Failed to get measurment - sleeping and skipping to next iteration hoping that the problem was not fatal")
#
#                 if not stopFlag:
#                     time.sleep(ps_checking_interval)
#                 continue
#
#             #Print the stuff to a file. Do later
#
#             # CHECK INFUSE TIMER CONDITION
#             if(newTime - infuseTimerReference)/3600.0 > infuseInterval:
#                 totalT = newTime - infuseTimerReference
#
#             # take the total I and divide it by the total time to get the average current over the time period
#                 try:
#                     I_avg = (total_I) / totalT
#                 except:
#                     I_avg = 0
#
#                 # reset the reference timer and total_I
#                 infuseTimerReference = newTime
#                 total_I = 0
#
#                 # set the infuse parameters and run the pump
#                 sp.set_parameters(I_avg, infuseRate, infuseInterval)
#                 time.sleep(0.1)
#                 sp.infuse()
#
#                 # # monitor the infusion
#                 # infused_volume, infuse_rate = sp.check_rate_volume(MOTOR_HAS_STALLED)
#                 # curr_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#                 # new_infusion = '%s : infused %.3f uL replenisher after %.2f hours at %.3f uL/s with %.3f A average current.' % (
#                 # curr_time, infused_volume, infuse_interval, infuse_rate, I_avg)
#                 #
#                 # if sp.use_flag is True:
#                 #     infusion_list.append(new_infusion)
#                 #     infused_amt_q.put(infused_volume)
#                 #     print("# infusions: ", infused_amt_q.qsize())
#
#             else:
#                 totalI = totalI + iNew * (newTime - oldTime)
#
#             figure = plt.figure()
#             p1 = figure.add_subplot(111)
#
#             line1, = plt.plot(tPlot, vPlot, '-')
#             line2, = plt.plot(tPlot, iPlot, '-')
#
#             def updatePlot():
#                 # Plot new voltage and current readings here in real time
#
#                 tPlot.append(totalTime)
#                 vPlot.append(vNew)
#                 iPlot.append(iNew)
#
#                 line1.set_data(tPlot, vPlot)
#                 line2.set_data(tPlot, iPlot)
#                 figure.gca().relim()
#                 figure.gca().autoscale_view()
#
#                 # Copy paste code to make some labels and see if it works
#                 try:
#                     # total elapsed time in hh:mm:ss
#                     hr, rem = divmod(tPlot[-1] - tPlot[0], 3600)
#
#                     mins, sec = divmod(rem, 60)
#                     time_axis_title = "Time (s): Elapsed time is {:0>2} hours, {:0>2} minutes, {:d} seconds".format(int(hr),int(mins),int(sec))
#                 except:
#                     time_axis_title = "Time (s)"
#
#                 plt.xlabel(time_axis_title)
#
#                 return line1,line2
#
#             animation = FuncAnimation(figure, updatePlot, interval=1000)
#             plt.show()
#
#             time.sleep(ps_checking_interval)
#
#
#
#         # Add code to delete time, voltage, and current matricies that are being plotted.
#         # Possibly also delete current plots in order to delete any current data
#         # Essentially if things are acting weird, just delete everything and start from scratch
#     return

def testEmail(Notify):
    # Get a screenshot the the system?
    fn = os.getcwd() + '/screenshot.png'
    os.system('scrot %s -q 75' % fn)

    pathToScreenshot = "C:\\Users\\Thomas Sison\\Pictures"
    nameScreenshot = "screenshot.png"
    img1 = dict(title='desktop screenshot', path=os.path.join(pathToScreenshot, nameScreenshot))

    print("Writing out test inputs for debugging purposes")
    print(Notify.pathToCredentials)
    print(Notify.dirToPickle)


    service = Notify.get_service(Notify.pathToCredentials, Notify.dirToPickle)
    message = Notify.create_message(Notify.fromEmail, Notify.toEmail, "Test subject", "If this email was received, the Notify class's email protocol is working", img1)
    Notify.send_message(service, Notify.fromEmail, message)

    return

def menu():
    ###############################################################################
    ############################ LIST OF DEFAULT VALUES ###########################

    #### Super hardcoded values. Won't need to change 99% of the time

    # For NotifyC Class

    #################################
    ## PUT OAUTH STUFF BACK IN HERE

    SID = "ACb4dd1978c3860effcff4d26ffaad4b99"
    AUTH = "a5f4f656cbfd9de498f2df038d8579d9"
    TO_NUM = '+18017267329'
    FROM_NUM = '+15012733970'

    error_notify_cnt_MAX = 100
    notifyType = 2
    use_text_only_for_bad_news = True

    # For Syringe Pump class
    s_manufacturer = 'bdp'
    s_volume = '3 ml'

    #### create parameter defaults for VI  ####
    volt_def = [6, 0.02, 18]  # Volts [Target, Low Warning, High Warning]
    cur_def = 0.35  # amps

    #### Oxygen and Pump Defaults ####
    syringe_on = False
    # Infuse rate in uL/s
    infuse_rate_def = 2
    # Interval time between infusions in hours
    infuse_interval_def = 1.5
    # Number of times to check
    num_times_to_check_def = 3
    # Syringe Factor
    factor_def = 50
    # Syringe Current in amps
    syringe_current_def = 0.5
    # Syringe on time in s.
    syringe_on_time_def = 1

    # then initialize the syringe pump
    #sp_port = 'ASRL4::INSTR'
    # sp_port='ASRL/dev/ttyACM0::INSTR'
    # pvisa port identifier for the syringe pump
    sp_port='ASRL/dev/ttyACM0::INSTR'

    oxygen_on = False
    # Oxygen Calibration value in something
    oxygen_calibration_def = 1

    oxygen_reads_def = 10

    ## Solenoid defaults
    solenoid_low_bound_def = 1
    solenoid_high_bound_def = 2

    #### SMS defaults ####
    # how often to check voltage and current, in seconds
    check_interval_def = 5
    # how often to notify (if still good) in minutes
    notify_interval_def = 20.0
    # how often to notify if bad in minutes
    error_notify_interval_def = 1

    ###############################################################################
    ###############################################################################

    ## tkinter spacing defaults
    labelPadXDef = 5
    labelFramePadDef = [10, 10]
    buttonDef = [10, 10, 14, 1]  # padx,pady,width,height
    gridPadDef = [10, 10]

    #### Initialize NotifyC class with default parameters ####

    NotifyObject = NotifyCSingle(SID,AUTH,TO_NUM,FROM_NUM,[0.02,18],cur_def,error_notify_interval_def,
                                 error_notify_cnt_MAX,notify_interval_def,notifyType,use_text_only_for_bad_news)

    #### Initialize Syringe Pump class with default parameters ####
    ## We initially keep the syringe disabled by default
    SyringeObject = Legato100_SP(sp_port,s_manufacturer,s_volume,factor_def,False)

    SolenoidObject = Solenoid_Controller()

    OxySensorObject = O2_Sensor(oxygen_reads_def)

    root = tk.Tk()
    root.title("Main Settings")
    root.geometry('+%d+%d' % (0, 0))

    voltage_frame = tk.LabelFrame(root, text="Voltage", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    voltage_frame.pack()

    plateOptionVar = tk.StringVar(voltage_frame)

    plateOption = tk.OptionMenu(voltage_frame,plateOptionVar,"Copper","Nickel")
    plateOption.grid(row=0,column=0,columnspan=3)

    # create string variables to store Voltage text box contents
    vTarget = tk.StringVar(voltage_frame, str(volt_def[0]))
    vLowWarn = tk.StringVar(voltage_frame, str(volt_def[1]))
    vHighWarn = tk.StringVar(voltage_frame, str(volt_def[2]))

    # Target voltage
    vTargetText = tk.StringVar()
    vTargetText.set("Target \nVoltage (V)")
    vTargetBoxLabel = tk.Label(voltage_frame, textvariable=vTargetText, height=2, padx=labelPadXDef)
    vTargetBoxLabel.grid(row=1, column=0)
    vTargetBox = tk.Entry(voltage_frame, text="Target", textvariable=vTarget, width=8, justify="center")
    vTargetBoxTip = CreateToolTip(vTargetBox,\
                                  "Sets voltage for the power supply to aim to be around when running electroplating in volts")
    vTargetBox.grid(row=2, column=0)

    # Low voltage warning
    vLowText = tk.StringVar()
    vLowText.set("Low Voltage \nWarning (V)")
    vLowBoxLabel = tk.Label(voltage_frame, textvariable=vLowText, height=2, padx=labelPadXDef)
    vLowBoxLabel.grid(row=1, column=1)
    vLowBox = tk.Entry(voltage_frame, text="Low Warning", textvariable=vLowWarn, width=8, justify="center")
    vLowBoxTip = CreateToolTip(vLowBox,\
                               "Lowest voltage the power supply can be until the user must be notified that something is wrong in volts.")
    vLowBox.grid(row=2, column=1)

    # high voltage warning
    vHighText = tk.StringVar()
    vHighText.set("High Voltage \nWarning(V)")
    vHighBoxLabel = tk.Label(voltage_frame, textvariable=vHighText, height=2, padx=labelPadXDef)
    vHighBoxLabel.grid(row=1, column=2)
    vHighBox = tk.Entry(voltage_frame, text="High Warning", textvariable=vHighWarn, width=8, justify="center")
    vHighBoxTip = CreateToolTip(vHighBox,\
                                "Highest voltage the power supply can output until the user must be notified that something is wrong in volts.")
    vHighBox.grid(row=2, column=2)

    # Create String variable for target current
    current_frame = tk.LabelFrame(root, text="Current", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    current_frame.pack()

    iTargetText = tk.StringVar(current_frame, str(cur_def))
    iText = tk.StringVar(value="Target \nCurrent (A)")

    iBoxLabel = tk.Label(current_frame, textvariable=iText, height=2, padx=labelPadXDef, pady=2)
    iBoxLabel.grid(row=0, column=0)
    iBox = tk.Entry(current_frame, text="Target Current", textvariable=iTargetText, width=8, justify="center")
    iBoxTip = CreateToolTip(iBox,\
                            "Target current we want the power supply to output. Usually more important than the voltage. In Amps.")
    iBox.grid(row=1, column=0, padx=gridPadDef[0], pady=2)

    iArea1LabelText = tk.StringVar(value="Area 1\n(m^2)")
    iArea1Label = tk.Label(current_frame, textvariable=iArea1LabelText)
    iArea1Label.grid(row=0, column=1)

    iArea1Text = tk.StringVar(current_frame, str(1))
    iArea1 = tk.Entry(current_frame, text="Area 1", textvariable=iArea1Text, width=8, justify="center")
    iArea1Tip = CreateToolTip(iArea1,\
                              "Area of one side of the electroplating in m^2")
    iArea1.grid(row=1, column=1, padx=gridPadDef[0], pady=2)

    iDensity1 = tk.StringVar(current_frame, "Area 1\nCurrent Density\n(A/m^2):\n")
    iDensity1Label = tk.Label(current_frame, textvariable=iDensity1, height=4, padx=labelPadXDef, pady=2)
    iDensity1Label.grid(row=2, column=1, pady=2)

    def calcDensity1(event):
        try:
            float(iArea1.get())
        except:
            iArea1.delete(0, "end")
            iArea1.insert(0, str(1))
            return
        result = float(iBox.get()) / float(iArea1.get())
        result = "{:.3f}".format(result)
        iDensity1.set("Area 1\nCurrent Density\n(A/m^2):\n" + result)

    iBox.bind('<FocusOut>', calcDensity1, add="+")
    iBox.bind('<Return>', calcDensity1, add="+")
    iArea1.bind('<FocusOut>', calcDensity1, add="+")
    iArea1.bind('<Return>', calcDensity1, add="+")

    iArea2LabelText = tk.StringVar(value="Area 2\n(m^2)")
    iArea2Label = tk.Label(current_frame, textvariable=iArea2LabelText)
    iArea2Tip = CreateToolTip(iArea1,\
                              "Area of the other side of the electroplating in m^2")
    iArea2Label.grid(row=0, column=2)

    iArea2Text = tk.StringVar(current_frame, str(1))
    iArea2 = tk.Entry(current_frame, text="Area 2", textvariable=iArea2Text, width=8, justify="center")
    iArea2.grid(row=1, column=2, padx=gridPadDef[0], pady=2)

    iDensity2 = tk.StringVar(current_frame, "Area 2\nCurrent Density\n(A/m^2):\n")
    iDensity2Label = tk.Label(current_frame, textvariable=iDensity2, height=4)
    iDensity2Label.grid(row=2, column=2, pady=2)

    def calcDensity2(event):
        try:
            float(iArea2.get())
        except:
            iArea2.delete(0, "end")
            iArea2.insert(0, str(1))
            return
        if (float(iArea2.get()) <= 0):
            iArea2.delete(0, "end")
            iArea2.insert(0, str(1))
            return
        result = float(iBox.get()) / float(iArea2.get())
        result = "{:.3f}".format(result)
        iDensity2.set("Area 2\nCurrent Density\n(A/m^2):\n" + result)

    iBox.bind('<FocusOut>', calcDensity2, add="+")
    iBox.bind('<Return>', calcDensity2, add="+")
    iArea2.bind('<FocusOut>', calcDensity2, add="+")
    iArea2.bind('<Return>', calcDensity2, add="+")

    ############################

    #### Make main buttons ####
    IVButtonFrame = tk.LabelFrame(root, text="Main Controls", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    IVButtonFrame.pack()

    testButton = tk.Button(IVButtonFrame, bd=1, text="Test IV \nSettings", padx=buttonDef[0], pady=buttonDef[1],
                           width=buttonDef[2], height=buttonDef[3])
    testButtonTip = CreateToolTip(testButton,\
                              "Runs a 5 second test and reads the power supply current and voltage. Used to ensure nothing's wrong with the power supply.")
    testButton.config(command=lambda: testVI())
    testButton.grid(row=0, column=0, padx=gridPadDef[0], pady=gridPadDef[1])

    runButton = tk.Button(IVButtonFrame, bd=1, text="Run Electroplating", padx=buttonDef[0], pady=buttonDef[1],
                          width=buttonDef[2], height=buttonDef[3])
    runButton.grid(row=1, column=0, padx=gridPadDef[0], pady=gridPadDef[1])

    stopButton = tk.Button(IVButtonFrame, bd=1, text="Stop", padx=buttonDef[0], pady=buttonDef[1],
                           width=buttonDef[2], height=buttonDef[3])
    stopButton['state'] = tk.DISABLED

    stopButton.grid(row=1, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    pauseButton = tk.Button(IVButtonFrame, bd=1, text="Pause", padx=buttonDef[0], pady=buttonDef[1],
                           width=buttonDef[2], height=buttonDef[3])
    pauseButton['state'] = tk.DISABLED

    pauseButton.grid(row=0, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    # infuseButton = tk.Button(IVButtonFrame,bd=1,text="Run Infusion",padx=buttonDef[0], pady=buttonDef[1],
    #                       width=buttonDef[2], height=buttonDef[3])
    #
    # infuseButton.grid(row=2,column=0,columnspan=2)

    ###########################

    #### Make main output Console ####
    outputFrame = tk.LabelFrame(root, text="Output Window", padx=labelFramePadDef[0] - 2, pady=labelFramePadDef[1] - 2)
    outputFrame.pack()

    output = scrolledtext.ScrolledText(outputFrame, width=60, height=20, font=("Tekton Pro", 9))
    output.config(state="disabled")
    output.grid(row=0, column=0, padx=0, pady=2)
    ##################################

    #### Oxygen and Syringe Pump Window ####
    oxyPumpParams = tk.Toplevel()
    oxyPumpParams.title("Oxygen and Syringe Pump Settings")
    oxyPumpParams.geometry('+%d+%d'%(500,0))

    #### Oxygen Stuff ####
    oxyFrame = tk.LabelFrame(oxyPumpParams, text="Oxygen Sensor", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    oxyFrame.pack()

    oxyOn = tk.IntVar(0)
    oxySwitch = tk.Checkbutton(oxyFrame, text="Enable?", variable=oxyOn)
    oxySwitch.grid(row=0, column=0)

    oxySensorReadLabel = tk.Label(oxyFrame, text="Oxygen Sensor\nRead", height=2)
    oxySensorReadLabel.grid(row=0, column=2, padx=gridPadDef[0])

    oxySensorReadBox = tk.Entry(oxyFrame,width = 7)
    oxySensorReadBox.grid(row=1,column=2,padx=gridPadDef[0])
    oxySensorReadBox['state'] = tk.DISABLED

    # oxySliderLabel = tk.Label(oxyFrame, text="Some Oxygen\nParameter", height=2)
    # oxySliderLabel.grid(row=1, column=0)
    # oxySlider = tk.Scale(oxyFrame, from_=0, to=100, orient="horizontal", resolution=1, length=200)
    # oxySlider.grid(row=1, column=1)
    #
    # oxySliderManual = tk.Entry(oxyFrame, width=7)
    # oxySliderManual.grid(row=1, column=2, padx=gridPadDef[0])

    oxyNumReads = tk.StringVar()

    oxyNumReadsText = tk.StringVar()
    oxyNumReadsText.set("Number of Reads for Calibration")
    oxyNumReadsLabel = tk.Label(oxyFrame, textvariable=oxyNumReadsText, height=2, padx=labelPadXDef)
    oxyNumReadsLabel.grid(row=2, column=0)
    oxyNumReadsBox = tk.Entry(oxyFrame, text="Low Warning", textvariable=oxyNumReads, width=8, justify="center")
    oxyNumReadsTip = CreateToolTip(oxyNumReadsBox, \
                               "Lowest oxygen until solenoid disabling sequence is automatically started.")
    oxyNumReadsBox.grid(row=3, column=0)

    #### Syringe Pump Stuff ####
    pumpFrame = tk.LabelFrame(oxyPumpParams, text="Syringe Pump", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    pumpFrame.pack()

    pumpOn = tk.IntVar(0)
    pumpSwitch = tk.Checkbutton(pumpFrame, text="Enable?", variable=pumpOn, justify="left")
    pumpSwitch.grid(row=0, column=0,sticky="W")

    pumpEquillibrium = tk.IntVar(0)
    pumpEquillibriumSwitch = tk.Checkbutton(pumpFrame,text="Set bath to \nequillibrium on run",variable=pumpEquillibrium,justify="left")
    pumpEquillibriumSwitch.grid(row=1,column=0,sticky="W")

    pumpTestButton = tk.Button(pumpFrame, bd=2, text="Test Pump", pady=5,
                               width=buttonDef[2] - 5, height=buttonDef[3])
    pumpTestButton.config(command=lambda: testSyringePump())
    pumpTestButton.grid(row=0, column=1,rowspan=2)

    ## Make a bunch of Entry parameters

    infuseRate = tk.StringVar(pumpFrame, infuse_rate_def)
    infuseInterval = tk.StringVar(pumpFrame, infuse_interval_def)
    timeToCheck = tk.StringVar(pumpFrame, num_times_to_check_def)
    syringeForce = tk.StringVar(pumpFrame, factor_def)
    syringeCurrent = tk.StringVar(pumpFrame, syringe_current_def)
    syringeOnTime = tk.StringVar(pumpFrame, syringe_on_time_def)

    infuseRateLabel = tk.Label(pumpFrame, text="Syringe Infuse Rate")
    infuseRateLabel.grid(row=2, column=0, padx=gridPadDef[0])
    infuseRateEntry = tk.Entry(pumpFrame, textvariable=infuseRate, width=8, justify="center")
    infuseRateEntry.grid(row=3, column=0, padx=gridPadDef[0], pady=gridPadDef[1] - 2)

    infuseIntervalLabel = tk.Label(pumpFrame, text="Syringe Infuse Interval")
    infuseIntervalLabel.grid(row=4, column=0, padx=gridPadDef[0])
    infuseIntervalEntry = tk.Entry(pumpFrame, textvariable=infuseInterval, width=8, justify="center")
    infuseIntervalEntry.grid(row=5, column=0, padx=gridPadDef[0], pady=gridPadDef[1] - 4)

    # Renamed to replenishUpdateInterval in the monitorApp. Too lazy to change everything
    timesToCheckLabel = tk.Label(pumpFrame, text="Number of Infusiions")
    timesToCheckLabel.grid(row=6, column=0, padx=gridPadDef[0])
    timesToCheckEntry = tk.Entry(pumpFrame, textvariable=timeToCheck, width=8, justify="center")
    timesToCheckEntry.grid(row=7, column=0, padx=gridPadDef[0], pady=gridPadDef[1] - 4)
    timesToCheckTooltip = CreateToolTip(timesToCheckEntry,\
                                          "The number of times we check the syringe infusion after it is done")

    syringeFactorLabel = tk.Label(pumpFrame, text="Syringe Factor")
    syringeFactorLabel.grid(row=2, column=1, padx=gridPadDef[0])
    syringeFactorEntry = tk.Entry(pumpFrame, textvariable=syringeForce, width=8, justify="center")
    syringeFactorEntry.grid(row=3, column=1, padx=gridPadDef[0], pady=gridPadDef[1] - 4)

    def checkFactor(event):
        try:
            test = float(syringeFactorEntry.get())
            print(test)
        except:
            syringeFactorEntry.delete(0, "end")
            syringeFactorEntry.insert(0, str(factor_def))
        if (float(syringeFactorEntry.get()) <= 0):
            syringeFactorEntry.delete(0, "end")
            syringeFactorEntry.insert(0, str(factor_def))
            return
        return

    syringeFactorEntry.bind('<FocusOut>', checkFactor, add="+")
    syringeFactorEntry.bind('<Return>', checkFactor, add="+")

    syringeCurrentLabel = tk.Label(pumpFrame, text="Syringe Current")
    syringeCurrentLabel.grid(row=4, column=1, padx=gridPadDef[0])
    syringeCurrentEntry = tk.Entry(pumpFrame, textvariable=syringeCurrent, width=8, justify="center")
    syringeCurrentEntry.grid(row=5, column=1, padx=gridPadDef[0], pady=gridPadDef[1] - 4)

    syringeOnTimeLabel = tk.Label(pumpFrame, text="Syringe On Time (s.)")
    syringeOnTimeLabel.grid(row=6, column=1, padx=gridPadDef[0])
    syringeOnTimeEntry = tk.Entry(pumpFrame, textvariable=syringeOnTime, width=8, justify="center")
    syringeOnTimeEntry.grid(row=7, column=1, padx=gridPadDef[0], pady=gridPadDef[1] - 4)

    syringeFactorEntry['state'] = tk.DISABLED
    syringeCurrentEntry['state'] = tk.DISABLED
    syringeOnTimeEntry['state'] = tk.DISABLED

    #### Solenoid Options ####

    vTarget = tk.StringVar(voltage_frame, str(volt_def[0]))
    vLowWarn = tk.StringVar(voltage_frame, str(volt_def[1]))
    vHighWarn = tk.StringVar(voltage_frame, str(volt_def[2]))

    solenoidFrame = tk.LabelFrame(oxyPumpParams,text = "Solenoid")
    solenoidFrame.pack()

    solenoidLowBound = tk.StringVar(solenoidFrame,0.5)
    solenoidHighBound = tk.StringVar(solenoidFrame,2)

    solenoidOn = tk.IntVar(0)
    solenoidSwitch = tk.Checkbutton(solenoidFrame, text="Use Solenoid (Only if Permalloy)", variable=solenoidOn, justify="left")
    solenoidSwitch.grid(row=0,column=0)

    # Solenoid Low O2 Percentage
    solenoidLowText = tk.StringVar()
    solenoidLowText.set("Low Voltage \nWarning (V)")
    solenoidLowLabel = tk.Label(solenoidFrame, textvariable=solenoidLowText, height=2, padx=labelPadXDef)
    solenoidLowLabel.grid(row=1, column=0)
    solenoidLowBox = tk.Entry(solenoidFrame, text="Low Warning", textvariable=solenoidLowBound, width=8, justify="center")
    solenoidLowBoxTip = CreateToolTip(solenoidLowBox, \
                               "Lowest oxygen until solenoid disabling sequence is automatically started.")
    solenoidLowBox.grid(row=2, column=0)

    # Solenoid Low O2 Percentage
    solenoidHighText = tk.StringVar()
    solenoidHighText.set("Low Voltage \nWarning (V)")
    solenoidHighLabel = tk.Label(solenoidFrame, textvariable=solenoidHighText, height=2, padx=labelPadXDef)
    solenoidHighLabel.grid(row=1, column=1)
    solenoidHighBox= tk.Entry(solenoidFrame, text="Low Warning", textvariable=solenoidHighBound, width=8, justify="center")
    solenoidHighBoxTip = CreateToolTip(solenoidHighBox, \
                               "Lowest voltage the power supply can be until the user must be notified that something is wrong in volts.")
    solenoidHighBox.grid(row=2, column=1)

    solenoidOpenButton = tk.Button(solenoidFrame, bd=1, text="Open Solenoid", padx=buttonDef[0], pady=buttonDef[1],
                          width=buttonDef[2], height=buttonDef[3])
    solenoidOpenButton.grid(row=3, column=0, padx=gridPadDef[0], pady=gridPadDef[1])

    solenoidCloseButton = tk.Button(solenoidFrame, bd=1, text="Close Solenoid", padx=buttonDef[0], pady=buttonDef[1],
                          width=buttonDef[2], height=buttonDef[3])
    solenoidCloseButton.grid(row=3, column=1, padx=gridPadDef[0], pady=gridPadDef[1])


    #### SMS Options ####
    SMSParamsWindows = tk.Toplevel()
    SMSParamsWindows.title("Timings")
    SMSParamsWindows.geometry('+%d+%d'%(500,450))

    SMSFrame = tk.LabelFrame(SMSParamsWindows, text="Options", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    SMSFrame.pack()

    checkInterval = tk.StringVar(SMSFrame, check_interval_def)
    notifyTimer = tk.StringVar(SMSFrame, notify_interval_def)
    errorNotify = tk.StringVar(SMSFrame, error_notify_interval_def)

    checkIntervalLabel = tk.Label(SMSFrame, text="Power Supply\n Checking Interval (s.)")
    checkIntervalLabel.grid(row=0, column=0, padx=gridPadDef[0])
    checkIntervalEntry = tk.Entry(SMSFrame, width=8, textvariable=checkInterval, justify="center")
    checkIntervalEntryTip = CreateToolTip(checkIntervalEntry,\
                                          "Sets amount of time between each check of voltage and current, in seconds")
    checkIntervalEntry.grid(row=0, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    notifyTimerLabel = tk.Label(SMSFrame, text="Ok Notification Interval (min.)")
    notifyTimerLabel.grid(row=1, column=0, padx=gridPadDef[0])
    notifyTimerEntry = tk.Entry(SMSFrame, width=8, textvariable=notifyTimer, justify="center")
    notifyTimerEntryTip = CreateToolTip(notifyTimerEntry,\
                                        "Sets how often to send a notification if the system is running ok in minutes")
    notifyTimerEntry.grid(row=1, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    errorNotifyLabel = tk.Label(SMSFrame, text="Error Notification Interval (min.)")
    errorNotifyLabel.grid(row=2, column=0, padx=gridPadDef[0])
    errorNotifyEntry = tk.Entry(SMSFrame, width=8, textvariable=errorNotify, justify="center")
    errorNotifyEntryTip = CreateToolTip(errorNotifyEntry,\
                                        "Sets how often to notify if the system has reached an error in minutes")
    errorNotifyEntry.grid(row=2, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    emailTestButton = tk.Button(SMSFrame, bd=2, text="Test Email Protocol", pady=5,
                               width=buttonDef[2] +5, height=buttonDef[3])
    emailTestButton.config(command=lambda: testEmail(NotifyObject))
    emailTestButton.grid(row=3, column=0,columnspan=2)
    emailTestButtonTip = CreateToolTip(emailTestButton,\
                                        "Sends a test email to see if the email protocol actually works")

    # Check if bad number was put in
    def BadNumber(event):
        if float(iBox.get()) < 0:
            iBox.delete(0, "end")
            iBox.insert(0, cur_def)

    iBox.bind('<FocusOut>', BadNumber)

    root.withdraw()
    oxyPumpParams.withdraw()
    SMSParamsWindows.withdraw()

    psVar = tk.StringVar()
    ps_ident = 0  # NOTE: This may need to be moved up later on

    ps = []

    def initWindow(ps_ident):
        initWin = tk.Toplevel()
        initWin.title("Initialization Window")
        initFrame = tk.Frame(initWin)
        initFrame.pack()

        finishInit = tk.Button(initFrame, text="Initialize", command=lambda: initDoneSwitch(initWin, ps_ident, ps))
        finishInit.grid(row=10, column=0, pady=10, padx=10, columnspan=3)

        psOptionLabel = tk.Label(initFrame, textvariable=tk.StringVar(initFrame, "Choose a power supply"), height=2,
                                 padx=labelPadXDef)
        psOptionLabel.grid(row=0, columnspan=3)
        psOption = tk.OptionMenu(initFrame, psVar, "Agilent E3631A", "Agilent E3634A", "Keysight E36105B")
        psOption.config(width=20, height=2)
        psOption.grid(row=1, column=0, columnspan=3)

        return

    monitorAppObject = []
    print(monitorAppObject)

    def initDoneSwitch(breakThis, ps_ident, ps):
        if psVar.get() == "":
            print("Please select a power supply")
            return

        root.deiconify()
        oxyPumpParams.deiconify()
        SMSParamsWindows.deiconify()

        breakThis.withdraw()

        print(psVar.get())
        if psVar.get() == "Agilent E3631A":
            ps_ident = 1
            #ps_port = 'ASRL/dev/ttyUSB0::INSTR' #From the host
            ps_port = 'ASRL3::INSTR'  #THOMAS'S WINDOWS LAPTOP
            channel = 8 # Related to the device
            ps.append(E3631A_PS(channel, ps_port, ps_ident))
        elif psVar.get() == "Agilent E3634A":
            ps_ident = 2
            ps_port = 'ASRL/dev/ttyUSB0::INSTR'
            channel = 5
            ps.append(E3634A_PS(channel, ps_port, ps_ident))
        elif psVar.get() == "Keysight E36105B":
            ps_ident = 3
            ps_port = 'USB::10893::6146::MY59001199::INSTR'
            channel = None  # not needed for this power supply and usbtmc interface
            ps.append(E36105B_PS(channel, ps_port, ps_ident))
        print(ps_ident)
        # Make label for currently used power supply
        curPS = tk.Label(voltage_frame, text="Current Power supply: " + psVar.get(), height=2, padx=labelPadXDef)
        curPS.grid(row=4, column=0, columnspan=3)
        createMonitor(monitorAppObject)

    monitorAppFrame = tk.Frame()

    def createMonitor(monitorAppObject):
        try:
            monitorAppObject.append(
                monitorApp(monitorAppFrame, ps[0], NotifyObject, volt_def, cur_def, check_interval_def,
                           infuse_interval_def, infuse_rate_def, notify_interval_def, error_notify_interval_def, SyringeObject,SolenoidObject,OxySensorObject,
                           oxygen_reads_def,solenoid_low_bound_def,solenoid_high_bound_def))
            print("Somehow actually created the monitorApp object... huh")
        except:
            print("Could not create monitorApp class, shutting down")
            exit(2)

    initWindow(ps_ident)

    def testVI():
        ps[0].run(vTargetBox.get(),iBox.get())

        startTime = time.time()
        nowTime = startTime

        tPlot, aPlot, bPlot = [], [], []
        figure = plt.figure()
        line1, = plt.plot(tPlot, aPlot, '-')
        line2, = plt.plot(tPlot,bPlot, '-')

        while nowTime-startTime <= 10:
            nowTime = time.time()
            try: vNew,iNew = ps[0].read_V_I()
            except:
                print("Could not read the power supply for 10 seconds.")

            toPlotTime = nowTime - startTime

            tPlot.append(toPlotTime)
            aPlot.append(vNew)
            bPlot.append(iNew)

            try:
                # total elapsed time in hh:mm:ss
                hr, rem = divmod(tPlot[-1] - tPlot[0], 3600)

                mins, sec = divmod(rem, 60)
                time_axis_title = "Time (s): Elapsed time is {:0>2} hours, {:0>2} minutes, {:d} seconds".format(int(hr),
                                                                                                                int(
                                                                                                                    mins),
                                                                                                                int(
                                                                                                                    sec))
            except:
                time_axis_title = "Time (s)"

            line1.set_data(tPlot,aPlot)
            line2.set_data(tPlot,bPlot)
            figure.gca().relim()
            figure.gca().autoscale_view()

            plt.legend(['Voltage', 'Current'])
            plt.xlabel(time_axis_title)
            time.sleep(1)


    def startElectroplating():
        stopButton['state'] = tk.NORMAL
        pauseButton['state'] = tk.NORMAL

        runButton['state'] = tk.DISABLED
        vTargetBox['state'] = tk.DISABLED
        vHighBox['state'] = tk.DISABLED
        vLowBox['state'] = tk.DISABLED
        iBox['state'] = tk.DISABLED
        infuseRateEntry['state'] = tk.DISABLED
        infuseIntervalEntry['state'] = tk.DISABLED

        checkIntervalEntry['state'] = tk.DISABLED
        notifyTimerEntry['state'] = tk.DISABLED
        errorNotifyEntry['state'] = tk.DISABLED
        timesToCheckEntry['state'] = tk.DISABLED

        # If we have
        monitorAppObject.startMonitor()

    def stopElectroplating():
        stopButton['state'] = tk.DISABLED
        pauseButton['state'] = tk.DISABLED

        runButton['state'] = tk.NORMAL

        monitorAppObject.stopMonitor()

    def pauseElectroplating():
        if monitorAppObject.getPauseState() == 0:
            pauseButton.config(text = "Unpause")
            monitorAppObject.pauseMonitor()
            return
        if monitorAppObject.getPauseState() == 1:
            pauseButton.config(text = "Pause")
            monitorAppObject.pauseMonitor()
            return

    runButton.config(command=lambda: startElectroplating())
    stopButton.config(command=lambda: stopElectroplating())
    pauseButton.config(command=lambda: monitorAppObject[0].pauseMonitor())

    solenoidOpenButton.config(command=lambda: monitorAppObject[0].openSolenoid())
    solenoidCloseButton.config(command=lambda: monitorAppObject[0].closeSolenoid())

    def updateMonitorApp():
        monitorAppObject[0].setParams(vTargetBox.get(),
                                   iBox.get(),
                                   vHighBox.get(),
                                   vLowBox.get(),
                                   checkIntervalEntry.get(),
                                   infuseIntervalEntry.get(),
                                   infuseRateEntry.get(),
                                   timesToCheckEntry.get(),
                                   oxyNumReadsBox.get(),
                                   solenoidLowBox.get(),
                                   solenoidHighBox.get(),
                                   notifyTimerEntry.get(),
                                   errorNotifyEntry.get(),
                                   plateOptionVar.get(),
                                solenoidOn.get())
        print("Updated monitorApp")

    # vTargetBox.bind('<Key>', lambda event: updateMonitorApp(),add="+")
    # iBox.bind('<Key>', lambda event: updateMonitorApp(), add="+")
    # vHighBox.bind('<Key>', lambda event: updateMonitorApp(), add="+")
    # vLowBox.bind('<Key>', lambda event: updateMonitorApp(), add="+")
    # checkIntervalEntry.bind('<Key>', lambda event: updateMonitorApp(), add="+")
    # infuseIntervalEntry.bind('<Key>', lambda event: updateMonitorApp(), add="+")
    # infuseRateEntry.bind('<Key>', lambda event: updateMonitorApp(), add="+")
    # timesToCheckEntry.bind('<Key>', lambda event: updateMonitorApp(), add="+")
    # oxyNumReadsBox.bind('<Key>', lambda event: updateMonitorApp(), add="+")
    # solenoidLowBox.bind('<Key>', lambda event: updateMonitorApp(), add="+")
    # solenoidHighBox.bind('<Key>', lambda event: updateMonitorApp(), add="+")
    # notifyTimerEntry.bind('<Key>', lambda event: updateMonitorApp(), add="+")
    # errorNotifyEntry.bind('<Key>', lambda event: updateMonitorApp(), add="+")
    
    vTargetBox.bind('<FocusOut>', lambda event: updateMonitorApp(),add="+")
    iBox.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")
    vHighBox.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")
    vLowBox.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")
    checkIntervalEntry.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")
    infuseIntervalEntry.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")
    infuseRateEntry.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")
    timesToCheckEntry.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")
    oxyNumReadsBox.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")
    solenoidLowBox.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")
    solenoidHighBox.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")
    notifyTimerEntry.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")
    errorNotifyEntry.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")
    plateOption.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")
    solenoidSwitch.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")

    plateOption.bind('<Leave>', lambda event: updateMonitorApp(), add="+")
    solenoidSwitch.bind('<Leave>', lambda event: updateMonitorApp(), add="+")


    def printMonitorValues():
        monitorAppObject[0].printParams()

    printParamsButton = tk.Button(IVButtonFrame,bd=1,text="Print Parameters", padx=buttonDef[0], pady=buttonDef[1],
                           width=buttonDef[2], height=buttonDef[3])
    printParamsButton.grid(row=2,column = 1, padx=gridPadDef[0], pady=gridPadDef[1])
    printParamsButton.config(command=lambda: printMonitorValues())

    updateParamsButton = tk.Button(IVButtonFrame, bd=1, text="Update Parameters", padx=buttonDef[0], pady=buttonDef[1],
                                  width=buttonDef[2], height=buttonDef[3])
    updateParamsButton.grid(row=2, column=0, padx=gridPadDef[0], pady=gridPadDef[1])
    updateParamsButton.config(command=lambda: updateMonitorApp())
    updateParamsButtonTip = CreateToolTip(updateParamsButton,\
                                        "Forces an update to the monitorApp's parameters, in case some bindings did not work")

    root.mainloop()


if __name__ == '__main__':
    notify_flag = 2
    use_text_only_for_bad_news = True

    menu()


#Talk to outside things modules and adjusting Python Interpreter
from datetime import datetime
from twilio.rest import Client
import sys,os,time,pyvisa,email, smtplib, ssl
from matplotlib.animation import FuncAnimation
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import matplotlib.pyplot as plt

import base64
import logging
import mimetypes
import os
import os.path
import pickle
import uuid


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
        self.fromEmail =
        self.toEmail =
        self.pathToScreenshot =
        self.nameScreenshot =
        self.pathToCredentials =
        self.dirToPickle =

    # Create googleEmailAPI functions for message protocol. Won't need to be used outside of this class? (Hopefully)
    def get_service(pathToCredentials, dirToPickle):
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

    def send_message(service, sender, message):
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

    def create_message(sender, to_list, subject, message_text, img1):
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
    def notify(self, V_new, I_new, notify_list, msg, infused_amt_q):

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


        ## construct message based on V value
        # These bounds need to change somehow
        # Tests if the read voltage value is above or below our set boundaries or the target current is greater
        # than 10% away from the target
        if (V_new < self.V_bounds[0] or V_new > self.V_bounds[1] or I_new < (self.I_target-self.I_target*0.1) or
            I_new > (self.I_target+self.I_target*0.1)) and self.error_notify_count < self.error_notify_cnt_MAX:
            if (V_new < self.V_bounds[0]):
                typeD = 'Voltage reading below low boundary'
            if V_new > self.V_bounds[1]:
                typeD = 'Voltage reading above high boundary'

            # If this is our first error, get the current time to record all future errors with
            if self.error_notify_count == 0:
                self.error_notify_ref = time.time()

            # Start a notification error timer to prevent spam
            self.error_notify_timer = (time.time() - self.error_notify_ref) / 60.0

            # if it is time to send out message OR we haven't sent an error message yet
            if self.error_notify_timer > self.error_notify_interval or self.error_notify_count == 0:

                self.error_notify_count = self.error_notify_count + 1

                emailBody = '%s. ERROR-%s.%s Warn %d. V: %.3f V, I: %.3f A. Inf: %.3f uL.' % (
                    current_date_time, typeD, self.msg, self.error_notify_count,V_new, I_new, infused_vl)
                print(emailBody)

                if self.notifyType in [1, 3]:
                    try:
                        self.notify_textmessage(emailBody)
                    except:
                        print(
                            'Could not *bad* notify via text message - continuing and hoping that the error was not fatal.')

                if self.notifyType in [2, 3]:
                    try:
                        self.notify_email(emailBody)
                    except:
                        print('Could not *bad* notify via email - continuing and hoping that the error was not fatal.')

                # After we send a message, create
                self.error_notify_ref = time.time()

            self.msg = ''

        elif self.notify_interval < notify_time:
            emailBody = '%s. Good.%s V: %.3f V, I: %.3f .A Inf: %.3f uL.' % (
                current_date_time, self.msg, V_new, I_new,infused_vl)

            # Ignoring text message protocols for now
            # if self.notifyType in [1, 3] and self.use_text_only_for_bad_news is False:
            #     try:
            #         self.notify_textmessage(message)
            #     except:
            #         print(
            #             'Could not *good* notify via text message - continuing and hoping that the error was not fatal.')

            if self.notifyType in [2, 3]:
                try:
                    self.notify_email(emailBody)
                except:
                    print('Could not *good* notify via email - continuing and hoping that the error was not fatal.')

            # reset error count, just in case of a temporary disconnect
            self.error_notify_count = 0
            self.error_notify_ref = time.time()
            self.error_notify_timer = 0

            # always print to terminal
            print(emailBody)
            self.msg = ''

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

class Legato100_SP():
    def __init__(self, sp_port, s_manufacturer, s_volume, force, use_syringe_pump):

        self.use_flag = use_syringe_pump

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
                self.sp.query('force %i' % force)

                # set the syringe volume, manufacturer. May need to do this manually, depending on syringe on hand. See manual.
                self.sp.query('syrm %s %s' % (s_manufacturer, s_volume))
                self.sp.query('syrm')
                print('Syringe type: %s' % self.sp.read().strip())

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

    def check_rate_volume(self, MOTOR_HAS_STALLED):

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
                    MOTOR_HAS_STALLED.set()
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

def ps_monitorSingle(ps,Notify,
                     V_set,I_set,
                     ps_checking_interval,infuseInterval,infuseRate,notifyIntervalMin,sp):
    """
    List of things I need to make this thingy work:
        The power supply, syringe pump (eventually), and the NotifyC class
        I guess the infusion type?
        Power supply checking interval

    Error types:
        Level 1:
            The power supply is reading values outside of the bounds. May or may not be fatal
        Level 2:
            Stuff that will probably be super expensive if it breaks this bad
            so notify the user as soon as possible and skip all notification timers
            Such as the power supply isn't actually even reading anything or whatnot
            or we are veryyyyyy far out our bounds
    """
    ps.run(V_set,I_set)
    plt.show()
    time.sleep(0.2)

    ## Setup reference times
    startTime = time.time()

    infuseTimerReference = time.time()

    lastReadTime = startTime
    lastPlotTime = startTime
    lastNotifyTime = startTime

    ## Setup arrays to plot our power supply data to
    tPlot = []
    vPlot = []
    iPlot = []

    totalI = 0 #What this do?

    stopFlag = False #Not sure how to use this yet but will probably be useful
                    # Still not sure how I'm gonna use this


    level1FailLast20 = 0
    level1Threshold = 50

    while not stopFlag:
        # Get our new times
        oldTime = newTime
        newTime = time.time()
        totalTime = newTime - startTime

        # Check if it is time to send a notification
        tempTimeDelta = newTime - lastNotifyTime
        if tempTimeDelta.total_seconds()/60 >= notifyIntervalMin:
            # Check the number of level 1 errors in the last 20 minutes
            if level1FailLast20 > level1Threshold:
                #Send a message
                msg = "We have X number of level 1 errors"
                Notify.notify()
                print("Bad notification")
            else:
                # Send notification that everything is fine
                print("Good notificiation")

            level1FailLast20 = 0

        #Attempt to read the power supply
        try: vNew, iNew = ps.read_V_I()
        except:
            failLast20Min = failLast20Min + 1
            print("Failed to get measurment - sleeping and skipping to next iteration hoping that the problem was not fatal")

            if not stopFlag:
                time.sleep(ps_checking_interval)
            continue

        #Print the stuff to a file. Do later

        # CHECK INFUSE TIMER CONDITION
        if(newTime - infuseTimerReference)/3600.0 > infuseInterval:
            totalT = newTime - infuseTimerReference

        # take the total I and divide it by the total time to get the average current over the time period
            try:
                I_avg = (total_I) / totalT
            except:
                I_avg = 0

            # reset the reference timer and total_I
            infuseTimerReference = newTime
            total_I = 0

            # set the infuse parameters and run the pump
            sp.set_parameters(I_avg, infuseRate, infuseInterval)
            time.sleep(0.1)
            sp.infuse()

            # # monitor the infusion
            # infused_volume, infuse_rate = sp.check_rate_volume(MOTOR_HAS_STALLED)
            # curr_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # new_infusion = '%s : infused %.3f uL replenisher after %.2f hours at %.3f uL/s with %.3f A average current.' % (
            # curr_time, infused_volume, infuse_interval, infuse_rate, I_avg)
            #
            # if sp.use_flag is True:
            #     infusion_list.append(new_infusion)
            #     infused_amt_q.put(infused_volume)
            #     print("# infusions: ", infused_amt_q.qsize())

        else:
            totalI = totalI + iNew * (newTime - oldTime)

        figure = plt.figure()
        p1 = figure.add_subplot(111)

        line1, = plt.plot(tPlot, vPlot, '-')
        line2, = plt.plot(tPlot, iPlot, '-')

        def updatePlot():
            # Plot new voltage and current readings here in real time

            tPlot.append(totalTime)
            vPlot.append(vNew)
            iPlot.append(iNew)

            line1.set_data(tPlot, vPlot)
            line2.set_data(tPlot, iPlot)
            figure.gca().relim()
            figure.gca().autoscale_view()

            # Copy paste code to make some labels and see if it works
            try:
                # total elapsed time in hh:mm:ss
                hr, rem = divmod(tPlot[-1] - tPlot[0], 3600)

                mins, sec = divmod(rem, 60)
                time_axis_title = "Time (s): Elapsed time is {:0>2} hours, {:0>2} minutes, {:d} seconds".format(int(hr),int(mins),int(sec))
            except:
                time_axis_title = "Time (s)"

            plt.xlabel(time_axis_title)

            return line1,line2

        animation = FuncAnimation(figure, updatePlot, interval=1000)
        plt.show()


        time.sleep(ps_checking_interval)


        # Add code to delete time, voltage, and current matricies that are being plotted.
        # Possibly also delete current plots in order to delete any current data
        # Essentially if things are acting weird, just delete everything and start from scratch
    return

def testEmail(Notify):
    # Get a screenshot the the system?
    fn = os.getcwd() + '/screenshot.png'
    os.system('scrot %s -q 75' % fn)

    pathToScreenshot = fn
    nameScreenshot = "screenshot.png"
    img1 = dict(title='desktop screenshot', path=os.path.join(pathToScreenshot, nameScreenshot))


    service = Notify.get_service(Notify.pathToCredentials, Notify.dirToPickle)
    message = Notify.create_message(Notify.fromEmail, Notify.toEmail, "Test subject", "If this email was received, the Notify class's email protocol is working", img1)
    Notify.send_message(service, Notify.fromEmail, message)


    return

def menu():
    ###############################################################################
    ############################ LIST OF DEFAULT VALUES ###########################

    #### Super hardcoded values. Won't need to change 99% of the time

    # For NotifyC Class
    SID=
    AUTH=
    TO_NUM=
    FROM_NUM=
    my_email =
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

    oxygen_on = False
    # Oxygen Calibration value in something
    oxygen_calibration_def = 1

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


    #### Initialize NotifyC class with default parameters

    NotifyObject = NotifyCSingle(SID,AUTH,TO_NUM,FROM_NUM,[0.02,18],cur_def,error_notify_interval_def,
                                 error_notify_cnt_MAX,notify_interval_def,notifyType,use_text_only_for_bad_news)

    root = tk.Tk()
    root.title("Main Settings")
    root.geometry('+%d+%d' % (0, 0))

    voltage_frame = tk.LabelFrame(root, text="Voltage", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    voltage_frame.pack()

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
    stopButton.config(command=lambda: emergencyStop())
    stopButton.grid(row=1, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    infuseButton = tk.Button(IVButtonFrame,bd=1,text="Run Infusion",padx=buttonDef[0], pady=buttonDef[1],
                          width=buttonDef[2], height=buttonDef[3])
    infuseButton.config(command=lambda: runInfusion())
    infuseButton.grid(row=0,column=1)

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

    oxySliderLabel = tk.Label(oxyFrame, text="Some Oxygen\nParameter", height=2)
    oxySliderLabel.grid(row=1, column=0)
    oxySlider = tk.Scale(oxyFrame, from_=0, to=100, orient="horizontal", resolution=1, length=200)
    oxySlider.grid(row=1, column=1)

    oxySliderManual = tk.Entry(oxyFrame, width=7)
    oxySliderManual.grid(row=1, column=2, padx=gridPadDef[0])

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

    infuseRateLabel = tk.Label(pumpFrame, text="Infuse Rate")
    infuseRateLabel.grid(row=2, column=0, padx=gridPadDef[0])
    infuseRateEntry = tk.Entry(pumpFrame, textvariable=infuseRate, width=8, justify="center")
    infuseRateEntry.grid(row=3, column=0, padx=gridPadDef[0], pady=gridPadDef[1] - 2)

    infuseIntervalLabel = tk.Label(pumpFrame, text="Infuse Interval")
    infuseIntervalLabel.grid(row=4, column=0, padx=gridPadDef[0])
    infuseIntervalEntry = tk.Entry(pumpFrame, textvariable=infuseInterval, width=8, justify="center")
    infuseIntervalEntry.grid(row=5, column=0, padx=gridPadDef[0], pady=gridPadDef[1] - 4)

    timeToCheckLabel = tk.Label(pumpFrame, text="Times to Check")
    timeToCheckLabel.grid(row=6, column=0, padx=gridPadDef[0])
    timeToCheckEntry = tk.Entry(pumpFrame, textvariable=timeToCheck, width=8, justify="center")
    timeToCheckEntry.grid(row=7, column=0, padx=gridPadDef[0], pady=gridPadDef[1] - 4)

    syringeFactorLabel = tk.Label(pumpFrame, text="Syringe Factor")
    syringeFactorLabel.grid(row=2, column=1, padx=gridPadDef[0])
    syringeFactorEntry = tk.Entry(pumpFrame, textvariable=syringeForce, width=8, justify="center")
    syringeFactorEntry.grid(row=3, column=1, padx=gridPadDef[0], pady=gridPadDef[1] - 4)

    syringeCurrentLabel = tk.Label(pumpFrame, text="Syringe Current")
    syringeCurrentLabel.grid(row=4, column=1, padx=gridPadDef[0])
    syringeCurrentEntry = tk.Entry(pumpFrame, textvariable=syringeCurrent, width=8, justify="center")
    syringeCurrentEntry.grid(row=5, column=1, padx=gridPadDef[0], pady=gridPadDef[1] - 4)

    syringeOnTimeLabel = tk.Label(pumpFrame, text="Syringe On Time (s.)")
    syringeOnTimeLabel.grid(row=6, column=1, padx=gridPadDef[0])
    syringeOnTimeEntry = tk.Entry(pumpFrame, textvariable=syringeOnTime, width=8, justify="center")
    syringeOnTimeEntry.grid(row=7, column=1, padx=gridPadDef[0], pady=gridPadDef[1] - 4)

    #### SMS Options ####
    SMSParamsWindows = tk.Toplevel()
    SMSParamsWindows.title("SMS Settings")
    SMSParamsWindows.geometry('+%d+%d'%(500,450))

    SMSFrame = tk.LabelFrame(SMSParamsWindows, text="Options", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    SMSFrame.pack()

    checkInterval = tk.StringVar(SMSFrame, check_interval_def)
    notifyTimer = tk.StringVar(SMSFrame, notify_interval_def)
    errorNotify = tk.StringVar(SMSFrame, error_notify_interval_def)

    checkIntervalLabel = tk.Label(SMSFrame, text="Check Interval (s.)")
    checkIntervalLabel.grid(row=0, column=0, padx=gridPadDef[0])
    checkIntervalEntry = tk.Entry(SMSFrame, width=8, textvariable=checkInterval, justify="center")
    checkIntervalEntryTip = CreateToolTip(checkIntervalEntry,\
                                          "Sets amount of time between each check of voltage and current, in seconds")
    checkIntervalEntry.grid(row=0, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    notifyTimerLabel = tk.Label(SMSFrame, text="Notification Timer (min.)")
    notifyTimerLabel.grid(row=1, column=0, padx=gridPadDef[0])
    notifyTimerEntry = tk.Entry(SMSFrame, width=8, textvariable=notifyTimer, justify="center")
    notifyTimerEntryTip = CreateToolTip(notifyTimerEntry,\
                                        "Sets how often to send a notification if the system is running ok in minutes")
    notifyTimerEntry.grid(row=1, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    errorNotifyLabel = tk.Label(SMSFrame, text="Error Notification (min.)")
    errorNotifyLabel.grid(row=2, column=0, padx=gridPadDef[0])
    errorNotifyEntry = tk.Entry(SMSFrame, width=8, textvariable=errorNotify, justify="center")
    errorNotifyEntryTip = CreateToolTip(errorNotifyEntry,\
                                        "Sets how often to notify if the system has reached an error in minutes")
    errorNotifyEntry.grid(row=2, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    emailTestButton = tk.Button(SMSFrame, bd=2, text="Test Email Protocol", pady=5,
                               width=buttonDef[2] - 5, height=buttonDef[3])
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
    ps_ident = 0 #NOTE: This may need to be moved up later on

    ## List of variables that need to be initialized first cause I don't wanna have to rewrite a bunch of code
    #sp_port
    #s_manufacturer DONE
    #s_volume DONE
    #force DONE
    #use_syringe_pump


    def initWindow(ps_ident):
        initWin = tk.Toplevel()
        initWin.title("Initialization Window")
        initFrame = tk.Frame(initWin)
        initFrame.pack()

        finishInit = tk.Button(initFrame, text="Initialize", command=lambda: initDoneSwitch(initWin,ps_ident))
        finishInit.grid(row=10,column=0,pady=10,padx=10,columnspan=3)

        psOptionLabel = tk.Label(initFrame,textvariable=tk.StringVar(initFrame,"Choose a power supply"),height=2, padx=labelPadXDef)
        psOptionLabel.grid(row=0,columnspan=3)
        psOption = tk.OptionMenu(initFrame, psVar, "Agilent E3631A", "Agilent E3634A", "Keysight E36105B")
        psOption.config(width=20,height=2)
        psOption.grid(row=1, column=0, columnspan=3)

        forceInitLabel = tk.Label(initFrame, textvariable=tk.StringVar(initFrame, "Syringe Force"), height=2,padx=labelPadXDef)
        forceInitLabel.grid(row=2,column=0)
        forceInitBox = tk.Entry(initFrame, text="Low Warning", textvariable=syringeForce, width=8, justify="center")
        forceInitTip = CreateToolTip(forceInitBox, \
                                   "Sets an initial force value to initialize the pump with (can be changed later")
        forceInitBox.grid(row=3, column=0,pady=2)


        return

    def initDoneSwitch(breakThis,ps_ident):
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
            ps_port = 'ASRL/dev/ttyUSB0::INSTR'
            channel = 8
            ps = E3631A_PS(channel, ps_port, ps_ident)
        elif  psVar.get() == "Agilent E3634A":
            ps_ident = 2
            ps_port = 'ASRL/dev/ttyUSB0::INSTR'
            channel = 5
            # ps = E3634A_PS(channel, ps_port, ps_ident)
        elif psVar.get() == "Keysight E36105B":
            ps_ident = 3
            ps_port = 'USB::10893::6146::MY59001199::INSTR'
            channel = None  # not needed for this power supply and usbtmc interface
            # ps = E36105B_PS(channel, ps_port, ps_ident)
        print(ps_ident)

        # Initialize the syringe pump

    initWindow(ps_ident)

    runButton.config(command=lambda: ps_monitorSingle())

    root.mainloop()


if __name__ == '__main__':
    notify_flag = 2
    use_text_only_for_bad_news = True

    menu()

    # Initialization window

    # SID="ACb4dd1978c3860effcff4d26ffaad4b99"
    # AUTH="a5f4f656cbfd9de498f2df038d8579d9"
    # TO_NUM='+18017267329'
    # FROM_NUM='+15012733970'
    #
    # ps_ident = 1
    # s_manufacturer = 'bdp'
    # s_volume = '3 ml'
    # force = 50 #Hard Code
    # use_syringe_pump = False
    #
    # ## Begin initialization
    #
    # [ps, sp] = Monitor_Initialize(ps_ident,s_manufacturer,s_volume,force,use_syringe_pump)
    #
    # testX = [1,3,4,5]
    # testY = [2,5,6,3]
    #
    # # Voltage in Volts. Current in Amps
    # V_def = 1
    # I_def = 0.1
    #
    # V_set = V_def
    # I_set = I_def
    #
    # fn = sys.stdin.fileno()
    # sys.stdin = os.fdopen(fn)
    #
    # keep_running = True
    # while keep_running:
    #     print('\nMain menu:')
    #     print('1: Test voltage,current')
    #     print('2: Change voltage, current')
    #     print('3: Run electroplating')
    #     print('4: Infuse')
    #     print('5: Quit and exit')
    #     choice = input('choice:  ')
    #
    #     # get the time that the choice started for logging purposes
    #     file_name = datetime.now().strftime('%Y_%m_%d__%H_%M_%S')
    #
    #     if choice == '1':
    #         # set the power supply to output
    #         print('Monitoring for 5 seconds at 1 second intervals.')
    #         ps.run(V_set, I_set)
    #
    #         st = time.time()
    #         now = 0
    #         while now - st < 5:
    #             now = time.time()
    #
    #             # print voltage, amperage to terminal
    #             V_new, I_new = ps.read_V_I()
    #             print('%.1f  %.3f   %.3f' % (now - st, V_new, I_new))
    #
    #         ps.stop()
    #         print('Test done. If you need to change the bounds on voltage or current, you will need to exit and edit code to do it.')
    #
    #     elif choice == '2':
    #
    #         print('Set voltage (V) upper limits and desired current (A). Power supply will not apply voltage now.')
    #
    #         V_set = input('Voltage upper limit in volts (default is %f V): ' % V_def)
    #         if V_set == '':
    #             V_set = V_def
    #         else:
    #             V_set = float(V_set)
    #
    #         I_set = input('Desired current in amperes   (default is %f A): ' % I_def)
    #         if I_set == '':
    #             I_set = 0.405
    #         else:
    #             I_set = float(I_set)
    #
    #     elif choice == '3':
    #
    #         # start the monitoring loop and start the electroplating.
    #         infusion_list = ps_monitorSingle()
    #
    #         # set the plot event so that plotting also happens
    #
    # plt.plot(testX,testY)
    #
    # plt.show()


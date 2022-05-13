#### Super hardcoded values. Won't need to change 99% of the time
# For NotifyC Class

from twilio.rest import Client
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

from datetime import datetime

import pyautogui

SID = "ACb4dd1978c3860effcff4d26ffaad4b99"
AUTH = "a5f4f656cbfd9de498f2df038d8579d9"
TO_NUM = '+18017267329'
FROM_NUM = '+15012733970'

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
        self.error_notify_count = 0  # Current amount of errors
        self.error_notify_cnt_MAX = error_notify_cnt_MAX
        self.error_notify_interval = error_notify_interval
        self.error_notify_timer = 0
        self.error_notify_ref = 0  # Start of sending errors?

        self.use_text_only_for_bad_news = use_text_only_for_bad_news

        self.infused_volume = 0
        self.msg = ''  # Sends status of motors and stuff in case things break

        # Hardcoded things
        self.fromEmail = "stl.electroplating@gmail.com"
        self.toEmail = ["spokosison@gmail.com"]
        self.pathToScreenshot = "/home/pi/Desktop"
        self.nameScreenshot = 'download.jpeg' #Note that this needs to be mapped to the desktop screenshot
        self.pathToCredentials = "/home/pi/Desktop/credentials.json"
        self.dirToPickle = "/home/pi/Desktop"

    # Create googleEmailAPI functions for message protocol. Won't need to be used outside of this class? (Hopefully)
    def get_service(self, pathToCredentials, dirToPickle):
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
            print("Found Existing Pickle Path")
            with open(picklePath, 'rb') as token:
                creds = pickle.load(token)

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            print("No Credentials found, letting user log in")
            if creds and creds.expired and creds.refresh_token:
                print("Creds found but expired")
                creds.refresh(Request())
            else:
                print("Starting Local Server thing")
                flow = InstalledAppFlow.from_client_secrets_file(
                    pathToCredentials, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(picklePath, 'wb') as token:
                print("Saving Credentials")
                pickle.dump(creds, token)

        service = build('gmail', 'v1', credentials=creds)
        return service

    def send_message(self, service, sender, message):
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

    def create_message(self, sender, to_list, subject, message_text, img1):
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

        # "img1["path"], 'rb'"

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
        return self.I_bounds, self.V_bounds

    def setIVBounds(self, newIBounds, newVBounds):
        # Sets a new boundary for the current and the voltage in the form of
        # [Low warning, high warning]

        self.I_bounds = newIBounds  # [Set current]
        self.V_bounds = newVBounds  # [Set (higher), high warning]
        return

    # Probably where most of the things will need to be changed
    def notify(self, case, vNew, iNew, infused_amt_q, msg, notify_list, failLast20):
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

        notify_time_ref = notify_list[0]
        notify_time = notify_list[1]

        if msg != '':
            self.msg = msg

        # get current time
        current_date_time = datetime.now().strftime('%Y-%m-%d %H_%M_%S')

        # get infused volume
        # infused_vl = self.infused_volume
        # for ii in range(infused_amt_q.qsize()):
        #     infused_vl = infused_vl + infused_amt_q.get()
        # self.infused_volume = infused_vl
        infused_v1 = 85

        # Creates a txt log of the current message as well and saves it to a folder.

        if case == "Standard":
            emailBody = '%s. Good.%s V: %.3f V, I: %.3f .A Inf: %.3f uL. Fails Last 20 minutes: %.3f' % (
                current_date_time, self.msg, vNew, iNew, infused_v1, failLast20)
            pass
        if case == "Voltage Out of Bounds":
            emailBody = '%s. Voltage Out of Bounds.%s V: %.3f V, I: %.3f .A Inf: %.3f uL.' % (
                current_date_time, self.msg, vNew, iNew, infused_v1)
            pass
        if case == "Current outside range":
            emailBody = '%s. Current Out of Range.%s V: %.3f V, I: %.3f .A Inf: %.3f uL.' % (
                current_date_time, self.msg, vNew, iNew, infused_v1)
            pass
        if case == "Reading Failed":
            emailBody = '%s. ERROR-%s. Warn %d. V: %.3f V, I: %.3f A. Inf: %.0f uL.' % (
                current_date_time, self.msg, self.error_notify_count, vNew, iNew, infused_v1)
        if case == "Fail Threshold Reached":
            emailBody = "Reached more than 20 errors in the last 20 minutes. Most likely due to a problem with the power supply at this point"
            pass



        ## Basic part of the code, will be sent every time

        ## Send text message

        # if self.notifyType in [1, 3] and self.use_text_only_for_bad_news is False:
        #     try:
        #         self.td['client'].messages.create(to=self.td['to_num'], from_=self.td['from_num'], body=emailBody)
        #     except:
        #         print("Could not send text message notification, going to hope that the error was not fatal")

        #Get a screenshot the the system?
        #fn = os.getcwd() + '/screenshots/screenshot.png'
        if os.path.exists("/home/pi/Electroplating/screenshots/screenshot.png"):
            os.remove("/home/pi/Electroplating/screenshots/screenshot.png")
        
        os.system('scrot -q 75 /home/pi/Electroplating/screenshots/screenshot.png')
        
       #pyautogui.screenshot().save(r'/home/pi/Electroplating/screenshots/screenshot.png')
        
        pathToScreenshot = "/home/pi/Electroplating/screenshots"
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
            print("Could not create the email message")
        try:
            self.send_message(service, self.fromEmail, message)
        except:
            print("Could not send message, continuing and hoping that the error is not fatal")

        return [notify_time_ref, notify_time]
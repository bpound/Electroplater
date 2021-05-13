from datetime import datetime
from twilio.rest import Client
import sys,os,time,pyvisa,email, smtplib, ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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

        # email parameters, commenting out some of them for now
        # self.sender_email = "stl.electroplating@gmail.com"
        # self.sender_email_password = 'mems4us!'
        # self.receiver_email = my_email
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

                emailBody = '%s. ERROR-%s.%s Warn %d. Inf: %.3f uL. V: %.3f V, I: %.3f A.' % (
                    current_date_time, typeD, self.msg, self.error_notify_count, infused_vl, V_new, I_new)
                print(emailBody)

                # Ignore text message prootcols for now
                # if self.notifyType in [1, 3]:
                #     try:
                #         self.notify_textmessage(message)
                #     except:
                #         print(
                #             'Could not *bad* notify via text message - continuing and hoping that the error was not fatal.')

                if self.notifyType in [2, 3]:
                    try:
                        self.notify_email(emailBody)
                    except:
                        print('Could not *bad* notify via email - continuing and hoping that the error was not fatal.')

                # After we send a message, create
                self.error_notify_ref = time.time()

            self.msg = ''
            service = self.get_service(self.pathToCredentials, self.dirToPickle)
            message = self.create_message(self.fromEmail, self.toEmail, "Test subject", "Test body", img1)
            self.send_message(service, self.fromEmail, message)

        elif self.notify_interval < notify_time:
            emailBody = '%s. Good.%s Inf: %.3f uL. V: %.3f V, I: %.3f .A' % (
                current_date_time, self.msg, infused_vl, V_new, I_new)

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
            self.msg = '' #What is this even used for?

        if self.notify_interval < notify_time: # Wait why is this even here?
            notify_time_ref = time.time()
            notify_time = 0
        else:
            pass  # ? Why needed

        return [notify_time_ref, notify_time]
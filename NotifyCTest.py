from datetime import datetime
from twilio.rest import Client
import sys,os,time,pyvisa,email, smtplib, ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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


    '''
    def __init__(self, SID, AUTH, TO_NUM, FROM_NUM, my_email, V_bounds, I_bounds, error_notify_interval,
                 error_notify_cnt_MAX, notify_interval, notifyType, use_text_only_for_bad_news):

        # create SMS client, and save parameters to dictionary
        sms_client = Client(SID, AUTH)
        twilio_dict = {'client': sms_client, 'to_num': TO_NUM, 'from_num': FROM_NUM}
        self.td = twilio_dict
        self.notifyType = notifyType
        self.notify_interval = notify_interval
        self.V_bounds = V_bounds
        self.I_bounds = I_bounds
        self.error_notify_count = 0
        self.error_notify_cnt_MAX = error_notify_cnt_MAX
        self.error_notify_interval = error_notify_interval
        self.error_notify_timer = 0
        self.error_notify_ref = 0

        # email parameters
        self.sender_email = "stl.electroplating@gmail.com"
        self.sender_email_password = 'mems4us!'
        self.receiver_email = my_email
        self.use_text_only_for_bad_news = use_text_only_for_bad_news

        self.infused_volume = 0
        self.msg = ''

    def getIVBounds(self):
        return self.I_bounds,self.V_bounds

    def setIVBounds(self,newIBounds,newVBounds):
        # Sets a new boundary for the current and the voltage in the form of
        # [Low warning, high warning]

        self.I_bounds = newIBounds # [Set current]
        self.V_bounds = newVBounds # [Set (higher), high warning]
        return

    def notify(self, V_new, I_new, notify_list, msg, infused_amt_q):
        # What's infused_amt_q

        # unpack list
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

        # construct message based on V value
        if (V_new < self.V_bounds[0] or V_new > self.V_bounds[1] or I_new < self.I_bounds[0] or I_new > self.I_bounds[
            1]) and self.error_notify_count < self.error_notify_cnt_MAX:
            if (V_new < self.V_bounds[0]) or I_new > self.I_bounds[1]:
                typeD = 'Shorting'
            if V_new > self.V_bounds[1] or I_new < self.I_bounds[0]:
                typeD = 'Disconnected'

            if self.error_notify_count == 0:
                self.error_notify_ref = time.time()

            self.error_notify_timer = (time.time() - self.error_notify_ref) / 60.0

            if self.error_notify_timer > self.error_notify_interval or self.error_notify_count == 0:

                self.error_notify_count = self.error_notify_count + 1

                message = '%s. ERROR-%s.%s Warn %d. Inf: %.3f uL. V: %.3f V, I: %.3f A.' % (
                current_date_time, typeD, self.msg, self.error_notify_count, infused_vl, V_new, I_new)
                print(message)

                if self.notifyType in [1, 3]:
                    try:
                        self.notify_textmessage(message)
                    except:
                        print(
                            'Could not *bad* notify via text message - continuing and hoping that the error was not fatal.')

                if self.notifyType in [2, 3]:
                    try:
                        self.notify_email(message)
                    except:
                        print('Could not *bad* notify via email - continuing and hoping that the error was not fatal.')

                self.error_notify_ref = time.time()

            self.msg = ''

        elif self.notify_interval < notify_time:
            message = '%s. Good.%s Inf: %.3f uL. V: %.3f V, I: %.3f A.' % (
            current_date_time, self.msg, infused_vl, V_new, I_new)

            if self.notifyType in [1, 3] and self.use_text_only_for_bad_news is False:
                try:
                    self.notify_textmessage(message)
                except:
                    print(
                        'Could not *good* notify via text message - continuing and hoping that the error was not fatal.')

            if self.notifyType in [2, 3]:
                try:
                    self.notify_email(message)
                except:
                    print('Could not *good* notify via email - continuing and hoping that the error was not fatal.')

            # reset error count, just in case of a temporary disconnect
            self.error_notify_count = 0
            self.error_notify_ref = time.time()
            self.error_notify_timer = 0

            # always print to terminal
            print(message)
            self.msg = ''

        if self.notify_interval < notify_time:
            notify_time_ref = time.time()
            notify_time = 0
        else:
            pass  # ? Why needed

        return [notify_time_ref, notify_time]

    def notify_textmessage(self, message):
        self.td['client'].messages.create(to=self.td['to_num'], from_=self.td['from_num'], body=message)

    def notify_email(self, message):
        subject = message
        body = message
        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = self.receiver_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        # specify filename and capture screen
        fn = os.getcwd() + '/screenshot.png'
        os.system('scrot %s -q 75' % fn)

        with open(fn, "rb") as attachment:
            # Add file as application/octet-stream
            # Email client can usually download this automatically as attachment
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())

        # Encode file in ASCII characters to send by email
        encoders.encode_base64(part)

        # Add header as key/value pair to attachment part
        part.add_header(
            "Content-Disposition",
            "attachment", filename=fn)

        # Add attachment to message and convert message to string
        message.attach(part)
        text = message.as_string()

        # Log in to server using secure context and send email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(self.sender_email, self.sender_email_password)
            server.sendmail(self.sender_email, self.receiver_email, text)

#!/usr/bin/env python

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from datetime import datetime
from twilio.rest import Client
import sys,os,time,pyvisa,email, smtplib, ssl, usbtmc
from matplotlib.widgets import Button
import multiprocessing as mp
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class NotifyC():
    def __init__(self,SID,AUTH,TO_NUM,FROM_NUM,my_email,V_bounds,I_bounds,error_notify_interval,error_notify_cnt_MAX,notify_interval,notify_flag,use_text_only_for_bad_news):
    
        # create SMS client, and save parameters to dictionary
        sms_client = Client(SID,AUTH)
        twilio_dict = {'client':sms_client,'to_num':TO_NUM,'from_num':FROM_NUM}
        self.td = twilio_dict
        self.notify_flag = notify_flag
        self.notify_interval = notify_interval
        self.V_bounds = V_bounds
        self.I_bounds = I_bounds 
        self.error_notify_count = 0
        self.error_notify_cnt_MAX = error_notify_cnt_MAX
        self.error_notify_interval = error_notify_interval
        self.error_notify_timer = 0
        self.error_notify_ref = 0
        
        # email parameters
        self.sender_email = electroplater_email # note that I just didn't want to put this in the repo, just because. Maybe we could have a text file that we read things like this from.
        self.sender_email_password = 'not going to put that here'
        self.receiver_email = my_email
        self.use_text_only_for_bad_news = use_text_only_for_bad_news

        self.infused_volume = 0
        self.msg = ''
    
    def notify(self, V_new ,I_new , notify_list , msg , infused_amt_q):
    
        # unpack list
        notify_time_ref = notify_list[0]
        notify_time = notify_list[1]

        if msg != '':
            self.msg = msg

        # get current time
        current_date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # get infused volume
        infused_vl = self.infused_volume
        for ii in range( infused_amt_q.qsize() ):
            infused_vl = infused_vl + infused_amt_q.get()
        self.infused_volume=infused_vl
        
        # construct message based on V value
        if (V_new<self.V_bounds[0] or V_new>self.V_bounds[1] or I_new<self.I_bounds[0] or I_new>self.I_bounds[1]) and self.error_notify_count<self.error_notify_cnt_MAX :
            if (V_new<self.V_bounds[0]) or I_new>self.I_bounds[1]:
                typeD = 'Shorting'
            if V_new>self.V_bounds[1] or I_new<self.I_bounds[0]:
                typeD = 'Disconnected'
                
            if self.error_notify_count == 0:
                self.error_notify_ref = time.time()
                
            
            self.error_notify_timer = (time.time() - self.error_notify_ref)/60.0
            
            if self.error_notify_timer>self.error_notify_interval or self.error_notify_count == 0:

                self.error_notify_count = self.error_notify_count+1
                
                
                message = '%s. ERROR-%s.%s Warn %d. Inf: %.3f uL. V: %.3f V, I: %.3f A.'%(current_date_time,typeD,self.msg,self.error_notify_count,infused_vl,V_new,I_new)
                print(message)
            
                
                if self.notify_flag in [1,3]:
                    try:
                        self.notify_textmessage(message)
                    except:
                        print('Could not *bad* notify via text message - continuing and hoping that the error was not fatal.')

                if self.notify_flag in [2,3]:
                    try:
                        self.notify_email(message)
                    except:
                        print('Could not *bad* notify via email - continuing and hoping that the error was not fatal.')
                
                    

                self.error_notify_ref = time.time()

            self.msg = ''
                
        elif self.notify_interval<notify_time:
            message = '%s. Good.%s Inf: %.3f uL. V: %.3f V, I: %.3f A.'%(current_date_time,self.msg,infused_vl,V_new,I_new)

            if self.notify_flag in [1,3] and self.use_text_only_for_bad_news is False:
                try:
                    self.notify_textmessage(message)
                except:
                    print('Could not *good* notify via text message - continuing and hoping that the error was not fatal.')

            if self.notify_flag in [2,3]:
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
        
            
        if self.notify_interval<notify_time:
            notify_time_ref = time.time()
            notify_time = 0
        else:
            pass
            
        return [notify_time_ref,notify_time]
                
    def notify_textmessage(self,message):
        self.td['client'].messages.create(to=self.td['to_num'],from_=self.td['from_num'],body=message) 
    
    def notify_email(self,message):
        subject = message
        body = message
        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = self.receiver_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))
        
        # specify filename and capture screen
        fn = os.getcwd() + '/screenshot.png'
        os.system('scrot %s -q 75'%fn)
        
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
            "attachment", filename= fn)

        # Add attachment to message and convert message to string
        message.attach(part)
        text = message.as_string()

        # Log in to server using secure context and send email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(self.sender_email, self.sender_email_password)
            server.sendmail(self.sender_email, self.receiver_email, text)
            
            
class E36105B_PS():
    def __init__(self,channel,ps_port,ps_ident):

        # save identification
        self.ident = ps_ident
        
        # open up Resource Manager
        #rm = pyvisa.ResourceManager('@py')
        
        # open up the right channel
        # the USB resource needs to be figured out beforehand, there is no way to figure out which power supply is 
        try:
            ps = usbtmc.Instrument(ps_port)
            
            # set address and protocol
            #ps.write('++addr %i'%channel)
            #ps.write('++eos 0') #Append CR+LF (ASCII 13 & 10 respectively) to instrument commands
            time.sleep(0.01)
            
            # try to get a response from power supply, in this case its identity
            idn = ps.ask('*IDN?\n')
            #ps.write('++read')
            print('Power supply identity: %s , %s'%(ps_port,idn) )
            
            # save communication instance into class variable
            self.ps = ps
        except:
            print('Something went wrong with power supply initialization.')
            self.ps = None           
    def run(self,V,I):
        
        if self.ps is not None:
            # take output off, set new voltage and current, then turn output back on
            # ps.write('OUTPUT OFF\n')
            #self.ps.write('VOLTage:RANGe P25V\n')
            self.ps.write('APPL %f, %f\n'%(V,I))
            
            # turn on the output
            self.ps.write('OUTPUT ON\n')
            print('Started power supply output.')
        else:
            print('Cannot run power supply; power supply did not initialize properly.')    
    def read_V_I(self):
        
        if self.ps is not None:
            # query power supply for voltage
            #self.ps.write('MEASURE:VOLTAGE?')
            measV = self.ps.ask('MEASURE:VOLTAGE?\n')
            #self.ps.write('++read')
            voltage = float(measV)
            
            # query power supply for current
            #self.ps.write('MEASURE:CURRENT?')
            measI = self.ps.ask('MEASURE:CURRENT?\n')
            #self.ps.write('++read') # Reads until timeout. So what might be happening is that its reading more than one value?
            current = float(measI)
        else:
            print('Cannot measure voltage/current; power supply did not initialize properly.')
            voltage=-1
            current=-1
        
        return voltage,current    
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
        
        #winsound.Beep(440,500)
        input('put the test resistor on the terminals')
        print('watch the power supply, see if the voltage or current reaches the specified levels')
        v=1;i=0.005
        self.run(v,i)
        print('Desired V, I: %f , %f'%(v,i))
        time.sleep(3)
        #winsound.Beep(440,500)
        v,i = self.read_V_I();
        print('Actual V, I: %f , %f'%(v,i))
        time.sleep(3)
        #winsound.Beep(440,500)
        nv = 0.4
        ni = 0.005
        self.run(nv,ni)
        print('Desired V, I: %f , %f'%(nv,ni))
        time.sleep(3)
        #winsound.Beep(440,500)
        v,i = self.read_V_I();
        print('Actual V, I: %f , %f'%(v,i))
        time.sleep(3)
        #winsound.Beep(440,500)
        ps.stop()
        print('output stopped')
        time.sleep(3)
        #winsound.Beep(440,500)
        v=1;i=0.005
        self.run(v,i)
        print('Desired V, I: %f , %f'%(v,i))
        time.sleep(3)
        #winsound.Beep(440,500)
        v,i = self.read_V_I();
        print('Actual V, I: %f , %f'%(v,i))
        self.stop()
        
class E3631A_PS():
    def __init__(self,channel,ps_port,ps_ident):

        # save identification
        self.ident = ps_ident
        
        # open up Resource Manager
        rm = pyvisa.ResourceManager('@py')
        
        # open up the right channel
        # the USB resource needs to be figured out beforehand, there is no way to figure out which power supply is 
        try:
            ps = rm.open_resource(ps_port)
            
            # set address and protocol
            ps.write('++addr %i'%channel)
            ps.write('++eos 0')
            time.sleep(0.01)
            
            # try to get a response from power supply, in this case its identity
            ps.write('*IDN?')
            ps.write('++read')
            print('Power supply identity: %s , %s'%(ps_port,ps.read().strip()) )
            
            # save communication instance into class variable
            self.ps = ps
        except:
            print('Something went wrong with power supply initialization.')
            self.ps = None           
    def run(self,V,I):
        
        if self.ps is not None:
            # take output off, set new voltage and current, then turn output back on
            # ps.write('OUTPUT OFF')
            self.ps.write('APPL P6V, %f, %f'%(V,I))
            
            # check if output is already on
            self.ps.write('OUTPUT?')
            self.ps.write('++read')
            on_flag = self.ps.read().strip()
            
            if on_flag =='0':
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
            voltage=1
            current=1
        
        return voltage,current    
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
    def __init__(self,channel,ps_port,ps_ident):

        # save identification
        self.ident = ps_ident
        
        # open up Resource Manager
        rm = pyvisa.ResourceManager('@py')
        
        # open up the right channel
        # the USB resource needs to be figured out beforehand, there is no way to figure out which power supply is 
        try:
            ps = rm.open_resource(ps_port)
            
            # set address and protocol
            ps.write('++addr %i'%channel)
            ps.write('++eos 0')
            time.sleep(0.01)
            
            # try to get a response from power supply, in this case its identity
            ps.write('*IDN?')
            ps.write('++read')
            print('Power supply identity: %s , %s'%(ps_port,ps.read().strip()) )
            
            # save communication instance into class variable
            self.ps = ps
        except:
            print('Something went wrong with power supply initialization.')
            self.ps = None           
    def run(self,V,I):
        
        if self.ps is not None:
            # take output off, set new voltage and current, then turn output back on
            # ps.write('OUTPUT OFF')
            self.ps.write('VOLTage:RANGe P25V')
            self.ps.write('APPL %f, %f'%(V,I))
            
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
            voltage=1
            current=1
        
        return voltage,current    
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
    def __init__(self,sp_port,s_manufacturer,s_volume,force,use_syringe_pump):
    
        self.use_flag = use_syringe_pump
        
        if use_syringe_pump is False:
        
            self.sp = None
            
        else:
        
            try:
                rm = pyvisa.ResourceManager()
                self.sp = rm.open_resource(sp_port)
                self.sp.query('echo on')
                self.sp.query('ver')
                print('Syringe pump identity: %s , %s'%(sp_port,self.sp.read().strip()) )
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
                self.sp.query('force %i'%force)
                
                # set the syringe volume, manufacturer. May need to do this manually, depending on syringe on hand. See manual.
                self.sp.query('syrm %s %s'%(s_manufacturer,s_volume))
                self.sp.query('syrm')
                print('Syringe type: %s'%self.sp.read().strip())          
    def set_parameters(self,current_A,infuse_rate,infuse_interval):
        
        if self.sp is not None:
            # get pump ready for operation by clearing some counters
            self.sp.query('civolume')
            self.sp.query('ctvolume')
            self.sp.query('citime')
            self.sp.query('cttime')
           
            # this is the factor, in mL/(A hr), to find the replenisher.
            # its hard-coded in so that people don't mess it up on accident.

            factor_A_hr_mL = 0.085   # real value
            
            # get the limits of the machine for the chosen syringe
            self.sp.query('irate lim')
            limits = self.sp.read()
            limits = limits.split()
            
            # lim = [numerical value, volume unit, time unit]
            # official good units: uL/second
            low_lim = [float(limits[0])] + limits[1].split('/')    
            high_lim = [float(limits[3])] + limits[4].split('/')

            # convert limits of pump with chosen syringe to ul/sec
            lims=[]
            for lim in [low_lim,high_lim]:

                if lim[1] == 'ml':
                    factor_v=10**3
                elif lim[1] == 'ul':
                    factor_v= 1
                elif lim[1] == 'l':
                    factor_v = 10**6
                elif lim[1] == 'nl':
                    factor_v = 10**-3
                elif lim[1] == 'pl':
                    factor_v = 10**-6
                else:
                    factor_v = 1
                    print('unknown volume units in limit')
                
                if lim[2] == 'hr':
                    factor_t = 3600
                elif lim[2] =='min':
                    factor_t = 60
                elif lim[2] =='s':
                    factor_t = 1
                else:
                    factor_t = 1
                    print('unknown time units in limit')
                    
                lims.append( lim[0]*factor_v/factor_t )
            
            # how much to infuse every {interval} hours. infuse_volume is in nL.
            # native units are mL, 10**3 converts to uL
            infuse_volume = current_A * infuse_interval * factor_A_hr_mL*1.0*10**3
            print('\nNeed replenisher volume (uL) per interval: %f'%infuse_volume)
            print('Infuse limits: [ %f, %f ] uL/sec'%(lims[0],lims[1]))
            print('Desired: infuse rate %f uL/s over %f seconds every %f hours.'%(infuse_rate,1.0*infuse_volume/infuse_rate,infuse_interval))
            
            if infuse_rate>lims[0] and infuse_rate<lims[1]:
                #print('Desired infuse rate OK')
                pass
            elif infuse_rate <= lims[0]:
                #print('Desired infuse rate too low. Setting infuse rate to lower limit.')
                infuse_rate = lims[0]*1.01
           
            elif infuse_rate >= lims[1]:
                #print('Desired infuse rate too high. Setting infuse rate to upper limit.')
                infuse_rate = lims[1]*0.99
                
            infuse_time = 1.0*infuse_volume/infuse_rate
            print('Set:     infuse rate %f uL/s over %f seconds every %f hours.'%(infuse_rate,infuse_time,infuse_interval))
            
            # set the parameters
            self.sp.query('irate %f ul/s'%infuse_rate)
            self.sp.query('tvolume %f ul'%infuse_volume)
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
                curr_rate = float(status[0])*1.0*10**-9 # converting from fL/s to uL/s
                t = int(status[1])/1000.0
                already_infused_volume = float(status[2])*1.0*10**-9


                # parsing the flag part
                flag = status[3]
                if flag[5] == 'T':
                    print('Pump done. Total infused volume: %.2f uL'%already_infused_volume)
                    break
                else:
                    print( 'Elapsed time (s): %.2f. Infused volume (uL): %.2f. Rate (uL/s): %.2f.'%(t,already_infused_volume,curr_rate) )

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

        return already_infused_volume,curr_rate
    def infuse(self):

        if self.sp is not None:
            # this gets rid of the pesky "T*" status commands that randomly pop up and screw everything up.
            self.sp.query('poll on')

            # runs the pump
            self.sp.query('run')
        else:
            if self.use_flag is True:
                print('Cannot run syringe pump; syringe pump was not initialized properly.')           
    def set_rate_volume_directly(self,rate_i,volume_i):
        
        if self.sp is not None:
            self.sp.query('irate %f ul/sec'%rate_i)
            time.sleep(0.1)
            self.sp.query('tvolume %f ul'%volume_i)
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
            
            
# plotting functions
def PS_plot(V_axes,I_axes,T,V,I):
        
    # plot axes one and two, using only the existing data, not all the zeros that are appended to the end
    V_axes.clear(); V_axes.plot(T,V)
    I_axes.clear(); I_axes.plot(T,I)
            
    # set some labels
    try:
        # total elapsed time in hh:mm:ss
        hr,rem = divmod(T[-1]-T[0],3600)
        
        mins,sec = divmod(rem,60)
        time_axis_title = "Time (s): Elapsed time is {:0>2} hours, {:0>2} minutes, {:d} seconds".format(int(hr),int(mins),int(sec))
    except:
        time_axis_title = "Time (s)"
        
    I_axes.set_xlabel(time_axis_title)
    I_axes.set_ylabel('Current (A)')
    V_axes.set_ylabel('Voltage (V)')
    
    plt.pause(0.0001)
def PS_figure_action_on_exit( evt , STOP_ALL_FLAG  ):
    if STOP_ALL_FLAG.qsize()==1:
        STOP_ALL_FLAG.get()
    STOP_ALL_FLAG.put(True)
def Plotting_Initialize(SID,AUTH,TO_NUM,FROM_NUM,my_email,V_bounds,I_bounds,error_notify_cnt_MAX,error_notify_interval,notify_interval, notify_flag, use_text_only_for_bad_news,BREAK_FLAG, STOP_ALL_FLAG,PLOT_EVT,T_q,V_q,I_q,fn,MOTOR_HAS_STALLED,infused_amt_q):
    
    # wait to do anything until the plot event has been triggered
    break_flag = BREAK_FLAG.get()
    BREAK_FLAG.put(break_flag)
    
    while break_flag is False:
        PLOT_EVT.wait()

        # read and reset
        stop_all_flag = STOP_ALL_FLAG.get()
        STOP_ALL_FLAG.put(stop_all_flag)
        
        if stop_all_flag is False:
            # iniatialize notify class
            Notify = NotifyC(SID,AUTH,TO_NUM,FROM_NUM,my_email,V_bounds,I_bounds,error_notify_interval,error_notify_cnt_MAX,notify_interval,notify_flag,use_text_only_for_bad_news)
                
            # create figure with callback to shut everything down when the window is closed.
            fig,[V_axes,I_axes] = plt.subplots(2,1)
            fig.suptitle('Real-time plots of characteristics')  
            fig.canvas.mpl_connect('close_event', lambda window_event: PS_figure_action_on_exit( window_event , STOP_ALL_FLAG ) )
            
            
            # initializations
            T = []
            V = []
            I = []    
            prev_notify_ind = 0
            notification_timer = [time.time(),0] # first value is the "reference" in seconds, second value is the value of current timer in minutes
            
        while stop_all_flag is False:
        
            # wait until event or timeout to continue loop, whichever comes first
            time.sleep(0.5)
            
            # get the new entries of T,V,I
            for ii in range(T_q.qsize()):
                T.append(T_q.get())
                V.append(V_q.get())
                I.append(I_q.get())
                
            # do the notification
            # update the timer
            notification_timer[1] = (time.time() - notification_timer[0])/60

            if MOTOR_HAS_STALLED.is_set():
                msg = ' MTR STALL.'
                MOTOR_HAS_STALLED.clear()
            else:
                msg = ''
                
            notification_timer = Notify.notify( V[-1] , I[-1] , notification_timer, msg , infused_amt_q)

            # plot the whole dataset
            PS_plot(V_axes,I_axes, T,V,I)     
            
            # read and re- set the STOP_ALL_FLAG
            stop_all_flag = STOP_ALL_FLAG.get()
            STOP_ALL_FLAG.put(stop_all_flag)
            
         
        PLOT_EVT.clear()
        
        break_flag = BREAK_FLAG.get()
        BREAK_FLAG.put(break_flag)

# power supply monitoring functions
def Monitor_Initialize( ps_ident, T_q,V_q,I_q,V_def,I_def,ps_checking_interval,fn,force,infuse_rate,infuse_interval,s_manufacturer,s_volume,num_times_to_check,STOP_ALL_FLAG,PLOT_EVT,BREAK_FLAG,A_HR_LEFTOVER ,MOTOR_HAS_STALLED,infused_amt_q,use_syringe_pump):

    # first, initialize the power supply
    # rm = pyvisa.ResourceManager('@py')
    #ps_port = 'ASRL5::INSTR'
    # ps_port = 'ASRL/dev/ttyUSB0::INSTR'
        

    
    if ps_ident == 1:
        ps_port = 'ASRL/dev/ttyUSB0::INSTR'
        channel = 8
        ps = E3631A_PS(channel,ps_port,ps_ident)
    elif ps_ident == 2:
        ps_port = 'ASRL/dev/ttyUSB0::INSTR'
        channel = 5
        ps = E3634A_PS(channel,ps_port,ps_ident)
    elif ps_ident == 3:
        ps_port = 'USB::10893::6146::MY59001199::INSTR'
        channel = None # not needed for this power supply and usbtmc interface
        ps = E36105B_PS(channel,ps_port,ps_ident)
    else:
        print('Check power supply identification again, invalid choice entered.')
          
    # then initialize the syringe pump
    #sp_port = 'ASRL4::INSTR'
    # sp_port='ASRL/dev/ttyACM0::INSTR'
    # pvisa port identifier for the syringe pump
    sp_port='ASRL/dev/ttyACM0::INSTR'   
    sp = Legato100_SP( sp_port,s_manufacturer,s_volume,force,use_syringe_pump )
        
    # now go to the menu.
    Menu(ps,sp,V_def,I_def,ps_checking_interval,fn,force,infuse_rate,infuse_interval,s_manufacturer,s_volume,num_times_to_check,T_q,V_q,I_q,STOP_ALL_FLAG,PLOT_EVT,BREAK_FLAG,A_HR_LEFTOVER,MOTOR_HAS_STALLED,infused_amt_q)

def ps_monitor(ps,V_set,I_set,ps_checking_interval,sp,infuse_interval,infuse_rate,num_times_to_check,T_q,V_q,I_q,PLOT_EVT,STOP_ALL_FLAG,A_HR_LEFTOVER,MOTOR_HAS_STALLED,file_name,infused_amt_q):

    # turn on the power supply
    ps.run(V_set,I_set)
    time.sleep(0.2)
    
    start_time = time.time()
    notify_list = [start_time,0]
    
    stop_all_flag = STOP_ALL_FLAG.get()
    STOP_ALL_FLAG.put(stop_all_flag)
    infuse_timer_ref = time.time()
    total_I = 0
    infusion_list = []
    new_time = time.time()
    
    # get filename and open file 
    if ps.ident == 1:
        ps_file_name = os.getcwd()+'/EP_log_files/CopperBath/PowerSupplyReadings/PS_'+file_name+'.txt'
    elif ps.ident == 2:
        ps_file_name = os.getcwd()+'/EP_log_files/Permalloy/PowerSupplyReadings_'+file_name+'.txt'
    elif ps.ident == 3:
        ps_file_name = os.getcwd()+'/EP_log_files/LowCurrent/PowerSupplyReadings_'+file_name+'.txt'
        
    print('Saved power supply readings to: %s'%ps_file_name)
    f = open( ps_file_name , 'w' )
    f.write('Time(s)  Voltage(V)  Current(A)')
            
    while stop_all_flag is False:
    
        # calculate total elapsed time
        old_time = new_time
        new_time = time.time()
        total_time = new_time - start_time

        #get voltage, current from power supply
        try:
            V_new,I_new = ps.read_V_I()
        except:
            print('Failed to get measurement - sleeping and skipping to next iteration hoping that the problem was not fatal.')
            
            # first, check the stop_all_flag, just in case the loop has been terminated
            stop_all_flag = STOP_ALL_FLAG.get()
            STOP_ALL_FLAG.put(stop_all_flag)
            if stop_all_flag is False:
                time.sleep(ps_checking_interval)
            
            # restart the loop
            continue
            
        # put new measurements into queues:
        T_q.put(total_time)
        V_q.put(V_new)
        I_q.put(I_new)
        
        # print voltage, amperage to terminal and file
        curr_str = '%.1f  %.3f   %.3f'%(total_time, V_new , I_new)
        print( curr_str )
        f.write( curr_str+'\n' )
        
        # trigger event for plotting
        PLOT_EVT.set()
        
        # check infuse timer condition
        if (new_time - infuse_timer_ref)/3600.0 > infuse_interval:
        
            # get the full difference between time points
            total_T = new_time - infuse_timer_ref
            
            # take the total I and divide it by the total time to get the average current over the time period
            try:
                I_avg = (total_I)/total_T
            except:
                I_avg = 0
            
            # reset the reference timer and total_I 
            infuse_timer_ref = new_time
            total_I = 0
            
            # set the infuse parameters and run the pump
            sp.set_parameters(I_avg,infuse_rate,infuse_interval)
            time.sleep(0.1)
            sp.infuse()
            
            # monitor the infusion
            infused_volume,infuse_rate = sp.check_rate_volume(MOTOR_HAS_STALLED)
            curr_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_infusion = '%s : infused %.3f uL replenisher after %.2f hours at %.3f uL/s with %.3f A average current.'%(curr_time,infused_volume,infuse_interval,infuse_rate,I_avg)
            
            if sp.use_flag is True:
                infusion_list.append(new_infusion)
                infused_amt_q.put( infused_volume )
                print("# infusions: ",infused_amt_q.qsize())

        else:
            
            total_I = total_I + I_new*(new_time-old_time)

        # sleep for the specified amount of time
        stop_all_flag = STOP_ALL_FLAG.get()
        STOP_ALL_FLAG.put(stop_all_flag)
        if stop_all_flag is False:
            time.sleep(ps_checking_interval)
        
        # check the flag after the long sleep
        stop_all_flag = STOP_ALL_FLAG.get()
        STOP_ALL_FLAG.put(stop_all_flag)

    # get residual amp average and time interval after loop has ended
    hr_leftover = (new_time - infuse_timer_ref)
    try:
        A_HR_LEFTOVER.put(total_I/hr_leftover)
        A_HR_LEFTOVER.put(hr_leftover/3600)
    except:
        A_HR_LEFTOVER.put(0)
        A_HR_LEFTOVER.put(0)
        
    # turn off the power supply
    ps.stop()
    
    # close file
    f.close()

    # return the infusion list
    return infusion_list
 
def Menu(ps,sp,V_def,I_def,ps_checking_interval,fn,force,infuse_rate,infuse_interval,s_manufacturer,s_volume,num_times_to_check,T_q,V_q,I_q,STOP_ALL_FLAG,PLOT_EVT,BREAK_FLAG,A_HR_LEFTOVER,MOTOR_HAS_STALLED,infused_amt_q):

    # open up stdin here
    sys.stdin = os.fdopen(fn)
    
    # some initializations
    keep_running=True
    break_flag=False
    V_set = V_def
    I_set = I_def
    
    while keep_running:
        print('\nMain menu:')
        print('1: Test voltage,current')
        print('2: Change voltage, current')
        print('3: Run electroplating')
        print('4: Infuse')
        print('5: Quit and exit')
        choice = input('choice:  ')
        
        # get the time that the choice started for logging purposes
        file_name = datetime.now().strftime('%Y_%m_%d__%H_%M_%S')
        
        if choice == '1':
            # set the power supply to output
            print('Monitoring for 5 seconds at 1 second intervals.')
            ps.run(V_set,I_set)

            st = time.time()
            now = 0
            while now - st < 5:
                now = time.time()
                
                # print voltage, amperage to terminal
                V_new,I_new = ps.read_V_I()
                print('%.1f  %.3f   %.3f'%(now - st, V_new , I_new) )

            ps.stop()
            print('Test done. If you need to change the bounds on voltage or current, you will need to exit and edit code to do it.')
            
        elif choice == '2':
        
            print('Set voltage (V) upper limits and desired current (A). Power supply will not apply voltage now.')

            V_set = input('Voltage upper limit in volts (default is %f V): '%V_def)
            if V_set=='':
                V_set = V_def
            else:
                V_set = float(V_set)
            
            
            I_set = input('Desired current in amperes   (default is %f A): '%I_def)
            if I_set=='':
                I_set = 0.405
            else:
                I_set = float(I_set)
            
            
        elif choice == '3':

            # start the monitoring loop and start the electroplating.
            infusion_list = ps_monitor(ps,V_set,I_set,ps_checking_interval,sp,infuse_interval,infuse_rate,num_times_to_check,T_q,V_q,I_q,PLOT_EVT,STOP_ALL_FLAG,A_HR_LEFTOVER,MOTOR_HAS_STALLED,file_name,infused_amt_q)

            a_leftover = A_HR_LEFTOVER.get(); print('average current in last segment (A): %f'%a_leftover)
            hr_leftover = A_HR_LEFTOVER.get(); print('time of last legment (hr): %f'%hr_leftover)
            
            if sp.use_flag is True:
                equ_infuse  = input('Do you want to do one last infusion to put bath in equilibrium (y/n)? ')
                if equ_infuse.lower()=='y':

                    # do one last infusion
                    # get left over values from queue and set parameters
                    sp.set_parameters(a_leftover,infuse_rate,hr_leftover)
                    
                    # run the syringe pump                    
                    time.sleep(0.1)
                    sp.infuse()
                    time.sleep(0.1)

                    # generate entry
                    leftover_volume,leftover_rate = sp.check_rate_volume(MOTOR_HAS_STALLED)
                    curr_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    new_infusion = '%s : infused %.3f uL replenisher after %.2f hours at %.3f uL/s with %.3f A average current.'%(curr_time,leftover_volume,hr_leftover,leftover_rate,a_leftover)
                    infusion_list.append(new_infusion)

                # infusion printing to file
                cwd = os.getcwd()
                fullname = cwd+'/EP_log_files/CopperBath/Infusion/InfusionData_'+file_name+'.txt'
                print('Saved infusion data to: %s'%fullname)
                
                with open( fullname,'w' ) as f:
                    for infusion in infusion_list:
                        f.write( infusion+'\n' )

            # set the plot event so that plotting also happens
            keep_running=True
            BREAK_FLAG.get()
            BREAK_FLAG.put(False)
            PLOT_EVT.clear()
            STOP_ALL_FLAG.get(); STOP_ALL_FLAG.put(False)
            
        elif choice == '4':
            if sp.use_flag is True:
                choice_i = input('input (1) volume or (2) amperes and hours with 0.085 factor? ')
                if choice_i == '1':
                    volume_i = float(input('Volume (uL): '))
                    rate_i   = float(input('Rate (uL/s) (needs to be >0.002) : '))
                
                elif choice_i == '2':
                    factor = 0.085
                    amperes_i = float(input('Amps (A): '))
                    time_i   = float(input('Over a period of what # hours: '))
                    volume_i = factor * amperes_i*time_i*10^3
                    rate_i   = float(input('Rate (uL/s) (needs to be >0.002) : '))
                
                else:
                    print('Not a valid choice.')
                    
                # set the parameters
                sp.set_rate_volume_directly(rate_i,volume_i)
                sp.infuse()
            else:
                print('User specified in start up to not use syringe pump, so this option does not do anything. Change the syringe pump flag.')

        elif choice == '5':
            
            keep_running = False
            BREAK_FLAG.get()
            BREAK_FLAG.put(True)
            
            # close out the power supply and syringe pump
            try:
                ps.stop()
                ps.disconnect()
            except:
                print('error with closing power supply.')
            
            try:
                sp.disconnect()
                print('Syringe pump off and disconnected.')
            except:
                print('error with closing syringe pump.')
                
            STOP_ALL_FLAG.get()
            STOP_ALL_FLAG.put(True)
            time.sleep(0.1)
            
            PLOT_EVT.set()
            
        else:
            print('Not a valid choice. Choose again.')

def main(force,infuse_rate,infuse_interval,s_manufacturer,s_volume,num_times_to_check,SID,AUTH,TO_NUM,FROM_NUM,my_email,checking_interval,error_notify_interval,notify_interval,notify_flag,use_text_only_for_bad_news,V_bounds,I_bounds,V_def,I_def,ps_ident,use_syringe_pump):

    ##### here are some pseudo-hard coded parameters that usually won't need to be changed
    
    # maximum number of notifications of bad events until the program stops sending notifications.
    error_notify_cnt_MAX = 10

    # initialize the Queues.
    T_q = mp.Queue(maxsize=0)
    V_q = mp.Queue(maxsize=0)
    I_q = mp.Queue(maxsize=0)
    
    # initialize events
    STOP_ALL_FLAG = mp.Queue(maxsize=1); STOP_ALL_FLAG.put(False)
    PLOT_EVT = mp.Event();PLOT_EVT.clear()
    INFUSE_EVT = mp.Event();INFUSE_EVT.clear()
    BREAK_FLAG = mp.Queue(maxsize=1); BREAK_FLAG.put(False)
    A_HR_LEFTOVER = mp.Queue()
    MOTOR_HAS_STALLED = mp.Event(); MOTOR_HAS_STALLED.clear()
    infused_amt_q = mp.Queue()
    
    # stdin identifier
    fn = sys.stdin.fileno()
    
    # initialize power supply monitoring, notify, and syringe pump routines.
    instr_proc = mp.Process( target = Monitor_Initialize, args= ( ps_ident, T_q,V_q,I_q, V_def,I_def,checking_interval,fn, force,infuse_rate,infuse_interval,s_manufacturer,s_volume,num_times_to_check,STOP_ALL_FLAG,PLOT_EVT,BREAK_FLAG,A_HR_LEFTOVER,MOTOR_HAS_STALLED,infused_amt_q,use_syringe_pump) )
    
    # initialize plotting routine processes - done
    plotting_proc = mp.Process( target = Plotting_Initialize , args = (SID,AUTH,TO_NUM,FROM_NUM,my_email,V_bounds,I_bounds,error_notify_cnt_MAX,error_notify_interval,notify_interval, notify_flag, use_text_only_for_bad_news,BREAK_FLAG,STOP_ALL_FLAG,PLOT_EVT,T_q,V_q,I_q,fn,MOTOR_HAS_STALLED,infused_amt_q) )

    instr_proc.start()
    plotting_proc.start()
    
    instr_proc.join()
    plotting_proc.join()
    
if __name__ == '__main__':
    
    ######################
    ###### set parameters
    ######################
    
    #### Syringe pump parameters ####
    
    # percent. Usually between 50-100, but look at documentation
    force = 50
    
    # infuse rate in uL/s
    #infuse_rate = 0.5
    infuse_rate=2
    
    # interval time between infusions in hours
    infuse_interval = 1.5
    
    # num times to check
    num_times_to_check = 3
    
    # syringe info
    s_manufacturer = 'bdp'
    s_volume = '3 ml'
    
    #### Notification parameters ####
    # client number, which number to send from. You would get these from the Twilio online interface.
    SID=""
    AUTH=""
    TO_NUM=""
    FROM_NUM=""

    # how often to check voltage and current, in seconds
    checking_interval = 5.0

    # how often to notify (if still good) in minutes
    notify_interval = 20.0

    # how often to notify if bad in minutes
    error_notify_interval = 1
    
    # my email to send notifications to
    my_email = ""
    
    # notification settings. Notifications only happen at the specified interval unless something goes wrong - notification happens immediately, then.
    # always terminal alert. 0:only terminal. 1: SMS. 2:Email. 3: SMS+Email. terminal alert.
    notify_flag = 2
    use_text_only_for_bad_news = True

    #### Power supply parameters ####
    # bounds on voltage (volts) and current (amps) - notify if voltage or current escapes bounds
    V_bounds = [0.02,5]
    I_bounds = [0.005,0.8]
    
    # V_def (volts), I_def (amps)
    V_def = 3.50
    I_def = 0.370
    
    # power supply identification: 1 = 3631A (for copper), 2 = 3634 (for permalloy), 3 = 36105 (for low current)
    ps_ident = 3
    
    # use syringe pump? True or False
    use_syringe_pump = False
    
    # run main function
    main(force,infuse_rate,infuse_interval,s_manufacturer,s_volume,num_times_to_check,SID,AUTH,TO_NUM,FROM_NUM,my_email,checking_interval,error_notify_interval,notify_interval,notify_flag,use_text_only_for_bad_news,V_bounds,I_bounds,V_def,I_def,ps_ident,use_syringe_pump)

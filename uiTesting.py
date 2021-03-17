#Talk to outside things modules and adjusting Python Interpreter
from datetime import datetime
from twilio.rest import Client
import sys,os,time,pyvisa,email, smtplib, ssl
from matplotlib.widgets import Button
import multiprocessing as mp #allows multi-core processing = faster stuff
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

#GUI modules uhh just import everything delete later
import tkinter as tk
from tkinter import scrolledtext
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle
from matplotlib.collections import PatchCollection
import numpy as np
import matplotlib.animation as animation
import matplotlib.backends.backend_tkagg as tkagg

#### Define button functions ####

#### Create Dictionary of Widgets to use in Callback functions ####
# v = voltage
# i = currrent
v_params_widget_list = {'target': -1,'lowWarn':-1,'highWarn':-1,}
i_params_widget_list = {'iBox':-1}
oxy_params_widget_list = {}
pump_params_widget_list = {}

def ui():

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
    factor_def = 0.085
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

    #### VI settings Window ####
    root = tk.Tk()
    root.title("Main Settings")

    labelPadXDef = 5
    labelFramePadDef = [10, 10]
    buttonDef = [10, 10, 14, 1]  # padx,pady,width,height
    gridPadDef = [10, 10]

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
    vTargetBoxLabel.grid(row=0, column=0)
    vTargetBox = tk.Entry(voltage_frame, text="Target", textvariable=vTarget, width=8, justify="center")
    vTargetBox.grid(row=1, column=0)

    # Low voltage warning
    vLowText = tk.StringVar()
    vLowText.set("Low Voltage \nWarning (V)")
    vLowBoxLabel = tk.Label(voltage_frame, textvariable=vLowText, height=2, padx=labelPadXDef)
    vLowBoxLabel.grid(row=0, column=1)
    vLowBox = tk.Entry(voltage_frame, text="Low Warning", textvariable=vLowWarn, width=8, justify="center")
    vLowBox.grid(row=1, column=1)

    # high voltage warning
    vHighText = tk.StringVar()
    vHighText.set("High Voltage \nWarning(V)")
    vHighBoxLabel = tk.Label(voltage_frame, textvariable=vHighText, height=2, padx=labelPadXDef)
    vHighBoxLabel.grid(row=0, column=2)
    vHighBox = tk.Entry(voltage_frame, text="High Warning", textvariable=vHighWarn, width=8, justify="center")
    vHighBox.grid(row=1, column=2)

    # Create String variable for target current
    current_frame = tk.LabelFrame(root, text="Current", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    current_frame.pack()

    iTargetText = tk.StringVar(current_frame, str(cur_def))
    iText = tk.StringVar(value="Target \nCurrent (A)")

    iBoxLabel = tk.Label(current_frame, textvariable=iText, height=2, padx=labelPadXDef, pady=2)
    iBoxLabel.grid(row=0, column=0)
    iBox = tk.Entry(current_frame, text="Target Current", textvariable=iTargetText, width=8, justify="center")
    iBox.grid(row=1, column=0,padx=gridPadDef[0],pady=2)

    iArea1LabelText = tk.StringVar(value="Area 1\n(m^2)")
    iArea1Label = tk.Label(current_frame,textvariable=iArea1LabelText)
    iArea1Label.grid(row=0,column=1)

    iArea1Text = tk.StringVar(current_frame,str(1))
    iArea1 = tk.Entry(current_frame,text="Area 1",textvariable=iArea1Text,width = 8,justify="center")
    iArea1.grid(row=1,column=1,padx=gridPadDef[0], pady=2)

    iDensity1 = tk.StringVar(current_frame,"Area 1\nCurrent Density\n(A/m^2):\n")
    iDensity1Label = tk.Label(current_frame,textvariable=iDensity1,height=4,padx=labelPadXDef, pady=2)
    iDensity1Label.grid(row = 2,column = 1,pady=2)

    def calcDensity1(event):
        try:
            float(iArea1.get())
        except:
            iArea1.delete(0,"end")
            iArea1.insert(0,str(1))
            return
        result = float(iBox.get()) /float(iArea1.get())
        result = "{:.3f}".format(result)
        iDensity1.set("Area 1\nCurrent Density\n(A/m^2):\n" + result)

    iBox.bind('<FocusOut>',calcDensity1,add="+")
    iBox.bind('<Return>', calcDensity1,add="+")
    iArea1.bind('<FocusOut>',calcDensity1,add="+")
    iArea1.bind('<Return>', calcDensity1,add="+")

    iArea2LabelText = tk.StringVar(value="Area 2\n(m^2)")
    iArea2Label = tk.Label(current_frame,textvariable=iArea2LabelText)
    iArea2Label.grid(row=0,column=2)

    iArea2Text = tk.StringVar(current_frame,str(1))
    iArea2 = tk.Entry(current_frame,text="Area 2",textvariable=iArea2Text, width = 8, justify="center")
    iArea2.grid(row=1,column=2,padx=gridPadDef[0], pady=2)

    iDensity2 = tk.StringVar(current_frame,"Area 2\nCurrent Density\n(A/m^2):\n")
    iDensity2Label = tk.Label(current_frame,textvariable=iDensity2,height=4)
    iDensity2Label.grid(row = 2,column = 2,pady=2)

    def calcDensity2(event):
        try:
            float(iArea2.get())
        except:
            iArea2.delete(0,"end")
            iArea2.insert(0,str(1))
            return
        if(float(iArea2.get()) <= 0):
            iArea2.delete(0,"end")
            iArea2.insert(0,str(1))
            return
        result = float(iBox.get()) /float(iArea2.get())
        result = "{:.3f}".format(result)
        iDensity2.set("Area 2\nCurrent Density\n(A/m^2):\n" + result)

    iBox.bind('<FocusOut>',calcDensity2,add="+")
    iBox.bind('<Return>',calcDensity2,add="+")
    iArea2.bind('<FocusOut>',calcDensity2,add="+")
    iArea2.bind('<Return>',calcDensity2,add="+")

    ############################

    #### Make main buttons ####
    IVButtonFrame = tk.LabelFrame(root, text="Main Controls", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    IVButtonFrame.pack()

    testButton = tk.Button(IVButtonFrame, bd=1, text="Test IV \nSettings", padx=buttonDef[0], pady=buttonDef[1],
                           width=buttonDef[2], height=buttonDef[3])
    testButton.config(command=lambda : testVI())
    testButton.grid(row=0, column=0, padx=gridPadDef[0], pady=gridPadDef[1])

    runButton = tk.Button(IVButtonFrame, bd=1, text="Run Electroplating", padx=buttonDef[0], pady=buttonDef[1],
                          width=buttonDef[2], height=buttonDef[3])
    runButton.config(command=lambda : runElectroplating())
    runButton.grid(row=1, column=0, padx=gridPadDef[0], pady=gridPadDef[1])

    stopButton = tk.Button(IVButtonFrame, bd=1, text="Stop", padx=buttonDef[0], pady=buttonDef[1],
                           width=buttonDef[2], height=buttonDef[3])
    stopButton.config(command =lambda : emergencyStop())
    stopButton.grid(row=1, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    ###########################

    #### Make main output Console ####
    outputFrame = tk.LabelFrame(root, text="Output Window", padx=labelFramePadDef[0]-2, pady=labelFramePadDef[1]-2)
    outputFrame.pack()

    output = scrolledtext.ScrolledText(outputFrame,width=60,height=20,font=("Tekton Pro",9))
    output.grid(row=0, column=0, padx=0, pady=2)
    ##################################

    #### Oxygen and Syringe Pump Window ####
    oxyPumpParams = tk.Toplevel()
    oxyPumpParams.title("Oxygen and Syringe Pump Settings")

    #### Oxygen Stuff ####
    oxyFrame = tk.LabelFrame(oxyPumpParams, text="Oxygen Sensor", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    oxyFrame.pack()

    oxyOn = tk.IntVar()
    oxyOn.set = 0
    oxySwitch = tk.Checkbutton(oxyFrame, text="Enable?", variable=oxyOn)
    oxySwitch.grid(row=0, column=0)

    oxySensorReadLabel=tk.Label(oxyFrame,text="Oxygen Sensor\nRead",height=2)
    oxySensorReadLabel.grid(row=0,column=2,padx=gridPadDef[0])

    oxySliderLabel= tk.Label(oxyFrame,text="Some Oxygen\nParameter",height=2)
    oxySliderLabel.grid(row=1,column=0)
    oxySlider = tk.Scale(oxyFrame, from_=0, to=100, orient="horizontal", resolution=1, length=200)
    oxySlider.grid(row=1, column=1)

    oxySliderManual = tk.Entry(oxyFrame,width=7)
    oxySliderManual.grid(row=1,column=2,padx=gridPadDef[0])

    #### Syringe Pump Stuff ####
    pumpFrame = tk.LabelFrame(oxyPumpParams,text="Syringe Pump",padx=labelFramePadDef[0],pady=labelFramePadDef[1])
    pumpFrame.pack()

    pumpOn = tk.IntVar(0)
    pumpSwitch = tk.Checkbutton(pumpFrame,text="Enable?", variable=pumpOn,justify="right")
    pumpSwitch.grid(row=0,column=0,pady=gridPadDef[1])

    pumpTestButton = tk.Button(pumpFrame,bd=2, text="Test Pump",pady=5,
                           width=buttonDef[2]-5, height=buttonDef[3])
    pumpTestButton.grid(row=0,column=1,pady=gridPadDef[1])

    ## Make a bunch of Entry parameters

    infuseRate = tk.StringVar(pumpFrame,infuse_rate_def)
    infuseInterval = tk.StringVar(pumpFrame,infuse_interval_def)
    timeToCheck = tk.StringVar(pumpFrame,num_times_to_check_def)
    syringeFactor = tk.StringVar(pumpFrame,factor_def)
    syringeCurrent = tk.StringVar(pumpFrame,syringe_current_def)
    syringeOnTime = tk.StringVar(pumpFrame,syringe_on_time_def)

    infuseRateLabel = tk.Label(pumpFrame,text="Infuse Rate")
    infuseRateLabel.grid(row=1,column=0,padx=gridPadDef[0])
    infuseRateEntry = tk.Entry(pumpFrame,textvariable=infuseRate,width=8,justify="center")
    infuseRateEntry.grid(row=2,column=0,padx=gridPadDef[0],pady=gridPadDef[1]-2)

    infuseIntervalLabel = tk.Label(pumpFrame,text="Infuse Interval")
    infuseIntervalLabel.grid(row=3,column=0,padx=gridPadDef[0])
    infuseIntervalEntry = tk.Entry(pumpFrame, textvariable=infuseInterval, width=8, justify="center")
    infuseIntervalEntry.grid(row=4,column=0,padx=gridPadDef[0],pady=gridPadDef[1]-4)

    timeToCheckLabel = tk.Label(pumpFrame,text="Time to Check")
    timeToCheckLabel.grid(row=5,column=0,padx=gridPadDef[0])
    timeToCheckEntry = tk.Entry(pumpFrame, textvariable=timeToCheck, width=8, justify="center")
    timeToCheckEntry.grid(row=6,column=0,padx=gridPadDef[0],pady=gridPadDef[1]-4)

    syringeFactorLabel = tk.Label(pumpFrame,text = "Syringe Factor")
    syringeFactorLabel.grid(row=1,column=1,padx=gridPadDef[0])
    syringeFactorEntry = tk.Entry(pumpFrame, textvariable=syringeFactor, width=8, justify="center")
    syringeFactorEntry.grid(row=2,column=1,padx=gridPadDef[0],pady=gridPadDef[1]-4)

    syringeCurrentLabel = tk.Label(pumpFrame,text = "Syringe Current")
    syringeCurrentLabel.grid(row=3,column=1,padx=gridPadDef[0])
    syringeCurrentEntry = tk.Entry(pumpFrame, textvariable=syringeCurrent, width=8, justify="center")
    syringeCurrentEntry.grid(row=4,column=1,padx=gridPadDef[0],pady=gridPadDef[1]-4)

    syringeOnTimeLabel = tk.Label(pumpFrame, text = "Syringe On Time")
    syringeOnTimeLabel.grid(row=5,column=1,padx=gridPadDef[0])
    syringeOnTimeEntry = tk.Entry(pumpFrame, textvariable=syringeOnTime, width=8, justify="center")
    syringeOnTimeEntry.grid(row=6,column=1,padx=gridPadDef[0],pady=gridPadDef[1]-4)

    #### SMS Options ####
    SMSParamsWindows = tk.Toplevel()
    SMSParamsWindows.title("SMS Settings")
    SMSFrame = tk.LabelFrame(SMSParamsWindows,text="Options", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    SMSFrame.pack()

    checkInterval = tk.StringVar(SMSFrame,check_interval_def)
    notifyTimer = tk.StringVar(SMSFrame,notify_interval_def)
    errorNotify = tk.StringVar(SMSFrame,error_notify_interval_def)

    checkIntervalLabel = tk.Label(SMSFrame,text="Check Interval (s.)")
    checkIntervalLabel.grid(row=0,column=0,padx=gridPadDef[0])
    checkIntervalEntry = tk.Entry(SMSFrame,width = 8,textvariable=checkInterval)
    checkIntervalEntry.grid(row=0, column=1, padx=gridPadDef[0], pady=gridPadDef[1])
    
    notifyTimerLabel = tk.Label(SMSFrame,text= "Notification Timer (min.)")
    notifyTimerLabel.grid(row=1,column=0,padx=gridPadDef[0])
    notifyTimerEntry = tk.Entry(SMSFrame,width = 8,textvariable=notifyTimer)
    notifyTimerEntry.grid(row =1, column = 1,padx=gridPadDef[0], pady=gridPadDef[1])

    errorNotifyLabel = tk.Label(SMSFrame,text= "Error Notification (min.)")
    errorNotifyLabel.grid(row=2,column=0,padx=gridPadDef[0])
    errorNotifyEntry = tk.Entry(SMSFrame,width = 8,textvariable=errorNotify)
    errorNotifyEntry.grid(row=2,column=1,padx=gridPadDef[0], pady=gridPadDef[1])

    # Check if bad number was put in
    def BadNumber(event):
        if float(iBox.get()) < 0:
            iBox.delete(0,"end")
            iBox.insert(0,cur_def)

    iBox.bind('<FocusOut>', BadNumber)

    def testVI():

        testVoltage = vTargetBox.get()
        testCurrent = iBox.get()
        ### Rewrite original command window code
        output.insert(tk.INSERT,"Monitoring for 5 seconds at 1 second intervals\nCurrent: " + str(testVoltage)
                      +" V\nVoltage: " + str(testCurrent) + " A\n\n")
        output.see("end")

        #ps.run(testVoltage,testCurrent)
        st = time.time()
        now = 0
        # while now - st < 5:
        #    now = time.time()
        #     print voltage, amperage to terminal (Probably replace in output window
        #
        #     V_new,I_new = ps.read_V_I()
        #     print('%.1f  %.3f   %.3f'%(now - st, V_new , I_new) )

        #ps.stop()

    def runElectroplating():
        # Get all parameters from entry boxes
        # file_name = datetime.now().strftime('%Y_%m_%d__%H_%M_%S') #Make log
        infusion_list = ps_monitor(ps, V_set, I_set, ps_checking_interval, sp, infuse_interval, infuse_rate,
                                   num_times_to_check, T_q, V_q, I_q, PLOT_EVT, STOP_ALL_FLAG, A_HR_LEFTOVER,
                                   MOTOR_HAS_STALLED, file_name, infused_amt_q)


    def emergencyStop():
        exit(2)

    root.mainloop()

if __name__ == '__main__':
    ui()

    #### Extra windows for VI and oxygen graph, probably will be scrapped
    # viGraph = tk.Toplevel()
    #
    # # Make VI curve graph
    # viGraph.title("Voltage and Current Readings")
    # figure1 = plt.figure(figsize=(4, 5), dpi=100)
    # ax1 = figure1.add_subplot(111)
    # ax1.set_title("Voltage and Current")
    # chart_type1 = FigureCanvasTkAgg(figure1, viGraph)
    #
    # chart_type1.get_tk_widget().pack()
    # tkagg.NavigationToolbar2Tk(chart_type1, viGraph)
    #
    # oxyGraph = tk.Toplevel()
    # oxyGraph.title("Oxygen Sensor Readings")
    # figure2 = plt.figure(figsize=(4, 5), dpi=100)
    # ax2 = figure2.add_subplot(111)
    # ax2.set_title("Oxygen Sensor")
    # chart_type2 = FigureCanvasTkAgg(figure2, oxyGraph)
    #
    # chart_type2.get_tk_widget().pack()
    # tkagg.NavigationToolbar2Tk(chart_type2, oxyGraph)
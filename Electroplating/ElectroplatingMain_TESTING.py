# Talk to outside things modules and adjusting Python Interpreter
from datetime import datetime
import time, pyvisa

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

# GUI modules
import tkinter as tk
import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from tkinter import scrolledtext

# try:
#     import RPi.GPIO as GPIO
# except:
#     import Mock.GPIO as GPIO

# Import our created hardware classes
import ToolTipStuff
import powerSupplies
import OPS
import NotifyClass
import monitor

screenshotPath = "C:\\Users\\Gabriele Domingo\\Pictures\\potato.png"
pathToLogs = "D:\\Files\\electro\\Logs"
'''
Class Order:
Power Supplies (95)
Legato100_SP (392)
O2_Sensor (609)
Solenoid_Controller (701)
NotifyCSingle (732)
monitorApp (1008)
Main GUI menu (1462)
'''

def testEmail(Notify):
    # Get a screenshot the the system?
    # fn = os.getcwd() + '/screenshot.png'
    # os.system('scrot %s -q 75' % fn)

    pathToScreenshot = "C:\\Users\\Thomas\\Pictures"
    pathToLogs = "D:\\Files\\electro\\Logs"
    nameScreenshot = "map.png"
    img1 = dict(title='desktop screenshot', path=os.path.join(pathToScreenshot, nameScreenshot))

    try:
        service = Notify.get_service(Notify.pathToCredentials, Notify.dirToPickle)
        message = Notify.create_message(Notify.fromEmail, Notify.toEmail, "Test subject",
                                        "If this email was received, the Notify class's email protocol is working", img1)
        Notify.send_message(service, Notify.fromEmail, message)
    except:
        print("Could not send test email")

    # Write test log
    print(os.getcwd())
    try:
        now = datetime.now()
        date_time = now.strftime("%m_%d_%Y %H_%M_%S")
        testLog = open(pathToLogs+"\\TEST LOG-"+date_time+".txt","w+")
        testLog.write("This is a test log. Details of current electroplating such as voltage and current will go here")
        testLog.close()
    except:
        print("Could not create test log")

    return

def menu():
    ###############################################################################
    ############################ LIST OF DEFAULT VALUES ###########################
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
    # sp_port = 'ASRL4::INSTR'
    # sp_port='ASRL/dev/ttyACM0::INSTR'
    # pvisa port identifier for the syringe pump
    sp_port = 'ASRL/dev/ttyACM0::INSTR'

    ## Solenoid defaults (Percentages)
    solenoid_low_bound_def = 0.5
    solenoid_high_bound_def = 2

    #### SMS defaults ####
    # how often to check voltage and current, in seconds
    check_interval_def = 5
    # how often to notify (if still good) in minutes
    notify_interval_def = 1.0
    # how often to notify if bad in minutes
    error_notify_interval_def = 1.0

    oxygen_on = False
    # Oxygen Calibration value in something
    oxygen_calibration_def = 1

    oxygen_reads_def = 10

    DEFVALUES = [volt_def[0],volt_def[1],volt_def[2],cur_def,
                 infuse_rate_def,infuse_interval_def,num_times_to_check_def,
                 solenoid_low_bound_def,solenoid_high_bound_def,check_interval_def,
                 notify_interval_def,error_notify_interval_def,10]

    ### Identification Numbers for each entry based on order of appearance:
    ### Generally done left to right, top to bottom with some windows taking priority
    ### Anything that gets missed or added will be shoved to the end

    # 0: Voltage Target
    # 1: Voltage Low
    # 2: Voltage High
    # 3: Current Target
    # 4: Syringe Pump Infusion Rate
    # 5: Syringe Pump Infusion Interval
    # 6: Syring Pump Number of Infusions
    # 7: Solenoid Low Bound
    # 8: Solenoid High Bound
    # 9: Power Supply Checking Interval
    # 10: Standard Notification Interval
    # 11: Error Notification Interval
    # 12: Number of Reads for Oxygen Calibration

    ###############################################################################
    ###############################################################################

    ## tkinter spacing defaults
    labelPadXDef = 5
    labelFramePadDef = [10, 10]
    buttonDef = [10, 10, 14, 1]  # padx,pady,width,height
    gridPadDef = [10, 10]

    #### Initialize NotifyC class with default parameters ####
    SID = "ACb4dd1978c3860effcff4d26ffaad4b99"
    AUTH = "a5f4f656cbfd9de498f2df038d8579d9"
    TO_NUM = '+18017267329'
    FROM_NUM = '+15012733970'

    NotifyObject = NotifyClass.NotifyCSingle(SID, AUTH, TO_NUM, FROM_NUM, [0.02, 18], cur_def, error_notify_interval_def,
                                 error_notify_cnt_MAX, notify_interval_def, notifyType, use_text_only_for_bad_news)

    #### Initialize Syringe Pump class with default parameters ####
    ## We initially keep the syringe disabled by default
    SyringeObject = OPS.Legato100_SP(sp_port, s_manufacturer, s_volume, factor_def, False)

    SolenoidObject = OPS.Solenoid_Controller()

    OxySensorObject = OPS.O2_Sensor(oxygen_reads_def)

    root = tk.Tk()
    root.title("Main Settings")
    root.geometry('+%d+%d' % (0, 0))

    voltage_frame = tk.LabelFrame(root, text="Voltage", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    voltage_frame.pack()

    plateOptionVar = tk.StringVar(voltage_frame)

    plateOption = tk.OptionMenu(voltage_frame, plateOptionVar, "Copper", "Nickel")
    plateOption.grid(row=0, column=0, columnspan=3)

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
    vTargetBoxTip = ToolTipStuff.CreateToolTip(vTargetBox, \
                            "Sets voltage for the power supply to aim to be around when running electroplating in volts")
    vTargetBox.grid(row=2, column=0)

    # Low voltage warning
    vLowText = tk.StringVar()
    vLowText.set("Low Voltage \nWarning (V)")
    vLowBoxLabel = tk.Label(voltage_frame, textvariable=vLowText, height=2, padx=labelPadXDef)
    vLowBoxLabel.grid(row=1, column=1)
    vLowBox = tk.Entry(voltage_frame, text="Low Warning", textvariable=vLowWarn, width=8, justify="center")
    vLowBoxTip = ToolTipStuff.CreateToolTip(vLowBox, \
                               "Lowest voltage the power supply can be until the user must be notified that something is wrong in volts.")
    vLowBox.grid(row=2, column=1)

    # high voltage warning
    vHighText = tk.StringVar()
    vHighText.set("High Voltage \nWarning(V)")
    vHighBoxLabel = tk.Label(voltage_frame, textvariable=vHighText, height=2, padx=labelPadXDef)
    vHighBoxLabel.grid(row=1, column=2)
    vHighBox = tk.Entry(voltage_frame, text="High Warning", textvariable=vHighWarn, width=8, justify="center")
    vHighBoxTip = ToolTipStuff.CreateToolTip(vHighBox, \
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
    iBoxTip = ToolTipStuff.CreateToolTip(iBox, \
                            "Target current we want the power supply to output. Usually more important than the voltage. In Amps.")
    iBox.grid(row=1, column=0, padx=gridPadDef[0], pady=2)

    iArea1LabelText = tk.StringVar(value="Area 1\n(m^2)")
    iArea1Label = tk.Label(current_frame, textvariable=iArea1LabelText)
    iArea1Label.grid(row=0, column=1)

    iArea1Text = tk.StringVar(current_frame, str(1))
    iArea1 = tk.Entry(current_frame, text="Area 1", textvariable=iArea1Text, width=8, justify="center")
    iArea1Tip = ToolTipStuff.CreateToolTip(iArea1, \
                              "Area of one side of the electroplating in m^2")
    iArea1.grid(row=1, column=1, padx=gridPadDef[0], pady=2)

    iDensity1 = tk.StringVar(current_frame, "Area 1\nCurrent Density\n(A/m^2):\n")
    iDensity1Label = tk.Label(current_frame, textvariable=iDensity1, height=4, padx=labelPadXDef, pady=2)
    iDensity1Label.grid(row=2, column=1, pady=2)

    def calcDensity1(event):
        try:
            float(iArea1.get())
            result = float(iBox.get()) / float(iArea1.get())
            result = "{:.3f}".format(result)
            iDensity1.set("Area 1\nCurrent Density\n(A/m^2):\n" + result)
        except:
            iArea1.delete(0, "end")
            iArea1.insert(0, str(1))
        return


    iBox.bind('<FocusOut>', calcDensity1, add="+")
    iBox.bind('<Return>', calcDensity1, add="+")
    iArea1.bind('<FocusOut>', calcDensity1, add="+")
    iArea1.bind('<Return>', calcDensity1, add="+")

    iArea2LabelText = tk.StringVar(value="Area 2\n(m^2)")
    iArea2Label = tk.Label(current_frame, textvariable=iArea2LabelText)
    iArea2Tip = ToolTipStuff.CreateToolTip(iArea1, \
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

    ## SEPERATE TO OWN WINDOW

    IVButtonFrame = tk.LabelFrame(root, text="Main Controls", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    IVButtonFrame.pack()

    testButton = tk.Button(IVButtonFrame, bd=1, text="Test IV \nSettings", padx=buttonDef[0], pady=buttonDef[1],
                           width=buttonDef[2], height=buttonDef[3])
    testButtonTip = ToolTipStuff.CreateToolTip(testButton, \
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

    # oxySensorReadLabel = tk.Label(oxyFrame, text="Oxygen Sensor\nRead", height=2)
    # oxySensorReadLabel.grid(row=0, column=0, padx=gridPadDef[0])
    # oxySensorReadBox = tk.Entry(oxyFrame,width = 7)
    # oxySensorReadBox.grid(row=0,column=1,padx=gridPadDef[0])
    # oxySensorReadBox['state'] = tk.DISABLED

    ##################################

    #### Oxygen and Syringe Pump Window ####
    oxyPumpParams = tk.Toplevel()
    oxyPumpParams.title("Oxygen and Syringe Pump Settings")
    oxyPumpParams.geometry('+%d+%d' % (500, 0))

    #### Oxygen Stuff ####
    oxyFrame = tk.LabelFrame(oxyPumpParams, text="Oxygen Sensor", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    oxyFrame.pack()

    oxyOn = tk.IntVar(0)
    oxySwitch = tk.Checkbutton(oxyFrame, text="Enable?", variable=oxyOn)
    oxySwitch.grid(row=0, column=0)

    oxySensorReadLabel = tk.Label(oxyFrame, text="Oxygen Sensor\nRead", height=2)
    oxySensorReadLabel.grid(row=0, column=2, padx=gridPadDef[0])

    oxySensorReadBox = tk.Entry(oxyFrame, width=7)
    oxySensorReadBox.grid(row=1, column=2, padx=gridPadDef[0])
    oxySensorReadBox['state'] = tk.DISABLED

    # oxySliderLabel = tk.Label(oxyFrame, text="Some Oxygen\nParameter", height=2)
    # oxySliderLabel.grid(row=1, column=0)
    # oxySlider = tk.Scale(oxyFrame, from_=0, to=100, orient="horizontal", resolution=1, length=200)
    # oxySlider.grid(row=1, column=1)
    #
    # oxySliderManual = tk.Entry(oxyFrame, width=7)
    # oxySliderManual.grid(row=1, column=2, padx=gridPadDef[0])

    oxyNumReads = tk.StringVar(oxyFrame, oxygen_reads_def)

    oxyNumReadsText = tk.StringVar()
    oxyNumReadsText.set("Number of Reads for Calibration")
    oxyNumReadsLabel = tk.Label(oxyFrame, textvariable=oxyNumReadsText, height=2, padx=labelPadXDef)
    oxyNumReadsLabel.grid(row=2, column=0)
    oxyNumReadsBox = tk.Entry(oxyFrame, text="Low Warning", textvariable=oxyNumReads, width=8, justify="center")
    oxyNumReadsTip = ToolTipStuff.CreateToolTip(oxyNumReadsBox, \
                                   "Lowest oxygen until solenoid disabling sequence is automatically started.")
    oxyNumReadsBox.grid(row=3, column=0)

    #### Syringe Pump Stuff ####
    pumpFrame = tk.LabelFrame(oxyPumpParams, text="Syringe Pump", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    pumpFrame.pack()

    pumpOn = tk.IntVar(0)
    pumpSwitch = tk.Checkbutton(pumpFrame, text="Enable?", variable=pumpOn, justify="left")
    pumpSwitch.grid(row=0, column=0, sticky="W")

    pumpEquillibrium = tk.IntVar(0)
    pumpEquillibriumSwitch = tk.Checkbutton(pumpFrame, text="Set bath to \nequillibrium on run",
                                            variable=pumpEquillibrium, justify="left")
    pumpEquillibriumSwitch.grid(row=1, column=0, sticky="W")

    pumpTestButton = tk.Button(pumpFrame, bd=2, text="Test Pump", pady=5,
                               width=buttonDef[2] - 5, height=buttonDef[3])
    pumpTestButton.config(command=lambda: testSyringePump())
    pumpTestButton.grid(row=0, column=1, rowspan=2)

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
    timesToCheckLabel = tk.Label(pumpFrame, text="Number of Infusions")
    timesToCheckLabel.grid(row=6, column=0, padx=gridPadDef[0])
    timesToCheckEntry = tk.Entry(pumpFrame, textvariable=timeToCheck, width=8, justify="center")
    timesToCheckEntry.grid(row=7, column=0, padx=gridPadDef[0], pady=gridPadDef[1] - 4)
    timesToCheckTooltip = ToolTipStuff.CreateToolTip(timesToCheckEntry, \
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

    solenoidFrame = tk.LabelFrame(oxyPumpParams, text="Solenoid")
    solenoidFrame.pack()

    solenoidLowBound = tk.StringVar(solenoidFrame, solenoid_low_bound_def)
    solenoidHighBound = tk.StringVar(solenoidFrame, solenoid_high_bound_def)

    solenoidOn = tk.IntVar(0)
    solenoidSwitch = tk.Checkbutton(solenoidFrame, text="Use Solenoid (Only if Permalloy)", variable=solenoidOn,
                                    justify="left")
    solenoidSwitch.grid(row=0, column=0)

    # Solenoid Low O2 Percentage
    solenoidLowText = tk.StringVar()
    solenoidLowText.set("Oxygen Lower Bound (%)")
    solenoidLowLabel = tk.Label(solenoidFrame, textvariable=solenoidLowText, height=2, padx=labelPadXDef)
    solenoidLowLabel.grid(row=1, column=0)
    solenoidLowBox = tk.Entry(solenoidFrame, text="Low Warning", textvariable=solenoidLowBound, width=8,
                              justify="center")
    solenoidLowBoxTip = ToolTipStuff.CreateToolTip(solenoidLowBox, \
                                      "Lowest oxygen until solenoid disabling sequence is automatically started.")
    solenoidLowBox.grid(row=2, column=0)

    # Solenoid Low O2 Percentage
    solenoidHighText = tk.StringVar()
    solenoidHighText.set("Oxygen Higher Bound (%)")
    solenoidHighLabel = tk.Label(solenoidFrame, textvariable=solenoidHighText, height=2, padx=labelPadXDef)
    solenoidHighLabel.grid(row=1, column=1)
    solenoidHighBox = tk.Entry(solenoidFrame, text="Low Warning", textvariable=solenoidHighBound, width=8,
                               justify="center")
    solenoidHighBoxTip = ToolTipStuff.CreateToolTip(solenoidHighBox, \
                                       "The Highest Oxygen concentratin before the solenoid must be opened")
    solenoidHighBox.grid(row=2, column=1)

    solenoidOpenButton = tk.Button(solenoidFrame, bd=1, text="Open Solenoid", padx=buttonDef[0], pady=buttonDef[1],
                                   width=buttonDef[2], height=buttonDef[3])
    solenoidOpenButton.grid(row=3, column=0, padx=gridPadDef[0], pady=gridPadDef[1])

    solenoidCloseButton = tk.Button(solenoidFrame, bd=1, text="Close Solenoid", padx=buttonDef[0], pady=buttonDef[1],
                                    width=buttonDef[2], height=buttonDef[3])
    solenoidCloseButton.grid(row=3, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    sole02TestButton = tk.Button(solenoidFrame, bd=1, text="Test 02/Solenoid", padx=buttonDef[0], pady=buttonDef[1],
                                    width=buttonDef[2], height=buttonDef[3])
    sole02TestButton.grid(row=4, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    #### SMS Options ####
    SMSParamsWindows = tk.Toplevel()
    SMSParamsWindows.title("Timings")
    SMSParamsWindows.geometry('+%d+%d' % (500, 450))

    SMSFrame = tk.LabelFrame(SMSParamsWindows, text="Options", padx=labelFramePadDef[0], pady=labelFramePadDef[1])
    SMSFrame.pack()

    checkInterval = tk.StringVar(SMSFrame, check_interval_def)
    notifyTimer = tk.StringVar(SMSFrame, notify_interval_def)
    errorNotify = tk.StringVar(SMSFrame, error_notify_interval_def)

    checkIntervalLabel = tk.Label(SMSFrame, text="Power Supply\n Checking Interval (s.)")
    checkIntervalLabel.grid(row=0, column=0, padx=gridPadDef[0])
    checkIntervalEntry = tk.Entry(SMSFrame, width=8, textvariable=checkInterval, justify="center")
    checkIntervalEntryTip = ToolTipStuff.CreateToolTip(checkIntervalEntry, \
                                          "Sets amount of time between each check of voltage and current, in seconds")
    checkIntervalEntry.grid(row=0, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    notifyTimerLabel = tk.Label(SMSFrame, text="Ok Notification Interval (min.)")
    notifyTimerLabel.grid(row=1, column=0, padx=gridPadDef[0])
    notifyTimerEntry = tk.Entry(SMSFrame, width=8, textvariable=notifyTimer, justify="center")
    notifyTimerEntryTip = ToolTipStuff.CreateToolTip(notifyTimerEntry, \
                                        "Sets how often to send a notification if the system is running ok in minutes")
    notifyTimerEntry.grid(row=1, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    errorNotifyLabel = tk.Label(SMSFrame, text="Error Notification Interval (min.)")
    errorNotifyLabel.grid(row=2, column=0, padx=gridPadDef[0])
    errorNotifyEntry = tk.Entry(SMSFrame, width=8, textvariable=errorNotify, justify="center")
    errorNotifyEntryTip = ToolTipStuff.CreateToolTip(errorNotifyEntry, \
                                        "Sets how often to notify if the system has reached an error in minutes")
    errorNotifyEntry.grid(row=2, column=1, padx=gridPadDef[0], pady=gridPadDef[1])

    emailTestButton = tk.Button(SMSFrame, bd=2, text="Test Email Protocol", pady=5,
                                width=buttonDef[2] + 5, height=buttonDef[3])
    emailTestButton.config(command=lambda: testEmail(NotifyObject))
    emailTestButton.grid(row=3, column=0, columnspan=2)
    emailTestButtonTip = ToolTipStuff.CreateToolTip(emailTestButton, \
                                       "Sends a test email to see if the email protocol actually works")

    # Check if bad number was put in
    def BadNumber(event):
        try:
            if (float(iBox.get()) < 0):
                iBox.delete(0, "end")
                iBox.insert(0, cur_def)
        except:
            print("iBox not given a number")

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
            ps_port = 'ASRL/dev/ttyUSB0::INSTR'
            channel = 8
            ps.append(powerSupplies.E3631A_PS(channel, ps_port, ps_ident))
        elif psVar.get() == "Agilent E3634A":
            ps_ident = 2
            ps_port = 'ASRL/dev/ttyUSB0::INSTR'
            channel = 5
            ps.append(powerSupplies.E3634A_PS(channel, ps_port, ps_ident))
        elif psVar.get() == "Keysight E36105B":
            ps_ident = 3
            ps_port = 'USB::10893::6146::MY59001199::INSTR'
            channel = None  # not needed for this power supply and usbtmc interface
            ps.append(powerSupplies.E36105B_PS(channel, ps_port, ps_ident))
        print(ps_ident)
        # Make label for currently used power supply
        curPS = tk.Label(voltage_frame, text="Current Power supply: " + psVar.get(), height=2, padx=labelPadXDef)
        curPS.grid(row=4, column=0, columnspan=3)

        # Draw power supply window here

        createMonitor(monitorAppObject)

    monitorAppFrame = tk.Frame()

    def createMonitor(monitorAppObject):
        try:
            monitorAppObject.append(
                monitor.monitorApp(monitorAppFrame, ps[0], NotifyObject, volt_def, cur_def, check_interval_def,
                           infuse_interval_def, infuse_rate_def, notify_interval_def, error_notify_interval_def,
                           SyringeObject, SolenoidObject, OxySensorObject,
                           oxygen_reads_def, solenoid_low_bound_def, solenoid_high_bound_def,psVar.get()))
            print("Power Supply Initialized \n\n\n")
        except:
            print("Could not create monitorApp class, shutting down")
            exit(2)

    initWindow(ps_ident)

    #...should testing of hardware be put in the monitorApp instead?

    def testVI():
        ps[0].run(float(vTargetBox.get()), float(iBox.get()))

        startTime = time.time()
        nowTime = startTime

        plt.ion()

        tPlot, aPlot, bPlot = [], [], []
        figure = plt.figure()

        ax = figure.add_subplot(111)

        line1, = ax.plot(tPlot, aPlot, '-')
        line2, = ax.plot(tPlot, bPlot, '-')

        while nowTime - startTime <= 10:
            nowTime = time.time()
            try:
                vNew, iNew = ps[0].read_V_I()
            except:
                print("ERROR: Could not read the power supply for 10 seconds continuously.")
                break

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

            line1.set_data(tPlot, aPlot)
            line2.set_data(tPlot, bPlot)

            figure.canvas.draw()
            figure.canvas.flush_events()

            figure.gca().relim()
            figure.gca().autoscale_view()

            plt.legend(['Voltage', 'Current'])
            plt.xlabel(time_axis_title)
            time.sleep(1)
        print("Power Supply Test Ended")

    def startTestSole02():
        startTime = time.time()
        nowTime = startTime

        loopCount = 0
        plt.ion()

        tPlot, aPlot = [], []
        figure = plt.figure()

        ax = figure.add_subplot(111)

        line1, = ax.plot(tPlot, aPlot, '-')
        while nowTime - startTime <= 10:
            nowTime = time.time()
            try:
                if (loopCount % 2) == 0:
                    vNew, oNew = OxySensorObject.read_O2_conc("Closed")
                if (loopCount % 2) == 1:
                    vNew,oNew = OxySensorObject.read_O2_conc("Open")

                if oNew > solenoid_high_bound_def:
                    print("O2 Higher than " + str(solenoid_high_bound_def) + ", Solenoid Closed")
                if oNew < solenoid_low_bound_def:
                    print("O2 Lower than " + str(solenoid_low_bound_def) + ", Solenoid Opened")

            except:
                print("ERROR: Could not read the 02 Sensor for 10 seconds continuously.")
                break

            toPlotTime = nowTime - startTime

            tPlot.append(toPlotTime)
            aPlot.append(oNew)

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

            line1.set_data(tPlot, aPlot)

            figure.canvas.draw()
            figure.canvas.flush_events()

            figure.gca().relim()
            figure.gca().autoscale_view()

            plt.legend(['O2%', 'Current'])
            plt.xlabel(time_axis_title)
            time.sleep(1)
            loopCount += 1
        print("Power 02 Test Ended")
        return

    def testSyringePump():
        # Tests the pump by calling all its basic functions to see if anything is going right

        try:
            SyringeObject.set_parameters(1,3,4)
        except:
            print("Syringe 'set_parameters' not working")

        # try infuse function
        try:
            SyringeObject.infuse()
        except:
            print("Syringe 'infuse' not working")

        #Time.sleep here to allow infusion to occur
        time.sleep(5)

        try:
            testVol,curRate = SyringeObject.check_rate_volume()
            print(testVol)
            print(curRate)
        except:
            print("Syringe 'check_rate_volume' not working")

        #Tries to changethe syringe volume and rate directly. Most likely will see a bug if trying to start electroplating
        #immediately after. May need to force an update monitor
        try:
            SyringeObject.set_rate_volume_directly(5,6)
        except:
            print("Syringe 'set_rate_volume_directly' not working")

        #Calling an update to monitor app in case some things ended up changing. Probably won't see a return from the
        #syringe pump
        updateMonitorApp()
        return

    def startElectroplating():
        #Update the monitiorApp one last time in case of any stray changes
        updateMonitorApp()

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
        monitorAppObject[0].startMonitor()

    def stopElectroplating():
        stopButton['state'] = tk.DISABLED
        pauseButton['state'] = tk.DISABLED

        runButton['state'] = tk.NORMAL
        
        runButton['state'] = tk.NORMAL
        vTargetBox['state'] = tk.NORMAL
        vHighBox['state'] = tk.NORMAL
        vLowBox['state'] = tk.NORMAL
        iBox['state'] = tk.NORMAL
        infuseRateEntry['state'] = tk.NORMAL
        infuseIntervalEntry['state'] = tk.NORMAL

        checkIntervalEntry['state'] = tk.NORMAL
        notifyTimerEntry['state'] = tk.NORMAL
        errorNotifyEntry['state'] = tk.NORMAL
        timesToCheckEntry['state'] = tk.NORMAL

        monitorAppObject[0].stopMonitor()

    def pauseElectroplating():
        if monitorAppObject.getPauseState() == 0:
            pauseButton.config(text="Unpause")
            monitorAppObject.pauseMonitor()
            return
        if monitorAppObject.getPauseState() == 1:
            pauseButton.config(text="Pause")
            monitorAppObject.pauseMonitor()
            return

    runButton.config(command=lambda: startElectroplating())
    stopButton.config(command=lambda: stopElectroplating())
    pauseButton.config(command=lambda: monitorAppObject[0].pauseMonitor())

    solenoidOpenButton.config(command=lambda: monitorAppObject[0].openSolenoid())
    solenoidCloseButton.config(command=lambda: monitorAppObject[0].closeSolenoid())
    sole02TestButton.config(command=lambda: startTestSole02())

    def checkInput(box,ident):
        # Pass box into function ins
        # tead of .get()
        # 2nd input for identifying the current box

        #ident: Number identity for indentifying current box

        # Attempt to convert the current input to a float value
        # If successful, we then check if the value is valid
        try:
            float(box.get())
        except:
            # If the last input was not a float value, we will revert back to the default value
            # Depending on the current box input
            print("Could not convert input to Float. Reverting to default")
            box.delete(0, "end")
            box.insert(0, str(DEFVALUES[ident]))

        #Generic Case: No number should be negative (maybe the current)
        if (float(box.get()) < 0):
            print("No Parameter can be negative. Reverting to default")
            box.delete(0, "end")
            box.insert(0, str(DEFVALUES[ident]))

        if (ident >= 0 and ident <= 2) and float(box.get()) > 25:
            print("Power Supply Voltage is max 25V due to 25V rail restrictions")
            box.delete(0, "end")
            box.insert(0, str(DEFVALUES[ident]))

        if (ident == 3) and float(box.get()) > 3:
            box.delete(0, "end")
            box.insert(0, str(DEFVALUES[ident]))

        if (ident == 6) and float(box.get()).is_integer() == False:
            print("Syringe pump number of infusions must be an integer")
            box.delete(0, "end")
            box.insert(0, str(DEFVALUES[ident]))

        if (ident == 7 or ident == 8) and float(box.get()) > 100:
            print("Solenoid bounds restricted to percentages from 0 to 100")
            box.delete(0, "end")
            box.insert(0, str(DEFVALUES[ident]))

        if (ident == 12) and float(box.get()).is_integer() == False:
            print("Number of Reads for Oxygen Calibration must be an integer")
            box.delete(0, "end")
            box.insert(0, str(DEFVALUES[ident]))

        # Update the monitor regardless of anything, need to reset to default values regardless
        updateMonitorApp()
        if ident == 12:
            SyringeObject.updateNumReads(float(box.get()))
        return

    def updateMonitorApp():
        monitorAppObject[0].setParams(float(vTargetBox.get()),
                                      float(iBox.get()),
                                      float(vHighBox.get()),
                                      float(vLowBox.get()),
                                      float(checkIntervalEntry.get()),
                                      float(infuseIntervalEntry.get()),
                                      float(infuseRateEntry.get()),
                                      float(timesToCheckEntry.get()),
                                      float(oxyNumReadsBox.get()),
                                      float(solenoidLowBox.get()),
                                      float(solenoidHighBox.get()),
                                      float(notifyTimerEntry.get()),
                                      float(errorNotifyEntry.get()),
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

    # Boxes containing number inputs need to be first checked that their inputs are floats before
    # Updating the monitorApp
    vTargetBox.bind('<FocusOut>', lambda event: checkInput(vTargetBox,0), add="+") #Add identifying string
    vLowBox.bind('<FocusOut>', lambda event: checkInput(vLowBox,1), add="+")
    vHighBox.bind('<FocusOut>', lambda event: checkInput(vHighBox,2), add="+")

    iBox.bind('<FocusOut>', lambda event: checkInput(iBox,3), add="+")

    infuseIntervalEntry.bind('<FocusOut>', lambda event: checkInput(infuseIntervalEntry,4), add="+")
    infuseRateEntry.bind('<FocusOut>', lambda event: checkInput(infuseRateEntry,5), add="+")
    timesToCheckEntry.bind('<FocusOut>', lambda event: checkInput(timesToCheckEntry,6), add="+")

    solenoidLowBox.bind('<FocusOut>', lambda event: checkInput(solenoidLowBox,7), add="+")
    solenoidHighBox.bind('<FocusOut>', lambda event: checkInput(solenoidHighBox,8), add="+")

    checkIntervalEntry.bind('<FocusOut>', lambda event: checkInput(checkIntervalEntry,9), add="+")
    notifyTimerEntry.bind('<FocusOut>', lambda event: checkInput(notifyTimerEntry,10), add="+")
    errorNotifyEntry.bind('<FocusOut>', lambda event: checkInput(errorNotifyEntry,11), add="+")

    oxyNumReadsBox.bind('<FocusOut>', lambda event: checkInput(oxyNumReadsBox,12), add="+")

    plateOption.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")
    solenoidSwitch.bind('<FocusOut>', lambda event: updateMonitorApp(), add="+")

    plateOption.bind('<Leave>', lambda event: updateMonitorApp(), add="+")
    solenoidSwitch.bind('<Leave>', lambda event: updateMonitorApp(), add="+")

    def printMonitorValues():
        monitorAppObject[0].printParams()

    printParamsButton = tk.Button(IVButtonFrame, bd=1, text="Print Parameters", padx=buttonDef[0], pady=buttonDef[1],
                                  width=buttonDef[2], height=buttonDef[3])
    printParamsButton.grid(row=2, column=1, padx=gridPadDef[0], pady=gridPadDef[1])
    printParamsButton.config(command=lambda: printMonitorValues())

    updateParamsButton = tk.Button(IVButtonFrame, bd=1, text="Update Parameters", padx=buttonDef[0], pady=buttonDef[1],
                                   width=buttonDef[2], height=buttonDef[3])
    updateParamsButton.grid(row=2, column=0, padx=gridPadDef[0], pady=gridPadDef[1])
    updateParamsButton.config(command=lambda: updateMonitorApp())
    updateParamsButtonTip = ToolTipStuff.CreateToolTip(updateParamsButton, \
                                          "Forces an update to the monitorApp's parameters, in case some bindings did not work")

    root.mainloop()


if __name__ == '__main__':
    notify_flag = 2
    use_text_only_for_bad_news = True
    menu()

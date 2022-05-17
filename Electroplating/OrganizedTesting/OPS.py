''' HARDWARE CLASSES'''
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

        # Simulation objects
        self.stateDelay = 3 #Number of times before a state can be changed
        self.curDelay = 0 #Current times has state has occured until we can change

    def switch_use_syringe_pump(self, input):
        self.use_flag = input

    def updateFactor(self, input):
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


class O2_Sensor():
    def __init__(self, numReads):

        self.lastVOxy = 5
        self.lastO2 = 0.02

        self.curDelay = 0
        self.stateDelay = 5

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

        self.startO2 = 50  # Percentage of O2 at start of simulation.

    def updateNumReads(self, numReads):
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

    def read_O2_conc(self, solenoidState):
        # Spit out fake values of oxygen depending on if the solenoid is closed or not
        # Doesn't happen in real life, but whatever

        newV_settled = self.lastVOxy

        # Update the 02 simulation as a triangle wave

        if solenoidState == "Open":
            self.curDelay += 1
            garbage = -0.8
        if solenoidState == "Closed":
            self.curDelay += 1
            garbage = 0.8

        newO2perc_settled = self.lastO2 + garbage
        print("Old O2: " + str(self.lastO2))
        print("New O2: " + str(newO2perc_settled))
        print("\n\n")
        self.lastO2 = newO2perc_settled

        # newV_settled = 0
        # newO2perc_settled = 0
        # for ii in range(self.numReads):
        #     newV = self.chan.voltage
        #     new_O2_perc_value = newV * self.conversion_factor
        #
        #     newV_settled += newV
        #     newO2perc_settled += new_O2_perc_value
        #     time.sleep(0.01)
        #
        # # gets average
        # newV_settled = newV_settled / self.numReads
        # newO2perc_settled = newO2perc_settled / self.numReads

        return newV_settled, newO2perc_settled

class Solenoid_Controller():
    def __init__(self):
        ## initial setup
        self.control_pin = 37
        self.status = 0  # 0 is closed, 1 is open

        # set the board pin number address scheme. We want to use pin 37 for signal. The ground is plugged into pin 39 (doesn't need to be controlled, obviously)
        #GPIO.setmode(GPIO.BOARD)

        # set up pin 37 as output
        #GPIO.setup(self.control_pin, GPIO.OUT)

    def open_solenoid(self):
        # Let out oxygen
        #GPIO.output(self.control_pin, GPIO.HIGH)
        self.status = 1

        # Tell the monitor loop to send
        return

    def close_solenoid(self):
        # Let in oxygen
        #GPIO.output(self.control_pin, GPIO.LOW)
        self.status = 0

    def cleanup(self):
        if self.status == 1:  # if its open, shut it before continuing
            self.close_solenoid()

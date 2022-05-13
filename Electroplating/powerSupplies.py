# Module usbtmc currently not working.
#import usbtmc

# For simulation
import random

class E3631A_PS():
    def __init__(self, channel, ps_port, ps_ident):

        # save identification
        self.ident = ps_ident

        # open up Resource Manager
        # rm = pyvisa.ResourceManager('@py')

        # open up the right channel
        # the USB resource needs to be figured out beforehand, there is no way to figure out which power supply is

        self.startI = -8
        self.startV = -8

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

        # if self.ps is not None:

        self.startI = I
        self.startV = V

        self.lastI = self.startI
        self.lastV = self.startV

        # take output off, set new voltage and current, then turn output back on
        # ps.write('OUTPUT OFF')
        # self.ps.write('APPL P6V, %f, %f' % (V, I))
        #
        # # check if output is already on
        # self.ps.write('OUTPUT?')/
        # self.ps.write('++read')
        # on_flag = self.ps.read().strip()
        #
        # if on_flag == '0':
        #     self.ps.write('OUTPUT ON')

        print('Started power supply output.')

    # else:
    #     print('Cannot run power supply; power supply did not initialize properly.')

    def read_V_I(self):

        # if self.ps is not None:
        V_vary = random.uniform(-0.05, 0.05)
        I_vary = random.uniform(-1, 1)

        # # query power supply for voltage
        # self.ps.write('MEAS:VOLT? P6V')
        # self.ps.write('++read')
        # voltage = float(self.ps.read().strip())
        #
        # # query power supply for current
        # self.ps.write('MEAS:CURR? P6V')
        # self.ps.write('++read')
        # current = float(self.ps.read().strip())

        voltage = self.lastV + V_vary
        current = self.lastI + I_vary

        self.lastV = voltage
        self.lastI = current

        # else:
        #     print('Cannot measure voltage/current; power supply did not initialize properly.')
        #     voltage = 1
        #     current = 1

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

class E36233A_PS():

    ## IMPLEMENTATION NOTES:
    # to get this working on Windows I had to install the proper driver for the Keysight power supply
    # what ended up working was downloading Zadig (https://zadig.akeo.ie/)
    # and installing the libusbK (v3.1.0.0) driver
    # the reason you need to install the driver is that it is not a HID device, so the computer has no idea how to communicate with it. linux might be different.
    # nothing is needed on Linux, it is handled correctly "out of the box".

    def __init__(self, channel, ps_port, ps_ident):
        """
        Purpose: initialize the power supply class

        Inputs:
        channel - not needed for USBTMC implementation, only for PyVISA. Pass None or whatever you want, this value is not used at all.
        ps_port - not needed, just pass None.
        ps_ident - 1 or 2. Identifies which E36233A you are using.

        Returns:
        class object
        """

        # save identification
        self.ident = ps_ident

        if ps_ident == 1:
            idn = 'USB::10893::13058::MY61001504::INSTR'
        elif ps_ident == 2:
            idn = 'USB::10893::13058::MY61001514::INSTR'
        else:
            print('ps_ident not a valid number, should be 1 or 2.')
            idn = -1

        print(idn)

        # open up Resource Manager
        # rm = pyvisa.ResourceManager('@py')

        # open up the right channel
        # the USB resource needs to be figured out beforehand, there is no way to figure out which power supply is
        try:
            self.ps = usbtmc.Instrument(idn)

            # not sure why this is suddenly necessary but without it there are errors about the device not working.
            try:
                self.ps.read()
            except:
                pass

            # clear errors
            self.ps.write('*CLS\n')
            time.sleep(0.01)

            # try to get a response from power supply, in this case its identity
            idn = self.ps.ask('*IDN?\n')
            print('Power supply identity: %s , %s' % (ps_port, idn))



        except Exception as e:
            print('Something went wrong with power supply initialization:')
            print(e)
            self.ps = None

    def _gen_channels(self, channels):
        try:
            len(channels)  # if it has a length, then we should be good
        except:
            channels = [
                channels]  # if not, then someone only passed an integer and it needs to be repackaged into a list

        return channels

    def run(self, V, I, channels=[1]):

        # does some error checking on the channels
        channels = self._gen_channels(channels)

        if self.ps is not None:
            # take output off, set new voltage and current, then turn output back on
            # ps.write('OUTPUT OFF\n')

            for channel in channels:
                self.ps.write('INST:NSEL %d\n' % channel)
                self.ps.write('APPL %f, %f\n' % (V, I))

                # turn on the output
                self.ps.write('OUTPUT ON\n')
                print('Started power supply output %d.' % channel)  # %channel[0])
        else:
            print('Cannot run power supply; power supply did not initialize properly during program start.')

    def read_V_I(self, channels=[1, 2]):

        # does some error checking on the channels
        channels = self._gen_channels(channels)

        if self.ps is not None:

            res = {1: [], 2: []}
            for channel in channels:
                self.ps.write('INST:NSEL %d\n' % channel)

                # query power supply for voltage
                measV = self.ps.ask('MEASURE:VOLTAGE?')  # %s\n'%channel[1])
                voltage = float(measV)

                # query power supply for current
                measI = self.ps.ask('MEASURE:CURRENT?')  # %s\n'%channel[1])
                current = float(measI)

                # store to dict
                # res[channel[0]]=[voltage,current]
                res[channel] = [voltage, current]

        else:
            print('Cannot measure voltage/current; power supply did not initialize properly.')
            voltage = -1
            current = -1

        return res

    def stop(self, channels=[1, 2]):

        # does some error checking on the channels
        channels = self._gen_channels(channels)

        if self.ps is not None:
            for channel in channels:
                self.ps.write('INST:NSEL %d\n' % channel)
                self.ps.write('OUTPUT OFF\n')
                print('Power supply %d is turned off.' % channel)
        else:
            print('Power supply did not initialize properly, so it cannot be turned off if on.')

    def disconnect(self):
        if self.ps is not None:
            self.stop()
            self.ps.close()
            print('Power supply has been disconnected.')
        else:
            print('Power supply was not initialized properly, but hopefully is disconnected anyway.')

    def selftest(self, flag=False):
        if flag: import winsound

        if flag: winsound.Beep(440, 500)
        input('put the test resistor on the terminals')
        print('watch the power supply, see if the voltage or current reaches the specified levels')

        v = 1;
        i = 0.1
        self.run(v, i, [1])
        print('Desired V, I: %f , %f' % (v, i))

        time.sleep(3)

        if flag: winsound.Beep(440, 500)
        res = self.read_V_I();
        print('Actual V, I: ', res)
        self.stop(1)
        time.sleep(3)

        v = 1;
        i = 0.1
        self.run(v, i, [2])
        print('Desired V, I: %f , %f' % (v, i))

        time.sleep(3)

        if flag: winsound.Beep(440, 500)
        res = self.read_V_I();
        print('Actual V, I: ', res)
        time.sleep(3)

        if flag: winsound.Beep(440, 500)
        nv = 2
        ni = 0.5
        self.run(nv, ni, [1, 2])
        print('Desired V, I: %f , %f' % (nv, ni))
        time.sleep(3)

        if flag: winsound.Beep(440, 500)
        res = self.read_V_I();
        print('Actual V, I: ', res)
        time.sleep(3)

        if flag: winsound.Beep(440, 500)
        ps.stop()
        print('output stopped')
        time.sleep(3)

        if flag: winsound.Beep(440, 500)
        v = 10;
        i = 1
        self.run(v, i, [1, 2])
        print('Desired V, I: %f , %f' % (v, i))
        time.sleep(3)

        if flag: winsound.Beep(440, 500)
        res = self.read_V_I();
        print('Actual V, I: ', res)
        self.stop()
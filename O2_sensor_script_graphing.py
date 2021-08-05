import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import matplotlib.pyplot as plt
import numpy as np

class O2_Sensor():
    def __init__(self,numReads):
        
        ### setup the adc to read the O2 sensor
        # create the I2C bus
        i2c = busio.I2C(board.SCL,board.SDA)

        # create the adc object using the I2C bus
        ads = ADS.ADS1115(i2c)

        # set the gain (2/3,1,2,4,8,16); probably doesn't do anything since we use the voltage reading directly 
        ads.gain = 1

        # create differential input chetween channel 0 and 1. No need to set the gain, we will use the voltage directly.
        self.chan = AnalogIn(ads,ADS.P0,ADS.P1)
        
        # put default values for calibration here
        self.o2_percent = 20.9 # percentage of O2 in plating lab; since we are close to sea level, I use 20.9
        self.o2_b = 0     # [V] "base" value that the O2 sensor outputs in 0% O2
        self.o2_a    = 0.011 # [V] "atmospheric" value, that the O2 sensor outputs in normal air, which is 20.9% O2 at sea level
        
        # calculate conversion factor
        self.conversion_factor = 0
        self._calculate_conversion_factor() # assigns value directly to self.conversion_factor
        
        # number of reads to do during calibration
        self.numReads = numReads
        
    def _calculate_conversion_factor(self):
        # conversion factor to convert volts to O2 concentration
        print('old conversion factor: %.6f [percent/V]'%(self.conversion_factor))
        self.conversion_factor = self.o2_percent/(self.o2_a-self.o2_b) # divide by 1000 to convert o2_a/b from [mV] to [V]
        print('new conversion factor: %.6f [percent/V]'%(self.conversion_factor))

    def calibrate(self):
        
        # take ten measurements in normal atmostphere, average, and assign value of 20.9% O2
        print('old value of o2_a: %.6f [V]'%(self.o2_a))
        o2_a = 0
        for ii in range(self.numReads):
            o2_a += self.chan.voltage
            
        self.o2_a = o2_a/self.numReads # get new averaged o2_a value

        print('new value of o2_a: %.6f [V]'%(self.o2_a))
        self._calculate_conversion_factor() # calculate new conversion factor
        
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
        newV_settled = newV_settled/self.numReads
        newO2perc_settled = newO2perc_settled/self.numReads        

        return newV_settled , newO2perc_settled
        
if __name__ == '__main__':
    
    # number of reads
    numReads = 50
    
    # initialize O2 sensor class; this sets up the interface and sets up default calibration
    O2sensor = O2_Sensor(numReads)
    
    # pause for a second to let sensor settle
    time.sleep(1)
    
    # do the calibration
    O2sensor.calibrate()
        
    # print header to terminal    
    print("{:>5}\t{:>5}".format('voltage [mV]','O2 [%]'))

    # continuously read out O2 percentage to terminal. Use cntrol+C to break of out loop
    begtime = time.time()
    timeL = np.array([])
    O2sensL = np.array([])
    fig, ax = plt.subplots()
    while True:
        newV,newO2perc = O2sensor.read_O2_conc()
        print("{:>5.3f}\t{:>5.2f}".format(newV*1000,newO2perc))
        
        timeL = np.append(timeL, time.time() - begtime )
        O2sensL = np.append(O2sensL,newO2perc)
        
        ax.clear()
        ax.plot(timeL,O2sensL,'o')
        ax.set_xlabel('Time [s]')
        ax.set_ylabel('O2 concentration [perc]')
        ax.set_title('O2 concentration [perc], last concentration: %.2f [perc]'%newO2perc)
        
        # plot value above each point
        #for i,v in enumerate(O2sensL):
        #    ax.annotate('%.2f'%v,xy=(timeL[i],v),xytext=(-7,7),textcoords='offset points')
        
        plt.pause(0.0001)
        time.sleep(10)
        
    plt.show()
    


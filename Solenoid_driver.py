import RPi.GPIO as GPIO
import time

class Solenoid_Controller():
    def __init__(self):
        
        ## initial setup
        self.control_pin = 37
        self.status = 0 # 0 is closed, 1 is open
        
        # set the board pin number address scheme. We want to use pin 37 for signal. The ground is plugged into pin 39 (doesn't need to be controlled, obviously)
        GPIO.setmode(GPIO.BOARD)

        # set up pin 37 as output
        GPIO.setup(self.control_pin,GPIO.OUT)
        
    def open_solenoid(self):
        GPIO.output(self.control_pin,GPIO.HIGH)
        self.status = 1
    
    def close_solenoid(self):
        GPIO.output(self.control_pin,GPIO.LOW)
        self.status = 0
        
    def cleanup(self):
        if self.status == 1: # if its open, shut it before continuing
            self.close_solenoid()
        GPIO.cleanup()
        
####################
if __name__ == '__main__':
    
    # initialize solenoid control class
    sol_control = Solenoid_Controller()

    # test loop
    for ii in range(2):
        time.sleep(1)

        # open solenoid
        sol_control.open_solenoid()
        
        time.sleep(1)

        # close solenoid
        sol_control.close_solenoid()
        
    time.sleep(1)
    sol_control.cleanup()



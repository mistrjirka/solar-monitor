
import machine
import utime
import json

voltage_divider_calib = 10.1/1
voltage_offset_calib = 0.14
conversion_factor = 3.3 / 65535
current_pin = machine.ADC(26)
voltage_pin = machine.ADC(27) 

offset_current_calib = 1.664124
current_divider_calib = 0.045  #volts per amper
time_wait_ms = 2
number_of_measurements = 486

def get_current_measurment(wait_time, nom, offset_current, current_divider):
    current_vals = []
    result = 0
    for i in range(0,nom):
        current_raw = current_pin.read_u16()
        current_vals.append(((current_raw * conversion_factor) - offset_current) / current_divider)
        utime.sleep_ms(wait_time)
    for curr in current_vals:
        result += curr
    result = result/len(current_vals)
    return round(result,5)

def get_voltage_measurment(wait_time, nom, voltage_divider):
    volt_vals = []
    result = 0
    for i in range(0,nom):
        voltage_raw = voltage_pin.read_u16()
        volt_vals.append(voltage_raw * conversion_factor * voltage_divider - voltage_offset_calib)
        utime.sleep_ms(wait_time)
    for volt in volt_vals:
        result += volt
    result = result/len(volt_vals)
    return round(result,5)
while True:
    start_time = utime.ticks_ms()
    voltage = get_voltage_measurment(time_wait_ms, number_of_measurements, voltage_divider_calib) 
    current = get_current_measurment(time_wait_ms, number_of_measurements, offset_current_calib, current_divider_calib)
    end_time = utime.ticks_ms()
    time = (end_time - start_time)/1000
    power = round(voltage*current,2)
    work = round((power*time),2)
    
    
    InfoObject = {
        "current": current,
        "voltage": voltage,
        "power": power,
        "work": work
    }
    print(json.dumps(InfoObject))
    
 

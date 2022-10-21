import _thread
from flask import Flask, json, jsonify, request, cli
from datetime import datetime, timezone, timedelta
from dateutil import parser
import serial
import json
import os
from time import sleep
from numpy import polyval, array_split
import numpy
from flask_cors import CORS
import gc
import logging
cli.show_server_banner = lambda *_: None
#log = logging.getLogger('werkzeug')
#log.setLevel(logging.ERROR)

portLocation = "/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_e66098f29b1d8739-if00"
serialPort = serial.Serial(port=portLocation, baudrate=115200,
                           bytesize=8, timeout=2, stopbits=serial.STOPBITS_ONE)

file_name = "/home/jirka/programovani/PanelRestAPI/log.json"
file_data_loaded = False
turnoff_voltage = 11.3
total_work = 0
sleeptime = 0.200
recalculate_SOC = False
log_data_object = {
    "current": 0,
    "work": 0,
    "power": 0,
    "voltage": 0,
    "timestamp": 0,
    "total_work": total_work,
}

current_data_object = {
    "current": 0,
    "work": 0,
    "power": 0,
    "voltage": 0,
    "timestamp": 0,
    "battery_SOC": 0,
    "total_work": total_work,
}

def calc_battery_SOC(battery_voltage, battery_charging):
    x = battery_voltage
    if not battery_charging:
        x += 0.00  
    else:
        x += -0.5
    level = 0
    if x > 12.8:
        return 100
    degrees = [0.0003435435096334664, -0.014861166679057156, 0.19505133591742307, -0.40799972301434473, 1.0257658100749545, -172.33916028652908, 219.4019089616911, 30315.654581694685, -274666.6760049927, 716495.4907487794]
    result = polyval(degrees, x)
    if result > 100:
        return 100
    if result < 0:
        return 0
    return result

def get_serial_data():
    global current_data_object
    global total_work
    global file_data_loaded
    batch_size = 150
    batch_index = 0
    work_per_batch = 0

    while 1:
        # Wait until there is data waiting in the serial buffer
        sleep(sleeptime)
        if(serialPort.in_waiting > 0):

            # Read data out of the buffer until a carraige return / new line is found
            serialString = serialPort.readline()

            # #print the contents of the serial data
            timestamp = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            current_data_object = {}
            current_data_object = json.loads(serialString.decode('Ascii')) | {
                "timestamp": timestamp,
                "total_work": total_work,

            }
            current_data_object["battery_SOC"] = calc_battery_SOC(current_data_object["voltage"], current_data_object["current"] > 0.5)
            if current_data_object["current"] < 0.161:
                current_data_object["current"] = 0
                current_data_object["work"] = 0
                current_data_object["power"] = 0
            if current_data_object["current"] > 0.065 or current_data_object["voltage"] > 11:
                    
                #print(batch_index)
                if batch_index < batch_size:
                    log_data_object["current"] += current_data_object["current"]
                    log_data_object["voltage"] += current_data_object["voltage"]
                    log_data_object["work"] += current_data_object["work"]
                    log_data_object["power"] += current_data_object["power"]
                    #print( current_data_object["power"])
                    log_data_object["total_work"] = current_data_object["total_work"]
                    batch_index += 1 
                else:
                    batch_index = 0
                    #print(log_data_object["work"])
                    log_data_object["current"] = round(log_data_object["current"] / batch_size, 2)
                    log_data_object["voltage"] = round(log_data_object["voltage"] / batch_size, 2)
                    log_data_object["battery_SOC"] = calc_battery_SOC(log_data_object["voltage"], log_data_object["current"] > 0.5)
                    if log_data_object["voltage"] <  turnoff_voltage:
                        f = open("preventiveshutdowns.txt", "a")
                        f.write(timestamp + " \n")
                        f.close()
                        os.system("shutdown /s /t 1")
                    
                    log_data_object["work"] = (round(log_data_object["work"], 4))
                    log_data_object["power"] = round(log_data_object["power"] / batch_size, 2)
                    log_data_object["timestamp"] = timestamp
                    
                    try:
                        file_object = open(file_name, 'r+')
                    except:
                        file_object = open(file_name, 'w+')
                    
                    contents = file_object.read()
                    
                    object_content = False
                    if len(contents) > 5:
                        try:
                            object_content = json.loads(contents)
                            file_object_bac = open(file_name + ".bac", 'w')
                            file_object_bac.write(contents)
                            file_object_bac.close()
                        except:
                            file_object_bac = open(file_name + ".bac", 'r')
                            object_content = json.loads(file_object_bac.read())
                            file_object.write(file_object_bac.read())
                            file_object_bac.close()        
                    file_object.close()                
                    file_object = open(file_name, 'w')        
                    if isinstance(object_content, list):
                        object_content.append(log_data_object)
                    else:
                        object_content = []
                        object_content.append(log_data_object)
                    file_object.write(json.dumps(object_content))
                    
                    file_object.close()
                    log_data_object["current"] = 0
                    log_data_object["voltage"] = 0
                    log_data_object["power"] = 0
                    log_data_object["work"] = 0
            """ operations that use previous data """
            if not file_data_loaded:
                #print("file data not loaded")
                object_content = []
                contents = ""
                try:
                    file_object = open(file_name, 'r+')
                    contents = file_object.read()
                    
                    object_content = json.loads(contents)
                    file_object.close()
                    
                except:
                    try:
                        file_object = open(file_name, 'w+')
                        file_object_bac = open(file_name + ".bac", 'r')
                        file_object.write(file_object_bac.read())
                        contents = file_object_bac.read()
                        json.loads(contents)
                        
                        #print("corrupted")
                        
                        object_content = json.loads(contents)
                        file_object.close()
                        file_object_bac.close()
                    except:
                        file_object = open(file_name, 'r')
                        contents = file_object.read()[:-1] + "]"
                        file_object.close()                       
                        object_content = json.loads(contents)
                        file_object = open(file_name, 'w')
                        file_object.write(contents)
                        file_object.close()
                        file_object_bac = open(file_name + ".bac", 'w')
                        file_object_bac.write(contents)
                        file_object_bac.close()      
                            
                if isinstance(object_content, list):
                    total_work += object_content[-1]["total_work"]
                else:
                    object_content = []
                if recalculate_SOC:
                    print("Calculating")
                    for reading in object_content:
                        reading["battery_SOC"] = calc_battery_SOC(reading["voltage"], reading["current"] > 1.5)
                    contents = json.dumps(object_content)
                    file_object = open(file_name, 'w')
                    file_object.write(contents)
                    file_object.close()
                file_data_loaded = True
            else:
                total_work += current_data_object["work"] / 3600/1000 # to convert to KWh


def server():
    global current_data_object
    api = Flask(__name__)
    CORS(api)
    @api.route('/currentdata', methods=['GET' , "POST"])
    def get_current_data():
        global current_data_object

        data = current_data_object 
        response = jsonify(data)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response


    @api.route('/graphtoday', methods=['GET', "POST"])
    def graphtoday():
        #try:
        start = request.json.get('start')
        end = request.json.get('end')
        
        #print(start)
        #print(end)
        

        file_object = open(file_name, 'r+')
        contents = file_object.read()
        object_content = False
        if len(contents) > 5 and (start == "" or end == ""):
            #print("reading")
            object_content = json.loads(contents)[-800:] # reversing array
        elif(len(contents) > 5):
            try:
                date_start = datetime.strptime(start, "%H:%M:%S %d. %m. %Y")
            except:
                datetime.now() - timedelta(1)
            try:
                date_end = datetime.strptime(end, "%H:%M:%S %d. %m. %Y")
            except:
                if date_start.date() == datetime.today().date():
                    date_end = datetime.now()
                else:
                    date_end = date_start + timedelta(1)
            date_start = date_start.replace(tzinfo=None)
            date_end = date_end.replace(tzinfo=None)
            today = False
            if date_end.date() == datetime.today().date():
                #print("same date")
                date_end = datetime.now()
                today = True
            object_content = numpy.array(json.loads(contents))
            index = 0
            index_start_set = False
            index_end_set = False
            index_start = 0
            index_end = 0

            step = 50
            print("object_content {}", len(object_content))
            split_arrays = array_split(numpy.flip(object_content[::step]),4)
            for mes_array in split_arrays:
                for meassurment in mes_array:
                    try:
                        mes_date = datetime.strptime(meassurment["timestamp"], "%m/%d/%Y, %H:%M:%S")
                    except:
                        #print("very old data skipping")
                        index += step
                        continue
                    if date_start > mes_date and index_start_set is False:
                        index_start_set = True
                        index_start = index
                        print(date_start, " a ", mes_date)
                        print("start set ", index)
                        if(today):
                            index_end = 0
                        break
                    if date_end > mes_date and index_end_set is False:
                        index_end_set = True
                        index_end = index
                        print(date_end, " a ", mes_date)
                        print("end set " , index)
                        #break 
                    index += step

            #print(index_start, " ", index_end)
            #print(object_content[index_start])
            index_start = len(object_content) - index_start -1
            index_end = len(object_content) - index_end - 1
            print(index_start, " ", index_end)
            print(object_content[index_start])
            object_content = object_content[index_start:index_end]
            print(len(object_content))
            #print(object_content[0])

        
        if isinstance(object_content, numpy.ndarray):
            tmp_graph_dataset = {
                "labels": [],
                "datasets": [
                    {
                        "label": "Current (A)",
                        "data": [],
                        "borderColor": "#ff6384",
                        "backgroundColor": "#ff6384"
                    },
                    {
                        "label": "Voltage (V)",
                        "data": [],
                        "borderColor": "#d9d9d9",
                        "backgroundColor": "#d9d9d9"
                    },
                    {
                        "label": "Power (Watts)",
                        "data": [],
                        "borderColor": "#b20093",
                        "backgroundColor": "#b20093"
                    },
                    {
                        "label": "Work total (Killowatt hours)",
                        "data": [],
                        "borderColor": "#56c222",
                        "backgroundColor": "#56c222"
                    },
                    {
                        "label": "battery SOC (%)",
                        "data": [],
                        "borderColor": "#ea7600",
                        "backgroundColor": "#ea7600"
                    }
                    
                ]
            }

            for datapoint in object_content:
                label = datapoint["timestamp"]
                tmp_graph_dataset["labels"].append(label)

                current = datapoint["current"]
                tmp_graph_dataset["datasets"][0]["data"].append(current)

                voltage = datapoint["voltage"]
                tmp_graph_dataset["datasets"][1]["data"].append(voltage)

                power = datapoint["power"]
                tmp_graph_dataset["datasets"][2]["data"].append(power)

                work = datapoint["work"]
                work_total = datapoint["total_work"]
                tmp_graph_dataset["datasets"][3]["data"].append(work_total)

                battery_soc = 0
                if "battery_SOC" in datapoint:
                    battery_soc = datapoint["battery_SOC"]
                tmp_graph_dataset["datasets"][4]["data"].append(battery_soc)
            response = jsonify(tmp_graph_dataset)
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response


        else:
            response = jsonify([])
            response.headers.add('Access-Control-Allow-Origin', '*')
            del object_content
            gc.collect()
            return response
        #except:
        #    response = jsonify([])
        #    del object_content
        #    gc.collect()
        #    response.headers.add('Access-Control-Allow-Origin', '*')
        #    
        #    return response

    api.run(host='0.0.0.0') 

if __name__ == '__main__':
    _thread.start_new_thread (get_serial_data,())
    _thread.start_new_thread (server,())

    while 1:
        pass

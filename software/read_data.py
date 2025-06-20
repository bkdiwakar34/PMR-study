import serial
import struct
from threading import Thread
import csv
import numpy as np
import math
import json
import asyncio
from bleak import BleakClient, BleakScanner
import pandas as pd
from datetime import datetime
import os

class MyJSONEncoder(json.JSONEncoder):         
    def default(self, o):
        try:
            return o.tolist() 
        except AttributeError:
            pass
        return json.JSONEncoder.default(self, o)


class ble_read(object):
    def __init__(self):
        self.c=0
        self.sw=0
        self.w=[]
        self.y=[]
        self.q=[]
        self.s=0
        self.g_ofst=1
        self.offset = []
        self.angle_acc =[]
        self.q_int = [1, 0, 0, 0]
        self.calibrate = 0
        self.reset = 0
        self._var_gyro_offst = 2.0
        self.prev_time = 0
        self.arr_comp_rom = []
        self.subject_name = []
        self.joint = []
        self.movement = []
    async def run(self,address, char_uuid):
        def notification_handler(sender,data):
            self.y=list(struct.unpack('3h', data[:6]))
            self.time1 = list(struct.unpack('L', data[6:]))
            self.time = self.time1[0]
            self.y.extend([self.time])
            data = self.y
            if self.calibrate == 1:
                self.offset.append(np.array(self.y[:3])/65.5)
                if len(self.offset) == 500:
                    gyro_offset = np.mean(self.offset, axis=0)
                    offset = {'gyro_off':gyro_offset}
                    with open(r'software\export.json', 'w') as f:
                        json.dump(offset, f, separators=(',', ':'), sort_keys=True, indent=4, cls=MyJSONEncoder)
                    self.offset = []
                    self.calibrate = 0
                    if np.max(gyro_offset)>5:
                        self.offset = []
                        self.calibrate = 1
            if self.reset == 1:
                self.offset.append(np.array(self.y[:3])/65.5)
                if len(self.offset) == 500:
                    self.gyro_offset = np.mean(self.offset, axis=0)
                    self._var_gyro_offst = np.max(np.var(self.offset[:500],axis = 0))
                    self.reset ==0
            
            with open(r'software\export.json', "r") as f:
                off = json.load(f, object_pairs_hook=lambda x: dict((k, np.array(v)) for k, v in x))
            if self._var_gyro_offst < 1.0:
                final_gyro_off = self.gyro_offset
                
            else:
                final_gyro_off = off['gyro_off']
                
            ang = self.rom(self.y,final_gyro_off,self.time)
            data.extend([ang])
            self.angle_acc = np.append(self.angle_acc, ang)
            if len(self.angle_acc)>4000:
                self.angle_acc = self.angle_acc[1:]
            if self.sw:
                self.arr_comp_rom.append(ang)
                self.writer.writerow(data)

        async with BleakClient(address) as client:
            if not await client.is_connected():
                print(f"Failed to connect to {address}")
                return
            
            print(f"Connected to {address}")

            # Start receiving notifications from the characteristic
            await client.start_notify(char_uuid, notification_handler)

            # Keep the script running to continue receiving notifications
            print("Listening for notifications...")
            await asyncio.sleep(500)  # Adjust the duration as needed

            # Stop notifications when done
            await client.stop_notify(char_uuid)


    async def main(self):
        
        # address = "13:C8:F4:32:5A:CC"  # Your device's MAC address
        address = "A9:42:49:0E:65:80"  # Your device's MAC address
        # address = "60:2B:A8:76:25:47"  # Your device's MAC address
        
        char_uuid = "660c4a6f-16d8-4e57-8fdb-a4058934242d"  # Characteristic UUID
        

        await self.run(address, char_uuid)
    
    def kill_switch(self, sw,path3):
        if sw:
            header = ['Pateint_ID', 'Date_Time', 'ROM']
            
            header=['gx','gy','gz','time','ang']           
            self.f=open(path3, 'w',newline='')
            self.writer = csv.writer(self.f)
            self.writer.writerow(header)
            self.sw = 1
        if not sw:
            self.sw = 0
            self.f.close()
            # Log summary
            self.log_global_max_rom(
                                        subject_id=self.subject_name,
                                        joint=self.joint,
                                        movement=self.movement,
                                        max_rom= np.max(self.arr_comp_rom) # Replace with actual value
                                    )
            self.arr_comp_rom = []
    def quaternion_multiply(self, quaternion1, quaternion0):
        w0, x0, y0, z0 = quaternion0
        w1, x1, y1, z1 = quaternion1
        return np.array([-x1 * x0 - y1 * y0 - z1 * z0 + w1 * w0,
                        x1 * w0 + y1 * z0 - z1 * y0 + w1 * x0,
                        -x1 * z0 + y1 * w0 + z1 * x0 + w1 * y0,
                        x1 * y0 - y1 * x0 + z1 * w0 + w1 * z0], dtype=np.float64)
    
    def rom(self,data,off,time):
        gyro = data[:3]
        if self.prev_time == 0:
            del_t = 1
        else:
            del_t = (self.time- self.prev_time)/1000000
        self.prev_time = self.time
        gyro = (np.array(gyro).astype(float)/65.5)-off 
        gyro = np.deg2rad(gyro)
        if np.linalg.norm(gyro) !=0 :
                aor = gyro/ np.linalg.norm(gyro)
        else:
                aor = gyro
        delta_theta = np.linalg.norm(gyro)*del_t
        temp_var = math.sin(delta_theta/2)
        q_gyro = [math.cos(delta_theta/2), aor[0]*temp_var, aor[1]*temp_var, aor[2]*temp_var]
        self.q_int = self.quaternion_multiply(q_gyro,self.q_int)
        q_int_norm = self.q_int/np.linalg.norm(self.q_int)
        gyro_ang = np.rad2deg(2*np.arccos(q_int_norm[0]))
        return gyro_ang
   
    def log_global_max_rom(self, subject_id, joint, movement, max_rom):
        global_summary_path = os.path.join("data", "global_summary.csv")
        
        # Prepare row data
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = {
            "Subject_ID": subject_id,
            "Date_Time": current_time,
            "Joint": joint,
            "Movement": movement,
            "Max_ROM": max_rom
        }

        # Check if file exists and write accordingly
        if not os.path.exists(global_summary_path):
            df = pd.DataFrame([row])
            df.to_csv(global_summary_path, index=False)
        else:
            df = pd.DataFrame([row])
            df.to_csv(global_summary_path, mode='a', header=False, index=False)
            
    def thread_run(self):
        asyncio.run(self.main())
                
    def connect1(self):
        self.show=Thread(target=self.thread_run,args=())
        self.show.start()




import os
import sys
from PyQt5.uic import loadUi
from PyQt5 import QtWidgets
import time
from read_data  import ble_read
from PyQt5.QtWidgets import *
from threading import Thread
from PyQt5.QtCore import QObject, pyqtSignal
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt
import pandas as pd
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QMessageBox
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import QDialog, QVBoxLayout


class SignalCommunicate(QObject):
    request_graph_update = pyqtSignal()
    invoke=pyqtSignal(int)

class StatsDialog(QDialog):
    def __init__(self, df, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Longitudinal ROM Plots")
        layout = QVBoxLayout(self)

        fig, axes = plt.subplots(nrows=len(df["Subject_ID"].unique()), figsize=(8, 4 * len(df["Subject_ID"].unique())))
        if len(df["Subject_ID"].unique()) == 1:
            axes = [axes]  # Ensure axes is iterable

        for ax, (subject, group) in zip(axes, df.groupby("Subject_ID")):
            for (joint, movement), sub_group in group.groupby(["Joint", "Movement"]):
                sub_group = sub_group.sort_values("Date_Time")
                ax.plot(sub_group["Date_Time"], sub_group["Max_ROM"], marker='o', label=f"{joint}-{movement}")
            ax.set_title(f"Subject: {subject}")
            ax.set_xlabel("Date")
            ax.set_ylabel("Max ROM")
            ax.legend()
            ax.grid(True)

        fig.tight_layout()
        canvas = FigureCanvas(fig)
        layout.addWidget(canvas)

class WelcomeScreen(QMainWindow):
    def __init__(self):
        super(WelcomeScreen, self).__init__()
        # Load UI and set up scaling
        loadUi(r"software\ui_file.ui", self)
        
        self.pushbuttonstart.clicked.connect(self.start_assess)
        self.pushbuttonstop.clicked.connect(self.stop_assess)
        self.pushbuttoncalibrate.clicked.connect(self.calibrate_gyro)
        self.pushbuttonstats.clicked.connect(self.show_stats)
        self.plot_now = 1
        self.display = 1
        self.obj = pg.PlotWidget()
        self.obj.setBackground('#FFFFFF')
        self.obj.setTitle("Range of Motion", color="#6497b1", size="20pt")
        styles = {'color':'#6497b1', 'font-size':'20px'}
        self.obj.setLabel('left', 'angle (deg)', **styles)
        self.obj.setLabel('bottom', 'time (sec)', **styles)
        layout =QGridLayout()
        layout.addWidget(self.obj)  
        self.pen = pg.mkPen(color=(194,124,64),width=2)
        self.graphicsView.setLayout(layout)
        self.obj.setYRange(0, 180) 
        self.a = ble_read()
        self.a.s=1
        self.a.connect1()
        self.signalComm = SignalCommunicate()
        self.signalComm.request_graph_update.connect(self.update_plot_data)
        self.show_new_window()
        self.start_disp = 0
        self.hosp_num = self.lineedithospitalnumber.text()
        self.joint = self.comboBoxjoint.currentText()
        self.movement = self.comboBoxmovement.currentText()
        self.comboBoxjoint.activated.connect(self.updatemovement)
    

    def updatemovement(self):
        if self.comboBoxjoint.currentText() == 'Neck':
            self.comboBoxmovement.clear()
            self.comboBoxmovement.addItems([' ','Flexion', 'Extension', 'Right Lateral Flexion', 'Left Lateral Flexion','Right Rotation','Left Rotation'])
        elif self.comboBoxjoint.currentText() == 'Shoulder':
            self.comboBoxmovement.clear()
            self.comboBoxmovement.addItems([' ','Flexion_Extension', 'Abduction_lAdduction', 'External Rotation','Internal Rotation'])
        elif self.comboBoxjoint.currentText() == 'Knee':
            self.comboBoxmovement.clear()
            self.comboBoxmovement.addItems([' ','Flexion','Extension'])
        elif self.comboBoxjoint.currentText() == 'Hip':
            self.comboBoxmovement.clear()
            self.comboBoxmovement.addItems([' ','Flexion', 'Extension'])
        elif self.comboBoxjoint.currentText() == 'Ankle':
            self.comboBoxmovement.clear()
            self.comboBoxmovement.addItems([' ','Flexion', 'Extension'])

    def progressBarValue(self, value):
        styleSheet = """
        QFrame{
            border-radius:150px;
            background-color: qconicalgradient(cx:0.5, cy:0.5, angle:90, stop:{STOP_1} rgba(255, 0, 255, 0), stop:{STOP_2} rgba(85, 170, 255, 255));
        }
        """
        progress = (360 - value) / 360.0
        stop_1 = str(progress - 0.001)
        stop_2 = str(progress)
        if value == 360:
            stop_1 = "1.000"
            stop_2 = "1.000"
        newStylesheet = styleSheet.replace("{STOP_1}", stop_1).replace("{STOP_2}", stop_2)
        self.circularprogress.setStyleSheet(newStylesheet)
     
    def calibrate_gyro(self):
        self.display = 1
        self.obj.clear()
        self.a.calibrate = 1
        self.a.offset = []
        self.a.angle_acc = np.array([])
        self.a.q_int = [1,0,0,0]
        self.progressBarValue(0)
        self.labelangle.setText('')
    
    def reset_offset(self):
        self.pushbuttonstart.setEnabled(True)
        self.pushbuttonstart.setStyleSheet("background-color: rgb(243, 221, 255);")
    
    def enable_button(self):
        # Enable the button again
        self.pushbuttonstart.setEnabled(True)
        self.pushbuttonstart.setStyleSheet("""
        QPushButton {
            background-color: #5a9bd5;
            color: #ffffff;
            border: 1px solid #3a7bbf;
            border-radius: 6px;
            padding: 8px 15px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #76a9e0;
            border: 1px solid #5a9bd5;
        }
        QPushButton:pressed {
            background-color: #487aa5;
            border: 1px solid #3a7bbf;
            padding-left: 13px;
            padding-top: 7px;
        }
        QPushButton:disabled {
            background-color: #c5c5c5;
            color: #7d7d7d;
            border: 1px solid #a9a9a9;
        }
        """)
    
    def start_assess(self):
        if self.lineedithospitalnumber.text() == '' or self.comboBoxjoint.currentText() == '' or self.comboBoxmovement.currentText() == '':
            self.pushbuttonstart.setEnabled(False)
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Input Required")
            msg_box.setText("Please enter subject details.")
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.buttonClicked.connect(self.enable_button)
            msg_box.exec_()
        if self.lineedithospitalnumber.text()!='' and self.comboBoxjoint.currentText()!='' and self.comboBoxmovement.currentText()!='':
            self.a.subject_name = self.lineedithospitalnumber.text()
            self.a.joint = self.comboBoxjoint.currentText()
            self.a.movement = self.comboBoxmovement.currentText()
            self.start_disp = 1
            self.a.reset = 1
            self.display = 1
            self.obj.clear()
            self.a.offset = []
            self.a.angle_acc = np.array([])
            self.a.q_int = [1,0,0,0]
            global path3
            self.labeljoint.setText(self.comboBoxjoint.currentText())
            self.labelmovement.setText(self.comboBoxmovement.currentText())
            path2 = r'data'
            id_path = os.path.join(path2, self.lineedithospitalnumber.text())
            jointpath=os.path.join(id_path,self.comboBoxjoint.currentText())
            movementpath=os.path.join(jointpath,self.comboBoxmovement.currentText())
            path3=os.path.join(movementpath, 'session00.csv')
            if not os.path.exists(path2):
                os.makedirs(path2)
            if not os.path.exists(id_path):
                os.makedirs(id_path)
            if not os.path.exists(jointpath):
                os.makedirs(jointpath)
            if not os.path.exists(movementpath):
                os.makedirs(movementpath)
            while os.path.exists(path3):
                base=list(os.path.basename(path3))
                if int(base[8])<9:
                    base[8]=int(base[8])+1
                    base[8]=str(base[8])
                elif int(base[8])==9:
                    base[7]=int(base[7])+1
                    base[7]=str(base[7])
                    base[8]=int(base[8])-9
                    base[8]=str(base[8])
                seperator = ' '
                base=seperator.join(base)
                path3=os.path.join(movementpath,base.replace(" ", ""))
            self.a.kill_switch(1,path3)
          
    def update_plot_data(self):
        if self.start_disp==1:
            if len(self.a.angle_acc)>100:
                rom = np.max(self.a.angle_acc)
                self.progressBarValue(rom)
                self.labelangle.setText(str(round(rom,2)))
        self.obj.clear()
        if self.display:
            x_plot1 = np.linspace(0,len(self.a.angle_acc)/600,len(self.a.angle_acc))
            y_plot1 = self.a.angle_acc
            if len(x_plot1) != len(y_plot1):
                y_plot1 = y_plot1[1:]
            self.obj.plot(x_plot1,y_plot1, pen=self.pen)
        else:
            x_plot2 = np.linspace(0,len(self.freeze)/600,len(self.freeze))
            y_plot2 = self.freeze
            if len(x_plot2) != len(y_plot2):
                y_plot2 = y_plot2[1:]
            self.obj.plot(x_plot2,y_plot2, pen=self.pen)
            self.obj.addLine(y=0,pen=pg.mkPen(color='b'))
            self.obj.addLine(y=np.max(self.freeze),pen=pg.mkPen(color='b'))
            self.obj.plot([np.argmax(self.freeze)/600,np.argmax(self.freeze)/600],[0,np.max(self.freeze)],pen=pg.mkPen(color='k'))

    def stop_assess(self):
        if self.lineedithospitalnumber.text() == '' or self.comboBoxjoint.currentText() == '' or self.comboBoxmovement.currentText() == '':
            self.pushbuttonstart.setEnabled(False)
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Input Required")
            msg_box.setText("Please enter subject details.")
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.buttonClicked.connect(self.enable_button)
            msg_box.exec_()
        self.start_disp = 0
        self.a.kill_switch(0,path3)
        rom = np.max(self.a.angle_acc)
        self.progressBarValue(rom)
        self.labelangle.setText(str(round(rom,2)))
        self.freeze = self.a.angle_acc
        self.display = 0
        
    def show_new_window(self):
        self.reader1 = Thread(target=self.connectnow,args=())
        self.reader1.start()
     
    def connectnow(self):
        while 1:
            time.sleep(0.05)
            self.signalComm.request_graph_update.emit()
    

    def show_stats(self):
        global_summary_path = os.path.join("data", "global_summary.csv")
        
        if not os.path.exists(global_summary_path):
            QMessageBox.information(self, "Stats", "No global summary data found.")
            return

        df = pd.read_csv(global_summary_path)

        # Clean and normalize data
        df["Subject_ID"] = df["Subject_ID"].astype(str).str.strip().str.lower()
        df["Joint"] = df["Joint"].astype(str).str.strip()
        df["Movement"] = df["Movement"].astype(str).str.strip()
        df["Date_Time"] = pd.to_datetime(df["Date_Time"])

        if df.empty:
            QMessageBox.information(self, "Stats", "No valid data to display.")
            return

        stats_dialog = StatsDialog(df, self)
        stats_dialog.exec_()
    
   
 

app = QApplication(sys.argv)
welcome = WelcomeScreen()
widget = QtWidgets.QStackedWidget()
widget.addWidget(welcome)
widget.setFixedHeight(676)
widget.setFixedWidth(1251)
widget.show()
try:
    sys.exit(app.exec_())
except:
    print("Exiting")
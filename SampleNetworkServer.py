import threading
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import infinc
import time
import math
import socket
import ssl
import errno


class SmartNetworkThermometer (threading.Thread) :
    prot_cmds = ["SET_DEGF", "SET_DEGC", "SET_DEGK", "GET_TEMP", "UPDATE_TEMP"]

    def __init__ (self, source, updatePeriod, listen_addr, port,
                  server_cert, server_key, client_certs):
        threading.Thread.__init__(self, daemon = True) 
        #set daemon to be true, so it doesn't block program from exiting
        self.source = source
        self.updatePeriod = updatePeriod
        self.curTemperature = 0
        self.updateTemperature()

        self.context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.context.verify_mode = ssl.CERT_REQUIRED
        self.context.load_cert_chain(certfile=server_cert, keyfile=server_key)
        self.context.load_verify_locations(cafile=client_certs)

        self.server_socket = socket.socket()
        self.server_socket.bind((listen_addr, port))
        self.server_socket.listen(5)

        self.deg = "K"

    def setSource(self, source) :
        self.source = source

    def setUpdatePeriod(self, updatePeriod) :
        self.updatePeriod = updatePeriod 

    def setDegreeUnit(self, s) :
        self.deg = s
        if self.deg not in ["F", "K", "C"] :
            self.deg = "K"

    def updateTemperature(self) :
        self.curTemperature = self.source.getTemperature()

    def getTemperature(self) :
        if self.deg == "C" :
            return self.curTemperature - 273
        if self.deg == "F" :
            return (self.curTemperature - 273) * 9 / 5 + 32

        return self.curTemperature

    def run(self) : #the running function
        while True:
            new_socket, addr = self.server_socket.accept()
            conn = self.context.wrap_socket(new_socket, server_side=True)
            while True:
                try:
                    data = conn.recv(4096)
                    msg = data.decode("utf-8").strip()
                    cmds = msg.split(';')
                    for c in cmds:
                        if c == "SET_DEGF":
                            self.deg = "F"
                        elif c == "SET_DEGC":
                            self.deg = "C"
                        elif c == "SET_DEGK":
                            self.deg = "K"
                        elif c == "GET_TEMP":
                            conn.send(b"%f\n" % self.getTemperature())
                        elif c == "UPDATE_TEMP":
                            self.updateTemperature()
                        elif c == "LOGOUT":
                            conn.close()
                            break
                        elif c:
                            conn.send(b"Invalid Command\n")
                except IOError as e:
                    if e.errno == errno.EWOULDBLOCK:
                        # do nothing
                        pass
                    else:
                        # do nothing for now
                        pass
                    msg = ""

                self.updateTemperature()
                time.sleep(self.updatePeriod)


class SimpleClient :
    def __init__(self, therm1, therm2) :
        self.fig, self.ax = plt.subplots()
        now = time.time()
        self.lastTime = now
        self.times = [time.strftime("%H:%M:%S", time.localtime(now-i)) for i in range(30, 0, -1)]
        self.infTemps = [0]*30
        self.incTemps = [0]*30
        self.infLn, = plt.plot(range(30), self.infTemps, label="Infant Temperature")
        self.incLn, = plt.plot(range(30), self.incTemps, label="Incubator Temperature")
        plt.xticks(range(30), self.times, rotation=45)
        plt.ylim((0, 400))
        plt.legend(handles=[self.infLn, self.incLn])
        self.infTherm = therm1
        self.incTherm = therm2

        self.ani = animation.FuncAnimation(self.fig, self.updateInfTemp, interval=500)
        self.ani2 = animation.FuncAnimation(self.fig, self.updateIncTemp, interval=500)

    def updateTime(self) :
        now = time.time()
        if math.floor(now) > math.floor(self.lastTime) :
            t = time.strftime("%H:%M:%S", time.localtime(now))
            self.times.append(t)
            #last 30 seconds of of data
            self.times = self.times[-30:]
            self.lastTime = now
            plt.xticks(range(30), self.times,rotation = 45)
            plt.title(time.strftime("%A, %Y-%m-%d", time.localtime(now)))


    def updateInfTemp(self, frame) :
        self.updateTime()
        self.infTemps.append(self.infTherm.getTemperature())
        #self.infTemps.append(self.infTemps[-1] + 1)
        self.infTemps = self.infTemps[-30:]
        self.infLn.set_data(range(30), self.infTemps)
        return self.infLn,

    def updateIncTemp(self, frame) :
        self.updateTime()
        self.incTemps.append(self.incTherm.getTemperature())
        #self.incTemps.append(self.incTemps[-1] + 1)
        self.incTemps = self.incTemps[-30:]
        self.incLn.set_data(range(30), self.incTemps)
        return self.incLn,

UPDATE_PERIOD = .05 #in seconds
SIMULATION_STEP = .1 #in seconds
SERVER_CERT = 'certs/server.crt'
SERVER_KEY = 'certs/server.key'
CLIENT_CERT = 'certs/client.crt'

#create a new instance of IncubatorSimulator
bob = infinc.Human(mass = 8, length = 1.68, temperature = 36 + 273)
#bobThermo = infinc.SmartThermometer(bob, UPDATE_PERIOD)
bobThermo = SmartNetworkThermometer(bob, UPDATE_PERIOD, '127.0.0.1', 23456,
                                    SERVER_CERT, SERVER_KEY,
                                    CLIENT_CERT)
bobThermo.start() #start the thread

inc = infinc.Incubator(width = 1, depth=1, height = 1, temperature = 37 + 273, roomTemperature = 20 + 273)
#incThermo = infinc.SmartNetworkThermometer(inc, UPDATE_PERIOD)
incThermo = SmartNetworkThermometer(inc, UPDATE_PERIOD, '127.0.0.1', 23457,
                                    SERVER_CERT, SERVER_KEY,
                                    CLIENT_CERT)
incThermo.start() #start the thread

incHeater = infinc.SmartHeater(powerOutput = 1500, setTemperature = 45 + 273, thermometer = incThermo, updatePeriod = UPDATE_PERIOD)
inc.setHeater(incHeater)
incHeater.start() #start the thread

sim = infinc.Simulator(infant = bob, incubator = inc, roomTemp = 20 + 273, timeStep = SIMULATION_STEP, sleepTime = SIMULATION_STEP / 10)

sim.start()

sc = SimpleClient(bobThermo, incThermo)

plt.grid()
plt.show()


from twisted.web import server, resource, static
from twisted.internet import reactor

import subprocess
import time
import sys
import ConfigParser
import os
import platform
import threading 

def isGadgetronAlive(port,environment):
    process = subprocess.Popen(["gt_alive","localhost",str(port)], env=environment)
    
    time.sleep(1)
    ret = process.poll()
    if ret == None:
        #Process is hanging
        process.kill()
        return -1
    elif ret != 0:
        #Failed to connect
        return -1
    else:
        return 0


class GadgetronResource(resource.Resource):
    isLeaf = True
    numberRequests = 0
    gadgetron_log_filename = 'gadgetron_log.txt'
    gadgetron_process = 0
    environment = 0;
    gadgetron_port = 9002
    check_thread = 0

    def __init__(self, cfgfilename):
        config = ConfigParser.RawConfigParser()
        config.read(cfgfilename)
        gadgetron_home = config.get('GADGETRON', 'GADGETRON_HOME')
        ismrmrd_home = config.get('GADGETRON', 'ISMRMRD_HOME')
        self.gadgetron_log_filename = config.get('GADGETRON','logfile')
        self.gadgetron_port = config.get('GADGETRON','port')
        gf = open(self.gadgetron_log_filename,"w")
        
        self.environment = dict()
        self.environment["GADGETRON_HOME"]=gadgetron_home
        self.environment["PATH"]=self.environment["GADGETRON_HOME"] + "/bin"

        if (platform.system() == 'Linux'):
            self.environment["LD_LIBRARY_PATH"]="/usr/local/cuda/lib64:/usr/local/cula/lib64:" +  self.environment["GADGETRON_HOME"] + "/lib:" + ismrmrd_home + "/lib"  
        elif (platform.system() == 'Darwin'):
            self.environment["DYLD_LIBRARY_PATH"]="/usr/local/cuda/lib64:/usr/local/cula/lib64:" +  self.environment["GADGETRON_HOME"] + "/lib:" + ismrmrd_home + "/lib:/opt/local/lib"  

        self.gadgetron_process = subprocess.Popen(["gadgetron","-p",self.gadgetron_port], env=self.environment,stdout=gf,stderr=gf)
        resource.Resource.__init__(self)
        
        self.check_thread = threading.Thread(target=self.check_gadgetron)
        self.check_thread.start()

    def __del__(self):
        self.check_thread.stop()
        self.gadgetron_process.terminate()

    def restart_gadgetron(self):
        s = self.gadgetron_process.poll()
        if (s == None):
            self.gadgetron_process.kill()
        gf = open(self.gadgetron_log_filename,"w")
        self.gadgetron_process = subprocess.Popen(["gadgetron"], env=self.environment,stdout=gf,stderr=gf)

    def check_gadgetron(self):
        while (True):
            s = self.gadgetron_process.poll()
            if (s != None):
                self.restart_gadgetron()
            time.sleep(3)
        

    def render_GET(self, request):
        gadgetron_restarted = False
        print_log_file = False
        
        if 'command' in request.args:
            if request.args['command'] == ['restart']:
                self.restart_gadgetron()
                time.sleep(2)
                gadgetron_restarted = True

            if request.args['command'] == ['log']:
                print_log_file = True

        doc = "<html>\n<body>\n"
        doc += "<h1>Gadgetron Monitor</h1>\n"

        alive = (isGadgetronAlive(self.gadgetron_port,self.environment) == 0)

        if gadgetron_restarted:
            doc += "<div><h2>Gadgetron Restarted</h2></div>"
    
        doc += "<div>Gadgetron Status: "

        if (alive):
            doc += "<span style=\"color: green;\">[OK]</span>"
        else:
            doc += "<span style=\"color: red;\">[UNRESPONSIVE]</span>"
            
        doc += "</div>"

        doc += "<div><a href=\"/gadgetron/?command=log\">[LOG]</a> <a href=\"/gadgetron/?command=restart\">[RESTART]</a></div>\n"
        
        if print_log_file:
            doc += "<iframe width=\"1024\" height=\"768\" src=\"/log\"></iframe>" 
        
        doc += "</body>\n</html>"
        return doc

class GadgetronLogResource(resource.Resource):
    filename = ""

    def __init__(self, logfilename):
        self.filename = logfilename
        resource.Resource.__init__(self)

    def render_GET(self, request):
        gf = open(self.filename,"r")
        l = gf.read()
        return "<html><body><pre style=\"font-size: 8px\">" + l + "</pre></body></html>"

config = ConfigParser.RawConfigParser()
config.read(sys.argv[1])
gadgetron_home = config.get('GADGETRON', 'GADGETRON_HOME')
port = int(config.get('WEBSERVER','port'))

root = resource.Resource()
root.putChild('gadgetron',GadgetronResource(sys.argv[1]))
root.putChild('log', GadgetronLogResource(config.get('GADGETRON','logfile')))

reactor.listenTCP(port, server.Site(root))
reactor.run()

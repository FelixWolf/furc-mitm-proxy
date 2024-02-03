#!/usr/bin/env python3
import sys
import os
import asyncio
import struct
import asyncio.exceptions
import libfurc.base
import socket
import HTTPServer
import logging
import traceback
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class Notifyd:
    def __init__(self):
        self.host = os.getenv("NOTIFY_SOCKET", None)
        self.socket = None
        if self.host != None:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            if self.host.startswith("@"):
                self.socket.connect("\0" + self.host[1:])
            else:
                self.socket.connect(self.host)
    
    def send(self, msg):
        if self.socket:
            self.socket.sendall(msg)
        else:
            for line in msg.split(b"\n"):
                if b"=" in line:
                    op, data = line.split(b"=",1)
                    print("[NOTIFY] {}: {}".format(op.decode(), data.decode()))
                else:
                    print("[NOTIFY] MALFORMED MESSAGE: {}".format(line.decode()))
    
    def ready(self):
        self.send(b"READY=1")
    
    def stopping(self):
        self.send(b"STOPPING=1")
    
    def reloading(self):
        self.send(b"RELOADING=1")
    
    def status(self, status):
        if type(status) == str:
            status = status.encode()
        self.send(b"STATUS="+status.replace(b"\n", b"\\n"))

notify = Notifyd()

def mitm_header_read(data):
    opcode = libfurc.base.b95decode(data[0:2])
    dlen = libfurc.base.b95decode(data[2:5])
    return opcode, dlen

def mitm_header_write(opcode, dlen):
    return libfurc.base.b95encode(opcode, 2) + libfurc.base.b95encode(dlen, 3)


def wrapReader(self, reader, local = False):
    readuntil = reader.readuntil
    async def readuntilWrapped(*args, **kwargs):
        data = await readuntil(*args, **kwargs)
        if data:
            self.rx += len(data)
            if local:
                self.parent.rxl += len(data)
            else:
                self.parent.rx += len(data)
        return data
    reader.readuntil = readuntilWrapped
    
    read = reader.read
    async def readWrapped(*args, **kwargs):
        data = await read(*args, **kwargs)
        if data:
            self.rx += len(data)
            if local:
                self.parent.rxl += len(data)
            else:
                self.parent.rx += len(data)
        return data
    reader.read = readWrapped

def wrapWriter(self, writer, local = False):
    write = writer.write
    def writeWrapped(data, *args, **kwargs):
        res = write(data, *args, **kwargs)
        if data:
            self.tx += len(data)
            if local:
                self.parent.txl += len(data)
            else:
                self.parent.tx += len(data)
        return res
    writer.write = writeWrapped

class MITMInstance:
    FLAG_BLOCK_CLIENT = 1
    FLAG_BLOCK_SERVER = 2
    def __init__(self, parent, client_reader, client_writer):
        self.parent = parent
        self.disconnecting = False
        self.rx = 0
        self.tx = 0
        self.client_reader, self.client_writer = client_reader, client_writer
        wrapReader(self, self.client_reader, True)
        wrapWriter(self, self.client_writer, True)
        self.listenering = None
        self.flags = 0
    
    @property
    def blocks_server(self):
        return self.flags & self.FLAG_BLOCK_SERVER
    
    @property
    def blocks_client(self):
        return self.flags & self.FLAG_BLOCK_CLIENT
    
    async def disconnect(self):
        if self.disconnecting:
            return
        self.disconnecting = True
        try:
            self.listenering.listeners.remove(self)
        except Exception as e:
            pass
        self.parent.mitm_connections.remove(self)

    async def from_mitm(self):
        while not self.disconnecting:
            try:
                data = await self.client_reader.readuntil(separator=b'\n')
            except (asyncio.exceptions.IncompleteReadError, ConnectionResetError) as e:
                data = None
            if self.disconnecting or not data:
                await self.disconnect()
                return
            
            opcode, dlen = mitm_header_read(data)
            data = data[5:]
            if dlen != len(data):
                print("Length mismatch: {} {}".format(dlen, len(data)))

            #print("Opcode {} size {}".format(opcode, dlen))
            if opcode == 0:
                #Send to client
                if not self.listenering:
                    continue
                try:
                    self.listenering.client_writer.write(data)
                    await self.listenering.client_writer.drain()
                except Exception as e:
                    pass
            
            elif opcode == 1:
                #Send to server
                if not self.listenering:
                    continue
                try:
                    self.listenering.server_writer.write(data)
                    await self.listenering.server_writer.drain()
                except Exception as e:
                    pass
            
            elif opcode == 2:
                #Disconnection
                if not self.listenering:
                    continue
                try:
                    self.listenering.listeners.remove(self)
                    self.listenering = None
                except Exception as e:
                    pass
            
            elif opcode == 3:
                #Find
                cons = []
                for con in self.parent.connections:
                    cons.append("{}:{}".format(con.id, con.getName()))
                data = " ".join(cons).encode()
                self.client_writer.write(mitm_header_write(3, len(data)+1)+data+b"\n")
                await self.client_writer.drain()
            
            elif opcode == 4:
                #Choose
                try:
                    conn = None
                    i = int(data.decode())
                    for con in self.parent.connections:
                        if con.id == i:
                            conn = con
                    if conn:
                        self.client_writer.write(mitm_header_write(4, 3)+b"ok\n")
                        await self.client_writer.drain()
                    else:
                        self.client_writer.write(mitm_header_write(4, 3)+b"no\n")
                        await self.client_writer.drain()
                    if self.listenering:
                        try:
                            self.listenering.listeners.remove(self)
                            self.listenering = None
                        except Exception as e:
                            print(e)
                            pass
                    self.listenering = conn
                    self.listenering.listeners.append(self)
                except Exception as e:
                    print(e)
                    self.client_writer.write(mitm_header_write(4, 3)+b"er\n")
                    await self.client_writer.drain()
            
            elif opcode == 5:
                #Set flags
                if len(data) == 3:
                    self.flags = libfurc.base.b95decode(data[:2])
                self.client_writer.write(mitm_header_write(5, 3)+libfurc.base.b95encode(self.flags, 2)+b"\n")
                await self.client_writer.drain()
            
            elif opcode == 6:
                #New connect
                #NOP
                pass
            
            elif opcode == 7:
                #Ping
                self.client_writer.write(mitm_header_write(8, len(data))+data+b"\n")
            
            elif opcode == 8:
                #Pong
                pass
            
            else:
                self.client_writer.write(mitm_header_write(255, 1)+b"\n")
                await self.client_writer.drain()

    async def write(self, data):
        self.client_writer.write(data)
        await self.client_writer.drain()

    async def start(self):
        try:
            await self.from_mitm()
        except Exception as e:
            traceback.print_exc()
            if not self.disconnecting:
                await self.disconnect()

class FurcadiaProxyInstance:
    SERVER_HOST = "72.52.134.168" #"lightbringer.furcadia.com"
    SERVER_PORT = 6500
    def __init__(self, parent, client_reader, client_writer, host=None, port=None):
        self.parent = parent
        self.disconnecting = False
        self.host = host or self.SERVER_HOST
        self.port = port or self.SERVER_PORT
        self.rx = 0
        self.tx = 0
        self.client_reader, self.client_writer = client_reader, client_writer
        wrapReader(self, self.client_reader)
        wrapWriter(self, self.client_writer)
        self.id2 = 0
        self.id = self.client_writer.get_extra_info("peername")[1]
        self.listeners = []
        self.data = {
            "character": "",
            "script": None,
            "script_logging": False
        }
    
    def getName(self):
        if self.data["character"]:
            return self.data["character"].decode()
        return str(self.id)

    async def disconnect(self):
        if self.disconnecting:
            return
        self.disconnecting = True
        c = str(self.id).encode()
        await self.parent.announce(mitm_header_write(2, len(c)+1)+c+b"\n")
        """
        for listener in self.listeners:
            try:
                await listener.write(mitm_header_write(2, 1)+b"\n")
            except Exception as e:
                print(e)
                self.listeners.remove(listener)
        """
        for p in [self.server_writer, self.client_writer]:
            try:
                p.close()
                await p.wait_closed()
            except Exception as e:
                print(e)
                pass
        self.parent.connections.remove(self)

    async def to_client(self):
        while not self.disconnecting:
            try:
                data = await self.server_reader.readuntil(separator=b'\n')
            except asyncio.exceptions.IncompleteReadError as e:
                data = None
            if self.disconnecting or not data:
                await self.disconnect()
                return

            if self.disconnecting or self.client_writer.is_closing():
                await self.disconnect()
                return
            
            blocking = False
            for listener in self.listeners:
                try:
                    blocks = await listener.write(mitm_header_write(0, len(data))+data)
                    blocking = blocking or listener.blocks_server
                except Exception as e:
                    print(e)
                    self.listeners.remove(listener)
            
            if not blocking:
                self.client_writer.write(data)
                await self.client_writer.drain()

    async def from_client(self):
        while not self.disconnecting:
            try:
                data = await self.client_reader.readuntil(separator=b'\n')
            except asyncio.exceptions.IncompleteReadError as e:
                data = None

            if self.disconnecting or not data:
                await self.disconnect()
                return

            if self.disconnecting or self.server_writer.is_closing():
                await self.disconnect()
                return
            
            blocking = False
            for listener in self.listeners:
                try:
                    await listener.write(mitm_header_write(1, len(data))+data)
                    blocking = blocking or listener.blocks_client
                except Exception as e:
                    print(e)
                    self.listeners.remove(listener)

            if data == b"which\n":
                self.client_writer.write("(<img src='fsh://system.fsh:86' /> You are connected to Hermes [{}] (QTEMP {}). There are {} players on this Hermes, of which you are player index {} with global id {}.\n".format(
                    self.parent.port,
                    self.id2,
                    len(self.parent.connections),
                    self.parent.connections.index(self) + 1 if self in self.parent.connections else "NaN",
                    self.id
                ).encode())
                await self.client_writer.drain()
            
            elif data[:7] == b"script ":
                if data[7:] == b"start\n":
                    if self.data["script"] != None:
                        self.client_writer.write("(<img src='fsh://system.fsh:86' /> <font color='error'>Script already running!</font>\n".encode())
                        await self.client_writer.drain()
                    else:
                        await self.startScript()
                    
                elif data[7:] == b"restart\n":
                    if self.data["script"] == None:
                        self.client_writer.write("(<img src='fsh://system.fsh:86' /> <font color='error'>No script running!</font>\n".encode())
                        await self.client_writer.drain()
                    else:
                        await self.stopScript()
                        await self.startScript()
                    
                elif data[7:] == b"stop\n":
                    if self.data["script"] == None:
                        self.client_writer.write("(<img src='fsh://system.fsh:86' /> <font color='error'>No script running!</font>\n".encode())
                        await self.client_writer.drain()
                    else:
                        await self.stopScript()
                
                elif data[7:] == b"status\n":
                    if self.data["script"] == None:
                        self.client_writer.write("(<img src='fsh://system.fsh:86' /> Script not running.\n".encode())
                        await self.client_writer.drain()
                    
                    elif self.data["script"] != None:
                        self.client_writer.write("(<img src='fsh://system.fsh:86' /> Script running.\n".encode())
                        await self.client_writer.drain()
                    
                elif data[7:11] == b"log ":
                    if data[11:] == b"on\n":
                        self.client_writer.write("(<img src='fsh://system.fsh:86' /> <font color='success'>Logging enabled.</font>\n".encode())
                        await self.client_writer.drain()
                        self.data["script_logging"] = True
                    
                    elif data[11:] == b"off\n":
                        self.client_writer.write("(<img src='fsh://system.fsh:86' /> <font color='success'>Logging disabled.</font>\n".encode())
                        await self.client_writer.drain()
                        self.data["script_logging"] = False
                    
                else:
                    self.client_writer.write("(<img src='fsh://system.fsh:86' /> <font color='error'>Unknown command</font>\n".encode())
                    await self.client_writer.drain()
                
                continue
            
            elif data[:8] == b"connect ":
                self.data["character"] = data.split(b" ")[1]
            
            elif data[:8] == b"account ":
                self.data["character"] = data.split(b" ")[2]
            
            
            if not blocking:
                self.server_writer.write(data)
                await self.server_writer.drain()
    
    async def startScript(self):
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-u", os.path.join("/home/felix/.scripts", "furc_mitm_agent.py"),
            '--character', self.data["character"],
            limit = 1024 * 1024,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        
        async def job(self, proc):
            self.client_writer.write("(<img src='fsh://system.fsh:86' /> <font color='success'>Script started.</font>\n".encode())
            await self.client_writer.drain()
            
            while True:
                try:
                    data = await proc.stdout.readline()
                except ValueError as e:
                    continue
                except Exception as e:
                    self.client_writer.write("(<img src='fsh://system.fsh:86' /> {}\n".format(str(e).replace("\n","\\n")).encode())
                    break
                
                if data == b"" or data == None:
                    break
                
                line = data[:-1]
                
                if self.data["script_logging"] == True:
                    self.client_writer.write("(<img src='fsh://system.fsh:86' /> {}\n".format(line.decode().replace("\n","\\n")).encode())
                    await self.client_writer.drain()
            
            self.client_writer.write("(<img src='fsh://system.fsh:86' /> <font color='success'>Script stopped.</font>\n".encode())
            await self.client_writer.drain()
            
            self.data["script"] = None
        
        self.data["script"] = {
            "proc": proc,
            "job": asyncio.ensure_future(job(self, proc))
        }
    
    async def stopScript(self):
        if self.data["script"] != None:
            self.data["script"]["proc"].terminate()
    
    async def start(self):
        self.server_reader, self.server_writer = \
            await asyncio.open_connection(self.host, self.port)
        self.id2 = self.server_writer.get_extra_info("sockname")[1]
        tmp = str(self.id).encode()
        await self.parent.announce(mitm_header_write(6, len(tmp)+1)+tmp+b"\n")
        asyncio.create_task(self.from_client())
        asyncio.create_task(self.to_client())

class MITMWebsocket(HTTPServer.WSServer):
    def __init__(self, proxy, *args, **kwargs):
        self.proxy = proxy
        super().__init__(*args, **kwargs)
    
    async def handle_websocket(self, request, websocket):
        await websocket.accept()
        
        instance = MITMInstance(self.proxy, websocket.reader, websocket.writer)
        instance.websocket = websocket
        self.proxy.mitm_connections.append(instance)
        await instance.start()
    
    async def handle_request(self, request):
        if request.method == "GET" \
           and request.getHeader("connection", "").lower() == "upgrade" \
           and request.getHeader("upgrade", "").lower() == "websocket":
               
            response = HTTPServer.HTTPResponse(request, 200)
            logger.debug("{} requesting websocket upgrade".format(request.remote_addr))
            
            if request.getHeader("Sec-Websocket-Key") == None:
                logger.debug("{} missing Sec-Websocket-Key".format(request.remote_addr))
                response.status = 400
                await response.write(b"Missing Sec-Websocket-Key header")
            
            else:
                logger.debug("Initializing websocket handler for {}".format(request.remote_addr))
                websocket = HTTPServer.HTTPWebsocket(request, response)
                await self.handle_websocket(request, websocket)
        
        else:
            response = HTTPServer.HTTPResponse(request, 200)
            with open("furc_mitm.htm", "rb") as f:
                await response.write(f.read())

class FurcadiaProxy:
    PROXY_HOST = "127.0.0.1"
    PROXY_PORT = 6500
    PROXY_MITM_PORT = 6501
    PROXY_MITM_PORT_WS = 6502
    def __init__(self, host = None, port = None, mitm_port = None, mitm_port_ws = None):
        self.host = host or self.PROXY_HOST
        self.port = port or self.PROXY_PORT
        self.mitm_port = mitm_port or self.PROXY_MITM_PORT
        self.mitm_port_ws = mitm_port_ws or self.PROXY_MITM_PORT_WS
        self.ws_mitm = MITMWebsocket(self)
        self.connections = []
        self.mitm_connections = []
        self.rx = 0
        self.tx = 0
        self.rxl = 0
        self.txl = 0
    
    async def announce(self, data):
        for client in self.mitm_connections:
            await client.write(data)
    
    async def handle_proxy(self, reader, writer):
        instance = FurcadiaProxyInstance(self, reader, writer)
        self.connections.append(instance)
        asyncio.create_task(instance.start())

    async def handle_mitm(self, reader, writer):
        instance = MITMInstance(self, reader, writer)
        self.mitm_connections.append(instance)
        asyncio.create_task(instance.start())
    
    async def start(self):
        notify.ready()
        self.proxy = await asyncio.start_server(
            self.handle_proxy, self.host, self.port)
        self.mitm = await asyncio.start_server(
            self.handle_mitm, self.host, self.mitm_port)
        self.wsmitm = await self.ws_mitm.start_server(self.host, self.mitm_port_ws)

        print('Listening for Furcadia on {}'.format(
                ', '.join(str(sock.getsockname()) for sock in self.proxy.sockets)
            )
        )
        print('Listening for MITM on {}'.format(
                ', '.join(str(sock.getsockname()) for sock in self.mitm.sockets)
            )
        )
        print('Listening for WSMITM on {}'.format(
                ', '.join(str(sock.getsockname()) for sock in self.wsmitm.sockets)
            )
        )
        async with self.proxy, self.mitm, self.wsmitm:
            await asyncio.gather(
                self.proxy.serve_forever(),
                self.mitm.serve_forever(),
                self.wsmitm.serve_forever(),
                self.update()
            )
    
    async def update(self):
        while True:
            notify.status("Serving {} (rx {} / tx {}) clients and {} (rx {} / tx {}) agents".format(
                len(self.connections), self.rx, self.tx,
                len(self.mitm_connections), self.rxl, self.txl
            ))
            await asyncio.sleep(5)

proxy = FurcadiaProxy()
asyncio.run(proxy.start())

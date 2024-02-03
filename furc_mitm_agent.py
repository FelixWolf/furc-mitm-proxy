#!/usr/bin/env python3
import struct
import socket
import sys
import traceback
import random
import libfurc.client
import libfurc.base
import io
import asyncio
import tkinter as tk
from tkinter import ttk
import time
import shlex
import os
import re
import codecs
import hashlib
import math

BBuddyJokes = []
try:
    with open("./data/jokes.txt", "r") as f:
        BBuddyJokes = list(filter(None,f.read().split("\n")))
except FileNotFoundError as e:
    pass

Fortunes = []
try:
    with open("./data/fortunes.txt", "r") as f:
        Fortunes = list(filter(None,f.read().split("\n")))
except FileNotFoundError as e:
    pass

class Random:
    def __init__(self, seed = None):
        self.magic = 0x9908B0DF
        self.period = 37
        self.statelen = 63
        self.state = [0] * (self.statelen + 1)
        self.next = 1
        self.left = -1
        if seed:
            self.seed(seed)
    
    def seed(self, seed):
        x = (1 | seed) & 0xffffffff
        self.left = 0
        self.state[0] = x
        for i in range(62):
            x = 69069 * x & 4294967295
            self.state[i + 1] = x
    
    def reload(self):
        if self.left < -1:
            self.seed(4357)
        
        self.left = 61
        self.next = 1
        
        e = self.state[0]
        h = self.state[1]
        n = 26
        
        s = self.period
        t = 0
        v = 2
        for n in reversed(range(1,27)):
            i = (0x80000000 & e | 0x7fffffff & h) >> 1
            n = 0
            if 1 == (1 & h):
                n = self.magic
            
            self.state[t] = self.state[s] ^ i ^ n
            t += 1
            s += 1
            
            e = h
            h = self.state[v]
            v += 1
        
        s = 0
        for n in reversed(range(1,self.period)):
            i = (0x80000000 & e | 0x7fffffff & h) >> 1
            n = 0
            if 1 == (1 & h):
                n = self.magic
            
            self.state[t] = self.state[s] ^ i ^ n
            t += 1
            s += 1
            e = h
            h = self.state[v]
            v += 1
        
        h = self.state[0]
        o = (0x80000000 & e | 0x7fffffff & h) >> 1
        r = 0
        if 1 == (1 & h):
            r = self.magic
        
        self.state[t] = self.state[s] ^ o ^ r
        h ^= h >> 11
        h ^= h << 7 & 0x9D2C5680
        h ^= h << 15 & 0xEFC60000
        return (h ^ h >> 18) >> 0
    
    def random(self):
        self.left = self.left - 1
        
        if self.left < 0:
            return self.reload()
        
        y = self.state[self.next]
        self.next += 1
        y ^= y >> 11
        y ^= y << 7 & 0x9D2C5680
        y ^= y << 15 & 0xEFC60000
        
        return (y ^ y >> 18) >> 0


async def printtb(fakeClientWriter):
    tb = traceback.format_exc().strip("\n")
    try:
        await sendMessage(fakeClientWriter, ["<font color=\"error\">{}</font>".format(i) for i in tb.split("\n")])
    except Exception as ee:
        print(ee)
        pass

def sortTreeView(tv, col, reverse=False):
    l = [(tv.set(k, col), k) for k in tv.get_children('')]
    l.sort(reverse=reverse, key=lambda x:int(x[1]))

    # rearrange items in sorted positions
    for index, (val, k) in enumerate(l):
        tv.move(k, '', index)

class GUIClient(tk.Tk):
    def __init__(self, client, fakeServerWriter, fakeClientWriter, attributes):
        self.client = client
        self.fakeServerWriter = fakeServerWriter
        self.fakeClientWriter = fakeClientWriter
        self.attributes = attributes
        self.activeFurres = []
        self.activeVars = []
        super().__init__()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.interval = 1/60
        self.init()
        self.update()
        self.geometry("400x300")
        self.lastUpdate = 0

    def init(self):
        #Create furre list
        #self.columnconfigure(0, weight=1)
        #self.rowconfigure(0, weight=1)
        notebook = ttk.Notebook(self)
        
        #Furre list
        furreListFrame = tk.Frame(notebook)
        furreListFrame.grid(row=0, column=0, sticky="NEWS")
        furreListFrame.columnconfigure(0, weight=1)
        furreListFrame.rowconfigure(0, weight=1)
        #furreListFrame.columnconfigure(1, weight=1)
        
        furreListScroll = tk.Scrollbar(furreListFrame, orient=tk.VERTICAL)
        furreListScroll.grid(row=0, column=1, sticky="NES")

        furreList = ttk.Treeview(furreListFrame,
            columns=tuple(range(1,6)), show='headings', height=3,
            yscrollcommand = furreListScroll.set,
            xscrollcommand = furreListScroll.set
        )
        def focusView(a):
            curItem = furreList.focus()
            b = furreList.item(curItem)["values"]
            self.fakeClientWriter.write(b"@"+libfurc.base.b95encode(b[2], 2) + libfurc.base.b95encode(b[3], 2)+b"\n")
        furreList.bind('<ButtonRelease-1>', focusView)

        furreListScroll.config(command=furreList.yview)
        
        furreList.heading(1, text="ID", anchor=tk.CENTER)
        furreList.heading(2, text="Name", anchor=tk.CENTER)
        furreList.heading(3, text="X", anchor=tk.CENTER)
        furreList.heading(4, text="Y", anchor=tk.CENTER)
        furreList.heading(5, text="Species", anchor=tk.CENTER)
        
        furreList.grid(row=0, column=0, sticky="NEWS")
        self.furreList = furreList
        
        #Var list
        varListFrame = tk.Frame(notebook)
        varListFrame.grid(row=0, column=0, sticky="NEWS")
        varListFrame.columnconfigure(0, weight=1)
        varListFrame.rowconfigure(0, weight=1)
        #varListFrame.columnconfigure(1, weight=1)
        
        varListScroll = tk.Scrollbar(varListFrame, orient=tk.VERTICAL)
        varListScroll.grid(row=0, column=1, sticky="NES")

        varList = ttk.Treeview(varListFrame,
            columns=tuple(range(1,3)), show='headings', height=3,
            yscrollcommand = varListScroll.set,
            xscrollcommand = varListScroll.set
        )
        
        varListScroll.config(command=varList.yview)
        
        varList.heading(1, text="Num", anchor=tk.CENTER)
        varList.heading(2, text="Val", anchor=tk.CENTER)
        
        varList.grid(row=0, column=0, sticky="NEWS")
        
        self.varList = varList
        
        #Random tool
        randomToolFrame = tk.Frame(notebook)
        randomToolFrame.grid(row=0, column=0, sticky="NEWS")
        randomToolFrame.columnconfigure(0, weight=1)
        randomToolFrame.rowconfigure(0)
        self.rtspinner = tk.Spinbox(randomToolFrame, from_=0, to=65535)
        self.rtspinner.grid(row=0, column=0, sticky="NEW")
        self.rtoffset = tk.Spinbox(randomToolFrame, from_=0, to=65535)
        self.rtoffset.grid(row=0, column=1, sticky="NEW")
        self.rtvalue = tk.StringVar(randomToolFrame)
        self.rtvalue.set("Prediction: {}".format(1))
        tk.Label(randomToolFrame, textvariable = self.rtvalue).grid(row=1, column=0, sticky="NEW")
        
        #varListFrame.columnconfigure(1, weight=1)
        
        #Finalize
        notebook.add(furreListFrame, text='Furres')
        notebook.add(varListFrame, text='Variables')
        notebook.add(randomToolFrame, text='Random Tool')
        notebook.pack(expand = 1, fill ="both")
        self.loop = asyncio.create_task(self._update())
    
    async def poll(self, t):
        if "furreTracker" in self.attributes and self.attributes["furreTracker"].dsAddon != None:
            rng = Random(self.attributes["furreTracker"].dsAddon["randSeed"])
            for i in range(0, int(self.rtoffset.get())):
                pass
            v = int(self.rtspinner.get())
            if v == 0:
                self.rtvalue.set("Prediction: {}".format(rng.random()))
            else:
                self.rtvalue.set("Prediction: {}".format(rng.random() % v))
        
        if "furreList" in self.attributes:
            for fuid in self.activeFurres:
                if fuid not in self.attributes["furreList"]:
                    self.furreList.delete(fuid)
                    self.activeFurres.remove(fuid)
            
            for fuid in self.attributes["furreList"]:
                furre = self.attributes["furreList"][fuid]
                if fuid not in self.activeFurres:
                    self.activeFurres.append(fuid)
                    self.furreList.insert(parent='', index=0, iid=fuid, values=(
                        fuid,
                        furre["name"].decode().replace("|", " "),
                        furre["x"],
                        furre["y"],
                        "{}, {}".format(furre["l"].species, furre["l"].avatar) if furre["l"] else ""
                    ))
                else:
                    self.furreList.item(fuid, values=(
                        fuid,
                        furre["name"].decode().replace("|", " "),
                        furre["x"],
                        furre["y"],
                        "{}, {}".format(furre["l"].species, furre["l"].avatar) if furre["l"] else ""
                    ))
        
            sortTreeView(self.furreList, 1)
        
        if "varList" in self.attributes:
            for fuid in self.activeVars:
                if fuid not in self.attributes["varList"]:
                    self.varList.delete(fuid)
                    self.activeVars.remove(fuid)
            
            for fuid in self.attributes["varList"]:
                furre = self.attributes["varList"][fuid]
                if fuid not in self.activeVars:
                    self.activeVars.append(fuid)
                    self.varList.insert(parent='', index=0, iid=fuid, values=(fuid, str(furre)))
                else:
                    self.varList.item(fuid, values=(fuid, str(furre)))
            sortTreeView(self.varList, 1)
    
    async def _update(self):
        while self.interval:
            t = time.time()
            if t >= self.lastUpdate + 0.1:
                try:
                    await self.poll(t)
                except Exception as e:
                    print(traceback.format_exc())
                self.lastUpdate = t
            self.update()
            await asyncio.sleep(self.interval)

    def close(self):
        self.attributes["gui"] = None
        self.interval = None
        self.destroy()

recordables = {
    b"m 1": "SW",
    b"m 2": "SW",
    b"m 3": "SE",
    b"m 4": "NW",
    b"m 5": "INVALID",
    b"m 6": "SE",
    b"m 7": "NW",
    b"m 8": "NE",
    b"m 9": "NE",
    b"<": "Left",
    b">": "Right",
    b"sit": "Sit",
    b"lie": "Lie",
    b"stand": "Stand",
    b"get": "Get",
    b"use": "Use",
    b"magic": "Magic",
    b"gloam -3": "Gloam(-3)",
    b"gloam -2": "Gloam(-2)",
    b"gloam -1": "Gloam(-1)",
    b"gloam 0": "Gloam(0)",
    b"gloam 1": "Gloam(+1)",
    b"gloam 2": "Gloam(+2)",
    b"gloam 3": "Gloam(+3)",
}
ctable = [
    [40, 41, 35, 0, 1, 2, 8, 43, 5, 3, 6, 7, 42, 10, 11, 14, 12, 13, 15, 28, 18, 17, 16, 44, 19, 22, 21, 20, 23, 34, 29, 24, 39, 38, 37, 25, 36, 27, 26, 33, 30, 31, 32, 4, 9],
    [0, 23, 2, 5, 20, 8, 10, 17, 4, 26, 12, 29, 30, 31, 33, 28, 32, 14, 27, 34, 35, 15, 37, 25, 38, 18, 39, 40, 24, 36, 41, 42, 43, 44, 19, 22, 1, 21, 13, 6, 7, 16, 11, 9, 3],
    [31, 27, 30, 17, 1, 20, 21, 0, 16, 8, 24, 32, 33, 41, 35, 36, 3, 25, 2, 4, 26, 38, 12, 28, 13, 6, 5, 9, 14, 10, 11, 39, 37, 40, 23, 29, 7, 22, 18, 15, 42, 43, 44, 19, 34],
    [42, 43, 41, 0, 1, 2, 44, 40, 6, 5, 3, 7, 8, 11, 10, 14, 12, 13, 18, 28, 15, 16, 17, 19, 23, 38, 34, 22, 21, 20, 29, 24, 39, 26, 25, 35, 36, 37, 27, 33, 32, 31, 30, 4, 9],
    [23, 25, 24, 18, 0, 31, 26, 22, 6, 2, 32, 34, 3, 35, 36, 4, 21, 17, 5, 39, 40, 8, 7, 41, 10, 29, 42, 33, 43, 28, 37, 44, 14, 9, 38, 20, 30, 27, 13, 19, 12, 11, 15, 16, 1]
]
async def handleClientMessage(client, data, fakeServerWriter, fakeClientWriter, attributes):
    print("CLIENT:",data)
        
    if attributes.get("recordInputs", False) and (data in recordables or \
        data.startswith((b":", b'"'))):
        attributes["recording"].append(data)
    
    if data.startswith(b'wh') or data.startswith(b'"'):
        return
    
    try:
        com = shlex.split(data.decode())
    except Exception as e:
        try:
            com = data.decode().split(" ",1)
        except Exception as e:
            print(e)
            return
    
    if len(com) == 0:
        return
    
    if com[0] == "script" and len(com) > 1:
        if com[1] == "stop":
            exit()
    
    elif com[0] == "gui":
        if "gui" in attributes and attributes["gui"]:
            attributes["gui"].focus()
        else:
            attributes["gui"] = GUIClient(client, fakeServerWriter, fakeClientWriter, attributes)
    
    elif com[0] == "pos":
        await sendMessage(fakeClientWriter, "* {}, {}".format(attributes["pos"][0] * 2, attributes["pos"][1]))
    
    elif com[0] == "faker":
        fakeClientWriter.write(data[6:]+b"\n")
    
    elif com[0] == "sendesc":
        a = codecs.escape_decode(data[8:])
        print(a[0])
        fakeClientWriter.write(a[0]+b"\n")
    
    elif com[0] == "particles" and len(com) > 1:
        if com[1] == "watch" and len(com) > 2:
            if "particlewatch" in attributes:
                pass
            else:
                attributes["particlewatch"] = [com[2], 0]
                
                async def spinner():
                    if not os.path.isfile(attributes["particlewatch"][0]):
                        return
                    
                    mtime = os.stat(attributes["particlewatch"][0]).st_mtime
                    if mtime <= attributes["particlewatch"][1]:
                        return
                    
                    attributes["particlewatch"][1] = mtime
                    
                    try:
                        with open(attributes["particlewatch"][0], "r") as f:
                            particle = libfurc.particles.Particles.loadsTxt(f.read())
                        fakeClientWriter.write(
                            b"]I"
                            + libfurc.base.b220encode(attributes["pos"][0], 2)
                            + libfurc.base.b220encode(attributes["pos"][1], 2)
                            + libfurc.base.b220encode(0, 2)
                            + libfurc.base.b220encode(0, 2)
                            + particle.dumpsMessage()
                            + b"\n"
                        )
                        
                    except Exception as e:
                        await printtb(fakeClientWriter)
                
                attributes["particlewatch"].append(Timer(0.25, spinner))
                await sendMessage(fakeClientWriter, "Watching particles " + attributes["particlewatch"][0])
        
        elif com[1] == "stop":
            if "particlewatch" not in attributes:
                pass
            else:
                attributes["particlewatch"][2].cancel()
                await sendMessage(fakeClientWriter, "Stopped watching particles " + attributes["particlewatch"][0])
                attributes.pop("particlewatch")
        
        elif com[1] == "play" and len(com) > 1:
            try:
                with open(com[2], "r") as f:
                    particle = libfurc.particles.Particles.loadsTxt(f.read())
                fakeClientWriter.write(
                    b"]I"
                    + libfurc.base.b220encode(attributes["pos"][0], 2)
                    + libfurc.base.b220encode(attributes["pos"][1], 2)
                    + libfurc.base.b220encode(0, 2)
                    + libfurc.base.b220encode(0, 2)
                    + particle.dumpsMessage()
                    + b"\n"
                )
            except Exception as e:
                await printtb(fakeClientWriter)
        
        elif com[1] == "playcache" and len(com) > 1:
            try:
                with open("/home/felix/Documents/Furcadia/script/particles/"+com[2]+".vxn", "rb") as f:
                    particle = libfurc.particles.Particles.loadsVXN(f.read())
                fakeClientWriter.write(
                    b"]I"
                    + libfurc.base.b220encode(attributes["pos"][0], 2)
                    + libfurc.base.b220encode(attributes["pos"][1], 2)
                    + libfurc.base.b220encode(0, 2)
                    + libfurc.base.b220encode(0, 2)
                    + particle.dumpsMessage()
                    + b"\n"
                )
            except Exception as e:
                await printtb(fakeClientWriter)
    
    elif com[0] == "butler":
        await sendMessage(fakeClientWriter, "* Holding: {}; Standing: {}".format(*attributes["butler"]))
    
    elif com[0] == "bbuddyjoke":
        await client.send(b'"'+random.choice(BBuddyJokes).encode())
    
    elif com[0] == "spinnage" and len(com) > 1:
        if com[1] == "start":
            if "spinnage" in attributes:
                pass
            else:
                async def spinner():
                    await client.send(b">")
                attributes["spinnage"] = Timer(1.0, spinner)
        
        elif com[1] == "stop":
            if "spinnage" not in attributes:
                pass
            else:
                attributes["spinnage"].cancel()
                attributes.pop("spinnage")
        
    elif com[0] == "digocycle" and len(com) > 1:
        if com[1] == "start":
            if "digocycle" in attributes:
                pass
            else:
                async def spinner():
                    await client.send(b"nextdigo")
                speed = 1.0
                if len(com) > 2:
                    speed = float(com[2])
                attributes["digocycle"] = Timer(speed, spinner)
        
        elif com[1] == "stop":
            if "digocycle" not in attributes:
                pass
            else:
                attributes["digocycle"].cancel()
                attributes.pop("digocycle")
        
    elif com[0] == b"antiidle" and len(com) > 1:
        if com[1] == "start":
            if "antiidle" in attributes:
                pass
            else:
                async def spinner():
                    await client.send(b">")
                    await client.send(b"<")
                    await client.send(b"unafk")
                attributes["antiidle"] = Timer(60.0, spinner)
                
        elif com[1] == "stop":
            if "antiidle" not in attributes:
                pass
            else:
                attributes["antiidle"].cancel()
                attributes.pop("antiidle")
    
    elif com[0] == "gloamr" and len(com) > 1:
        if com[1] == "start":
            if "gloamr" in attributes:
                pass
            else:
                async def spinner():
                    i = 0
                    cycle = [0,1,2,3,2,1,0,-1,-2,-3,-2,-1]
                    while True:
                        await client.send("gloam {}".format(cycle[i]).encode())
                        i += 1
                        if i >= len(cycle):
                            i = 0
                        await asyncio.sleep(1.0)
                attributes["gloamr"] = Timer(1.0, spinner)
                
        elif com[1] == "stop":
            if "gloamr" not in attributes:
                pass
            else:
                attributes["gloamr"].cancel()
                attributes.pop("gloamr")
        
    
    elif com[0] == "colorr" and len(com) > 1:
        if com[1] == "start":
            if "colorr" in attributes:
                pass
            else:
                async def spinner():
                    print("STARTING WITH MODE", attributes["colorrmode"])
                    def colFunc(cmin, cmax, table = None):
                        if attributes["colorrmode"] == 0:
                            return random.randint(cmin, cmax)
                        elif attributes["colorrmode"] == 1:
                            t = abs(math.sin(time.time() / 22.5))
                            c = math.floor(t * len(ctable[table]))
                            if ctable[table][c] <= cmax-cmin:
                                return cmin+ctable[table][c]
                            i = 1
                            while True:
                                if c - i > 0:
                                    if cmin + ctable[table][c - i] > cmin:
                                        return cmin + ctable[table][c - i]
                                    
                                if c + i < len(ctable[table]):
                                    if cmin + ctable[table][c + i] <= cmax:
                                        return cmin + ctable[table][c + i]
                                
                                if c - i <= 0 and c + i >= len(ctable[table]):
                                    return cmin
                                i += 1
                                
                                
                    while True:
                        # `chcol w%%=/I7;;:?#:$#
                        # w############$#
                        # w;;O@J@@@@@;@$#
                        choice = bytes([
                            119, # w
                            colFunc(35, 59, 1), # ;
                            colFunc(35, 59, 1), # ;
                            colFunc(35, 79, 0), # O
                            colFunc(35, 64, 3), # @
                            colFunc(35, 74, 2), # J
                            colFunc(35, 64, 4), # @
                            colFunc(35, 64, 4), # @
                            colFunc(35, 64, 4), # @
                            colFunc(35, 64, 4), # @
                            colFunc(35, 64, 4), # @
                            colFunc(35, 59, 1), # ;
                            colFunc(35, 64, 4), # @
                            36, # $
                            39, # 
                            35, # #
                        ])
                        print("SEND", choice)
                        await client.send(b"chcol "+choice)
                        await asyncio.sleep(1)
                attributes["colorrmode"] = 0 if len(com) < 3 else int(com[2])
                attributes["colorr"] = Timer(1.0, spinner)
                
        elif com[1] == "stop":
            if "colorr" not in attributes:
                pass
            else:
                attributes["colorr"].cancel()
                attributes.pop("colorr")
        
    elif com[0] == "peek" and len(com) > 2:
        x, y = int(com[1]), int(com[2])
        fakeClientWriter.write(b"@"+libfurc.base.b95encode(x, 2) + libfurc.base.b95encode(y, 2)+b"\n")
    
    elif com[0] == "aafk":
        await client.send(b"afk")
    
    elif com[0] == "autosummon":
        attributes["autosummon"] = not attributes.get("autosummon", True)
        
        await sendMessage(fakeClientWriter, "* Autosummon is {}".format("on" if attributes["autosummon"] else "off"))
    
    elif com[0] == "show" and len(com) > 1:
        x = int(com[1])
        fakeClientWriter.write(b"%"+libfurc.base.b95encode(x, 2) + b"\n")
    
    elif com[0] == "gloamtest" and len(com) > 4:
        fakeClientWriter.write(b"]O"
            +libfurc.base.b220encode(attributes["furreTracker"].selfID, 4)
            +"{:0>2X}{:0>2X}{:0>2X}".format(int(com[3]),int(com[2]),int(com[1])).encode()
            +libfurc.base.b220encode(int(com[4]), 2)
            +b"\n")
    
    elif com[0] == "mark" and len(com) > 3:
        tile = int(com[1])
        buffer = b"1"
        x = 0
        for i in range(0, len(com)-2, 2):
            buffer += libfurc.base.b220encode(int(com[2+i]) // 2, 2) \
                    + libfurc.base.b220encode(int(com[3+i]), 2) \
                    + libfurc.base.b220encode(tile, 2)
            x += 1
        fakeClientWriter.write(buffer + b"\n")
        await sendMessage(fakeClientWriter, "* Marked {} locations".format(x))
    
    elif com[0] == "f" and len(com) > 2:
        what, value = int(com[1]), int(com[2])
        result = ", ".join(["({},{})".format(*i) for i in attributes["objTracker"].find(what, value)])
        await sendMessage(fakeClientWriter, "{} is at: {}".format(value, result))
    
    elif com[0] == "record" and len(com) > 1:
        if com[1] == "start":
            await sendMessage(fakeClientWriter, "* Recording inputs.")
            attributes["recording"] = []
            attributes["recordInputs"] = True
        
        elif com[1] == "end":
            attributes["recordInputs"] = False
            await sendMessage(fakeClientWriter, "* Recording ended.")
        
        elif com[1] == "list":
            result = []
            for i in attributes.get("recording", []):
                if i in recordables:
                    result.append(recordables[i])
                else:
                    result.append(i.decode())
            await sendMessage(fakeClientWriter, "* Recorded inputs: {}".format(", ".join(result)))
        
        elif com[1] == "play":
            attributes["recordInputs"] = False
            delay = 1
            if len(com) > 2:
                delay = float(com[2])
            
            if attributes.get("recordplayer", None) != None:
                attributes["recordplayer"].cancel()
            
            async def player():
                for step in attributes["recording"]:
                    await client.send(step)
                    await asyncio.sleep(delay)
                await sendMessage(fakeClientWriter, "* Playback finished.")
                return False
            
            attributes["recordplayer"] = Timer(1, player)
            await sendMessage(fakeClientWriter, "* Playing...")
        
        elif com[1] == "loop":
            attributes["recordInputs"] = False
            delay = 1
            if len(com) > 2:
                delay = float(com[2])
            
            if attributes.get("recordplayer", None) != None:
                attributes["recordplayer"].cancel()
            
            async def player():
                if len(attributes["recording"]) == 0:
                    return
                while True:
                    for step in attributes["recording"]:
                        await client.send(step)
                        await asyncio.sleep(delay)
            
            attributes["recordplayer"] = Timer(1, player)
            await sendMessage(fakeClientWriter, "* Playing...")
        
        elif com[1] == "stop":
            if attributes.get("recordplayer", None) != None:
                attributes["recordplayer"].cancel()
            
            await sendMessage(fakeClientWriter, "* Stopped.")
        
        elif com[1] == "clear":
            attributes["recording"] = []
            await sendMessage(fakeClientWriter, "* Cleared...")
        
        elif com[1] == "save" and len(com) > 2:
            with open(com[2], "wb") as f:
                f.write(b"\n".join(attributes["recording"]))
            await sendMessage(fakeClientWriter, "* Saved...")
        
        elif com[1] == "load" and len(com) > 2:
            with open(com[2], "rb") as f:
                attributes["recording"] = f.read().split(b"\n")
            await sendMessage(fakeClientWriter, "* Loaded...")



class FurreTracker:
    def __init__(self, client):
        self.client = client
        self.furres = {}
        self.DSTarget = None
        self.dsAddon = None
        self.selfID = 0
        self.client.hook("Dream", self.Dream)
        self.client.hook("FurreArrive", self.FurreArrive)
        self.client.hook("HideAvatar", self.HideAvatar)
        self.client.hook("MoveAvatar", self.MoveAvatar)
        self.client.hook("RemoveAvatarID", self.RemoveAvatar)
        self.client.hook("RemoveAvatar", self.RemoveAvatar)
        self.client.hook("AnimateAvatar", self.MoveAvatar)
        self.client.hook("SpawnAvatar", self.SpawnAvatar)
        self.client.hook("DSEvent", self.DSEvent)
        self.client.hook("DSEventAddon", self.DSEventAddon)
    
    async def Dream(self, *args):
        for item in list(self.furres.keys()):
            self.furres.pop(item)
    
    async def FurreArrive(self, fuid, xy, direction, shape, *args):
        if fuid not in self.furres:
            self.furres[fuid] = {
                "x": 0, "y": 0, "d": 0,
                "o": -1,
                "c": -1,
                "e": -1,
                "l": None,
                "name": b"unknown"
            }
        self.furres[fuid]["x"] = xy[0]
        self.furres[fuid]["y"] = xy[1]
        self.furres[fuid]["d"] = direction
    
    async def HideAvatar(self, fuid, xy, *args):
        if fuid not in self.furres:
            self.furres[fuid] = {
                "x": 0, "y": 0, "d": 0,
                "o": -1,
                "c": -1,
                "e": -1,
                "l": None,
                "name": b"unknown"
            }
            
        self.furres[fuid]["x"] = xy[0]
        self.furres[fuid]["y"] = xy[1]
    
    async def RemoveAvatar(self, fuid, *args):
        if fuid in self.furres:
            self.furres.pop(fuid)
    
    async def MoveAvatar(self, fuid, xy, direction, shape, *args):
        if fuid not in self.furres:
            self.furres[fuid] = {
                "x": 0, "y": 0, "d": 0,
                "o": -1,
                "c": -1,
                "e": -1,
                "l": None,
                "name": b"unknown"
            }
        self.furres[fuid]["x"] = xy[0]
        self.furres[fuid]["y"] = xy[1]
        self.furres[fuid]["d"] = direction
    
    async def SpawnAvatar(self, fuid, xy, direction, shape, name, colors, *args):
        if fuid not in self.furres:
            self.furres[fuid] = {
                "x": 0, "y": 0, "d": 0,
                "o": -1,
                "c": -1,
                "e": -1,
                "l": None,
                "name": b"unknown"
            }
        self.furres[fuid]["x"] = xy[0]
        self.furres[fuid]["y"] = xy[1]
        self.furres[fuid]["d"] = direction
        self.furres[fuid]["l"] = colors
        self.furres[fuid]["name"] = name
    
    async def DSEventAddon(self, a):
        self.dsAddon = a
    
    async def DSEvent(self, selfTrigger, a):
        if selfTrigger:
            self.selfID = self.dsAddon["userID"]
        
        if self.dsAddon and self.dsAddon["userID"] != 0:
            fuid = self.dsAddon["userID"]
            if self.dsAddon["moveFlag"] == 1:
                xy = a["to"]
            else:
                xy = a["from"]
            
            if fuid not in self.furres:
                self.furres[fuid] = {
                    "x": 0, "y": 0, "d": 0,
                    "o": -1,
                    "c": -1,
                    "e": -1,
                    "l": None,
                    "name": b"unknown"
                }
            
            self.furres[fuid]["d"] = self.dsAddon["facingDir"]
            self.furres[fuid]["x"] = xy[0]
            self.furres[fuid]["y"] = xy[1]
            self.furres[fuid]["o"] = self.dsAddon["objPaws"]
            self.furres[fuid]["c"] = self.dsAddon["triggererCookies"]
            self.furres[fuid]["e"] = self.dsAddon["entryCode"]
    
    def __del__(self):
        self.client.off("Dream", self.Dream)
        self.client.off("FurreArrive", self.FurreArrive)
        self.client.off("HideAvatar", self.HideAvatar)
        self.client.off("MoveAvatar", self.MoveAvatar)
        self.client.off("RemoveAvatarID", self.RemoveAvatar)
        self.client.off("RemoveAvatar", self.RemoveAvatar)
        self.client.off("AnimateAvatar", self.MoveAvatar)
        self.client.off("SpawnAvatar", self.SpawnAvatar)
        self.client.off("DSEvent", self.DSEvent)
        self.client.off("DSEventAddon", self.DSEventAddon)

class VarTracker:
    def __init__(self, client):
        self.client = client
        self.vars = {}
        self.stack = []
        self.client.hook("Dream", self.Dream)
        self.client.hook("DSVariableStack", self.DSVariableStack)
        self.client.hook("SetVariables", self.SetVariables)
    
    async def Dream(self, *args):
        for item in list(self.vars.keys()):
            self.vars.pop(item)
    
    async def DSVariableStack(self, stack):
        self.stack = stack
    
    def popStack(self):
        if len(self.stack) == 0:
            return 0
        else:
            return self.stack.pop(0)
    
    async def SetVariables(self, a):
        for i in a:
            self.vars[i] = a[i]
    
    def __del__(self):
        self.client.off("Dream", self.Dream)
        self.client.off("DSVariableStack", self.DSVariableStack)
        self.client.off("SetVariables", self.SetVariables)

class ObjTracker:
    FLOOR = 0
    OBJECT = 1
    WALL = 2
    REGION = 3
    EFFECT = 4
    SFX = 5
    AMBIENT = 6
    MAX = 7
    def __init__(self, client):
        self.client = client
        self.tiles = {}
        self.client.hook("Dream", self.Dream)
        self.client.hook("SetRegion", self.SetRegion)
        self.client.hook("SetEffect", self.SetEffect)
        self.client.hook("SetWall", self.SetWall)
        self.client.hook("SetFloor", self.SetFloor)
        self.client.hook("SetObject", self.SetObject)
        self.client.hook("SetSFX", self.SetSFX)
        self.client.hook("SetAmbient", self.SetAmbient)
    
    def set(self, where, what, value):
        if where not in self.tiles:
            self.tiles[where] = [None]*self.MAX
        self.tiles[where][what] = value
    
    def get(self, where, what):
        if where not in self.tiles:
            return None
        return self.tiles[where][what]
    
    def find(self, what, value):
        result = []
        for tile in self.tiles:
            if self.tiles[tile][what] == value:
                result.append(tile)
        return result
    
    async def Dream(self, *args):
        for item in list(self.tiles.keys()):
            self.tiles.pop(item)
    
    async def SetFloor(self, a):
        for i in range(len(a)):
            self.set(a[i]["pos"], self.FLOOR, a[i]["id"])
    
    async def SetObject(self, a):
        for i in range(len(a)):
            self.set(a[i]["pos"], self.OBJECT, a[i]["id"])
    
    async def SetWall(self, a):
        for i in range(len(a)):
            self.set(a[i]["pos"], self.WALL, a[i]["id"])
    
    async def SetRegion(self, a):
        for i in range(len(a)):
            self.set(a[i]["pos"], self.REGION, a[i]["id"])
    
    async def SetEffect(self, a):
        for i in range(len(a)):
            self.set(a[i]["pos"], self.EFFECT, a[i]["id"])
    
    async def SetSFX(self, a):
        for i in range(len(a)):
            self.set(a[i]["pos"], self.SFX, a[i]["id"])
    
    async def SetAmbient(self, a):
        for i in range(len(a)):
            self.set(a[i]["pos"], self.AMBIENT, a[i]["id"])
    
    def __del__(self):
        self.client.off("Dream", self.Dream)
        self.client.off("SetRegion", self.SetRegion)
        self.client.off("SetEffect", self.SetEffect)
        self.client.off("SetWall", self.SetWall)
        self.client.off("SetFloor", self.SetFloor)
        self.client.off("SetObject", self.SetObject)
        self.client.off("SetSFX", self.SetSFX)
        self.client.off("SetAmbient", self.SetAmbient)

rSummonReq = re.compile(r"^<font color='query'><name shortname='([^']+)'>(?:[^<]+)</name> requests permission to join your company\. To accept the request, <a href='command://summon'>click here</a> or type `summon and press &lt;enter&gt;\.</font>$", re.MULTILINE | re.IGNORECASE)


rWhichHeimdall = re.compile(r"^<img src='fsh://system\.fsh:86' /> You are connected to Heimdall \[(?P<port>[0-9]+):(?P<server>[0-9+]+)\] \(QTEMP (?P<qterp>[0-9]+)\). There are (?P<players>[0-9]+) players on this Heimdall, of which you are player index (?P<player>[0-9]+) with globalid (?P<globalid>[0-9]+), and you are on map (?P<map>[0-9]+)(?:. Heimdall is running version: (?P<version>[a-f0-9]+))?", re.MULTILINE | re.IGNORECASE)
rWhichHorton = re.compile(r"^<img src='fsh://system\.fsh:86' /> You are connected to Horton \[(?P<name>[a-z0-9]+)@(?P<host>[a-z0-9._-]+):(?P<port>[0-9]+)\] \(QTEMP (?P<qtemp>[0-9]+)\). There are (?P<players>[0-9]+) players in this horton, of which you are the player index (?P<player>[0-9]+) with global id (?P<globalid>[0-9]+). (?P<tag>(?:It's a beautiful day in Gosford Park\.)|[^.]+.) (?:Horton is running version: (?P<version>[a-f0-9]+))?", re.MULTILINE | re.IGNORECASE)
rWhichTribble = re.compile(r"^<img src='fsh://system\.fsh:86' /> You are connected to tribble \[(?P<port>[0-9]+)\] \(QTEMP (?P<qtemp>[0-9]+)\). There are (?P<players>[0-9]+) players on this tribble, of which you are player index (?P<player>[0-9]+) with global id (?P<globalid>[0-9]+). You are exactly at \((?P<x>[0-9]+),(?P<y>[0-9]+)\). This tribble feels like (?P<map>[a-z0-9-_]+)::(?P<checksum>[0-9]+)(?: and is running version: (?P<version>[a-f0-9]+))?", re.MULTILINE | re.IGNORECASE)

rPlayerMessage = re.compile(r"^(<font color='shout'>{S} )?<name shortname='(?P<shortname>[^']+)'>(?P<realname>[^<]+)</name>: (?P<message>.*)(</font>)?$", re.IGNORECASE)
rPlayerWhisper = re.compile(r"^<font color='whisper'>\[ <name shortname='(?P<shortname>[^']+)' src='whisper-from'>(?P<realname>[^<]+)</name> whispers, \"(?P<message>.*)\" to you. ]</font>$", re.MULTILINE | re.IGNORECASE)

MSG_BLOCK = (
    b"(<font color='success'>With force of will you suppress your Gloaming, keeping it at bay, for now.</font>",
    b"(<font color='success'>The Gloaming rises up from within, affecting your entire being.  To return to normal, <a href='command://gloam 0'>click here</a> or type `gloam 0 and press enter.</font>",
    b"]gupdate.exe",
    b"]hupdate.exe",
)

async def attachHooks(client, toServer, toClient, attributes):
    client.recordInputs = False
    client.recording = []
    await sendMessage(toClient, "* MITM agent attached")
    attributes["furreTracker"] = FurreTracker(client)
    attributes["furreList"] = attributes["furreTracker"].furres
    attributes["varTracker"] = VarTracker(client)
    attributes["varList"] = attributes["varTracker"].vars
    attributes["objTracker"] = ObjTracker(client)
    attributes["pos"] = (0,0)
    attributes["butler"] = [0,0]
    attributes["dream"] = {
        "default": True,
        "name": "unknown",
        "checksum": 0,
        "modern": False
    }
    
    @client.on("*")
    async def test(name, *args):
        if name == "Raw":
            return
        if name == "SetVariables":
            return
        if name == "RegionFlags":
            return
        print(name, *args)
    
    @client.on("Raw")
    async def raw(data):
        if data in MSG_BLOCK:
            return
        toClient.write(data)
        toClient.write(b"\n")
        await toClient.drain()
    
    @client.on("PrefixLine")
    async def Prefix(data):
        with open("./data/chatlog.txt", "ab+") as f:
            f.write(data)
        
    @client.on("ButlerPaws")
    async def ButlerPaws(data):
        attributes["butler"][0] = data
    
    @client.on("ButlerFeet")
    async def ButlerFeet(data):
        attributes["butler"][1] = data
    
    @client.on("MoveCamera")
    async def MoveCamera(data):
        attributes["pos"] = data["to"]
    
    @client.on("Dream")
    async def Dream(default, name, checksum, modern):
        attributes["dream"]["default"] = default
        attributes["dream"]["name"] = name.decode()
        attributes["dream"]["checksum"] = int(checksum.decode())
        attributes["dream"]["modern"] = modern
        
    @client.on("Particles")
    async def Particles(pos, offset, data):
        p = data.dumpsVXN()
        h = hashlib.md5(p).hexdigest()
        pp = "./data/particles/{}.vxn".format(h)
        if not os.path.isfile(pp):
            with open(pp, "wb+") as f:
                f.write(p)
        
        with open("./data/particlelog.txt", "a+") as f:
            f.write("{}: pos= {},{}; offset={},{}\n".format(h, *pos, *offset))
    
    @client.on("Message")
    async def Message(data):
        #TODO: add extended data to which
        with open("./data/chatlog.txt", "ab+") as f:
            f.write(data + b"\n")
            
            try:
                if attributes.get("autosummon", True):
                    test = rSummonReq.match(data.decode("latin-1"))
                    if test:
                        await client.send(("summon "+test.group(1)).encode())
            except Exception as e:
                await printtb(toClient)
            
            #Player commands
            try:
                whisper = False
                test = rPlayerMessage.match(data.decode("latin-1"))
                if not test:
                    test = rPlayerWhisper.match(data.decode("latin-1"))
                    whisper = True
                
                if test:
                    msg = test.group("message")
                    who = test.group("shortname")
                    who2 = test.group("realname")
                    if whisper:
                        if msg == ".where":
                            fuid = None
                            for entry in attributes["furreList"]:
                                if attributes["furreList"][entry]["name"].decode("latin-1") == who2:
                                    fuid = entry
                                    break
                            if fuid:
                                furre = attributes["furreList"][entry]
                                await client.send(("wh "+who+" You are player {} at ({},{}) facing {}. You entered with entry code {}, have {} cookies, and are holding item {}.".format(
                                    fuid,
                                    furre["x"],
                                    furre["y"],
                                    ["SW", "SE", "NW", "NE"][furre["d"]] if 0 <= furre["d"] <= 3 else "INVALID DIRECTION",
                                    "UNKNOWN" if furre["e"] == -1 else furre["e"],
                                    "UNKNOWN" if furre["c"] == -1 else furre["c"],
                                    "UNKNOWN" if furre["o"] == -1 else furre["o"],
                                )).encode())
                            else:
                                await client.send(("wh "+who+" I don't have information on you yet, please wait for it to populate!").encode())
                        elif msg == ".fortune":
                            await client.send(("wh "+who+" {}".format(random.choice(Fortunes))).encode())
                    else:
                        if msg == ".cookie":
                            await client.send(("\"make-cookie "+who).encode())
                    
            except Exception as e:
                await printtb(toClient)
            
            
            if False: #TODO: detect if I can see this, if not, print it
                try:
                    test = rWhichHeimdall.match(data.decode())
                    if test:
                        await sendMessage(toClient, "<img src='fsh://system.fsh:86' /> You are connected to tribble [{}] (QTEMP ?????). There are {} players on this tribble, of which you are player index ? with global id {}. You are exactly at ({},{}). This tribble feels like {}::{}".format(
                            test.group("map"),
                            len(attributes["furreList"]),
                            test.group("globalid"),
                            attributes["pos"][0], attributes["pos"][1],
                            attributes["dream"]["name"], attributes["dream"]["checksum"]
                        ))
                except Exception as e:
                    await printtb(toClient)

#===============================================================================

async def sendMessage(client, msg):
    if type(msg) == str:
        msg = msg.split("\n")
    
    for line in msg:
        client.write(b"("+line.replace("\n","").encode()+b"\n")
    
    await client.drain()

class Timer:
    def __init__(self, timeout, callback, repeats = 0):
        self._timeout = timeout
        self._callback = callback
        self._repeats = repeats
        self._task = asyncio.ensure_future(self._job())

    async def _job(self):
        while self._repeats > 1 or self._repeats == 0:
            await asyncio.sleep(self._timeout)
            res = await self._callback()
            if res == False:
                break
            if self._repeats == 1:
                break
            if self._repeats > 1:
                self._repeats = self._repeats - 1

    def cancel(self):
        self._task.cancel()
    
    def __del__(self):
        self.cancel()

class Client(libfurc.client.PacketHooks, libfurc.client.Commands):
    def __init__(self, server = None):
        super().__init__()
        self.reader = None
        self.writer = None
    
    async def attach(self, reader, writer, fakeClientWriter):
        self.reader = reader
        self.writer = writer
        self.client = fakeClientWriter
    
    async def disconnect(self):
        writer.close()
        await writer.wait_closed()
        self.reader = None
        self.writer = None
    
    async def send(self, data):
        if self.connected:
            self.writer.write(data)
            await self.writer.drain()
            return True
        return False
    
    def command(self, data):
        if type(data) == str:
            data = data.encode()
        return self.send(data + b"\n")
    
    @property
    def connected(self):
        if self.reader == None or self.writer == None:
            return False
        return True
    
    #Actual read loop, it is designed to be it's own task
    async def run(self):
        while self.connected:
            data = await self.reader.readline()
            
            if not data: #None = Disconnected
                break
            
            if data[-1] != 10: #No EOL means incomplete stream + disconnected
                break
            
            data = data[:-1] #Strip EOL
            
            if len(data) == 0: #If empty, ignore
                continue
            
            try:
                await self.handlePacket(data)
            except Exception as e:
                tb = traceback.format_exc().strip("\n")
                try:
                    await sendMessage(self.client, ["<font color=\"error\">{}</font>".format(i) for i in tb.split("\n")])
                except Exception as ee:
                    print(ee)
                    pass
            
        #We are out of the loop! Presume Disconnected!
        self.reader = None
        self.writer = None

class FakeIO:
    def __init__(self):
        self.buffer = b""
        self.readable = True
    
    async def write(self, data):
        if self.buffer == None:
            return None
        self.buffer += data
    
    async def read(self, l = None):
        if self.buffer == None:
            return None
        while not self.readable:
            if self.buffer == None:
                return None
            await asyncio.sleep(0.01)
        
        self.readable = False
        
        if l == None:
            l = len(self.buffer)
        
        result = b""
        while l < len(result):
            if self.buffer == None:
                return None
            if len(self.buffer) > 0:
                needed = l - len(result)
                result += self.buffer[:needed]
                self.buffer = self.buffer[needed:]
            await asyncio.sleep(0.01)
        
        self.readable = True
        return result
    
    async def readline(self):
        if self.buffer == None:
            return None
        while not self.readable:
            if self.buffer == None:
                return None
            await asyncio.sleep(0.01)
        
        self.readable = False
        
        result = b""
        while True:
            if self.buffer == None:
                return None
            if len(self.buffer) > 0:
                for i in range(len(self.buffer)):
                    if self.buffer[i] == 10:
                        break
                i += 1
                result += self.buffer[:i]
                self.buffer = self.buffer[i:]
                if result[-1] == 10:
                    break
            await asyncio.sleep(0.01)
        
        self.readable = True
        return result
    
    def close(self):
        self.buffer = None

#===============================================================================
#mitm code
#===============================================================================
def mitm_header_read(data):
    opcode = libfurc.base.b95decode(data[0:2])
    dlen = libfurc.base.b95decode(data[2:5])
    return opcode, dlen

def mitm_header_write(opcode, dlen):
    return libfurc.base.b95encode(opcode, 2) + libfurc.base.b95encode(dlen, 3)

class WriterProxy:
    def __init__(self, dest, direction):
        self.real = dest
        self.direction = direction
    
    def write(self, data):
        if not self.real:
            return
        for line in data.split(b"\n"):
            line += b"\n"
            self.real.write(mitm_header_write(self.direction, len(line))+line)
    
    async def drain(self):
        if not self.real:
            return
        await self.real.drain()
    
    def close():
        self.real = None

FLAG_BLOCK_CLIENT = 1
FLAG_BLOCK_SERVER = 2
async def main(character = None):
    attributes = {}
    reader, writer = await asyncio.open_connection('127.0.0.1', 6501)
    writer.write(mitm_header_write(3, 1)+b"\n")
    writer.write(mitm_header_write(5, 3)+libfurc.base.b95encode(FLAG_BLOCK_SERVER, 2)+b"\n")
    await writer.drain()
    
    client = None
    connected = False
    connectionID = None
    fakeServerWriter = None
    fakeClientWriter = None
    fakeReader = None
    task = None
    while True:
        try:
            try:
                data = await asyncio.wait_for(reader.readline(), 30)
            except asyncio.TimeoutError:
                continue
            
            if data == None:
                break
            
            opcode, dlen = mitm_header_read(data)
            data = data[5:]

            if dlen != len(data):
                print("Length mismatch: {} {}".format(dlen, len(data)))
                continue

            if data[-1:] != b"\n":
                print("Missing new line at end of data")
                continue
            
            data = data[:-1] #Remove newline
            
            if opcode == 3:
                if not client:
                    channels = data.split(b" ")
                    found = False
                    for channel in channels:
                        channel = channel.split(b":",1)
                        if len(channel) == 2 and (character == None or channel[1].decode() == character):
                            connectionID = channel[0]
                            writer.write(mitm_header_write(4, len(channel[0])+1)+channel[0]+b"\n")
                            await writer.drain()
                            found = True
                            break
                    if not found:
                        exit()
                    
            elif opcode == 4:
                if data == b"ok":
                    attributes.clear()
                    print("Attached to connection {}".format(connectionID.decode()))
                    connected = True
                    fakeServerWriter = WriterProxy(writer, 1) #Send to SERVER
                    fakeClientWriter = WriterProxy(writer, 0) #Send to Client
                    fakeReader = FakeIO()
                    client = Client()
                    await attachHooks(client, fakeServerWriter, fakeClientWriter, attributes)
                    await client.attach(fakeReader, fakeServerWriter, fakeClientWriter)
                    task = asyncio.create_task(client.run())
                else:
                    print("Failed to attach to connection {}: {}".format(connectionID.decode(), data.decode()))
                    connected = False
                    connectionID = b""

            elif opcode == 0:
                #From server
                if fakeReader:
                    await fakeReader.write(data+b"\n")
            
            elif opcode == 1:
                #From client
                if client:
                    await handleClientMessage(client, data, fakeServerWriter, fakeClientWriter, attributes)
            
            elif opcode == 2:
                print("Client {} disconnected".format(data.decode()))
                if data == connectionID:
                    if client:
                        fakeReader.close()
                        #fakeWriter.close()
                        fakeReader = None
                        fakeWriter = None
                        client = None
                    print("Attached connection {} disconnected".format(connectionID.decode()))
            elif opcode == 5:
                print("Proxy flags set", libfurc.base.b95decode(data[0:2]))
            elif opcode == 6:
                if not connected:
                    print("Client {} connected".format(data.decode()))
                    writer.write(mitm_header_write(4, len(data)+1)+data+b"\n")
                    await writer.drain()
            
        except Exception as e:
            tb = traceback.format_exc().strip("\n")
            try:
                await sendMessage(fakeClientWriter, ["<font color=\"error\">{}</font>".format(i) for i in tb.split("\n")])
            except Exception as ee:
                print(ee)
                pass
            print("-"*80)
            print(tb)
            print("-"*80)
    if "gui" in attributes and attributes["gui"]:
        gui.close()

async def main_loop():
    import argparse
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument("-c", "--character", default=None,
                        help="Character to attach to")

    args = parser.parse_args()
    
    while True:
        await main(args.character)
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main_loop())
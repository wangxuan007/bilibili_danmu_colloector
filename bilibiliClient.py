import asyncio
import aiohttp
import xml.dom.minidom
import random
import json
from struct import *
import json
import re
import time

import logging
logger = logging.getLogger('bili')

class bilibiliClient():
    def __init__(self, roomid, lock, commentq,  numq):
        self._CIDInfoUrl = 'http://live.bilibili.com/api/player?id=cid:'
        self._roomId = 0
        self._ChatPort = 788
        self._protocolversion = 1
        self._reader = 0
        self._writer = 0
        self.connected = False
        self._UserCount = 0
        self._ChatHost = 'livecmt-1.bilibili.com'

        self._roomId = roomid
        self.lock = lock
        self.commentq = commentq
        self.numq = numq


    async def connectServer(self):
        #print ('正在进入房间。。。。。')
        try:
            with aiohttp.ClientSession() as s:
                async with s.get('http://live.bilibili.com/' + str(self._roomId)) as r:
                    html = await r.text()
                    m = re.findall(r'ROOMID\s=\s(\d+)', html)
                    ROOMID = m[0]
                self._roomId = int(ROOMID)
                async with s.get(self._CIDInfoUrl + ROOMID) as r:
                    xml_string = '<root>' + await r.text() + '</root>'
                    dom = xml.dom.minidom.parseString(xml_string)
                    root = dom.documentElement
                    server = root.getElementsByTagName('server')
                    self._ChatHost = server[0].firstChild.data
        except:
            return


        reader, writer = await asyncio.open_connection(self._ChatHost, self._ChatPort)
        self._reader = reader
        self._writer = writer
        #print ('链接弹幕中。。。。。')
        if (await self.SendJoinChannel(self._roomId) == True):
            self.connected = True
            print ('进入房间成功。。。。。%s' % self._roomId)
            logging.debug('进入房间成功。。。。。%s' % self._roomId)
            #print ('链接弹幕成功。。。。。')
            try:
                await self.ReceiveMessageLoop()
            except: # 发生异常直接退出该 task
                return

    async def HeartbeatLoop(self):
        while self.connected == False:
            await asyncio.sleep(0.5)

        try:
            while self.connected == True:
                await self.SendSocketData(0, 16, self._protocolversion, 2, 1, "")
                await asyncio.sleep(30)
        except: # 发生异常直接退出该 task
            return


    async def SendJoinChannel(self, channelId):
        self._uid = (int)(100000000000000.0 + 200000000000000.0*random.random())
        body = '{"roomid":%s,"uid":%s}' % (channelId, self._uid)
        await self.SendSocketData(0, 16, self._protocolversion, 7, 1, body)
        return True


    async def SendSocketData(self, packetlength, magic, ver, action, param, body):
        bytearr = body.encode('utf-8')
        if packetlength == 0:
            packetlength = len(bytearr) + 16
        sendbytes = pack('!IHHII', packetlength, magic, ver, action, param)
        if len(bytearr) != 0:
            sendbytes = sendbytes + bytearr
        self._writer.write(sendbytes)
        await self._writer.drain()


    async def ReceiveMessageLoop(self):
        while self.connected == True:
            tmp = await self._reader.read(4)
            expr, = unpack('!I', tmp)
            tmp = await self._reader.read(2)
            tmp = await self._reader.read(2)
            tmp = await self._reader.read(4)
            num, = unpack('!I', tmp)
            tmp = await self._reader.read(4)
            num2 = expr - 16

            if num2 != 0:
                num -= 1
                if num==0 or num==1 or num==2:
                    tmp = await self._reader.read(4)
                    num3, = unpack('!I', tmp)
                    self._UserCount = num3

                    item = [self._roomId, num3, int(time.time())]
                    if self.lock.acquire():
                        self.numq.append(item)
                        self.lock.release()
                    continue
                elif num==3 or num==4:
                    tmp = await self._reader.read(num2)
                    # strbytes, = unpack('!s', tmp)
                    try: # 为什么还会出现 utf-8 decode error??????
                        messages = tmp.decode('utf-8')
                    except:
                        continue
                    self.parseDanMu(messages)
                    continue
                elif num==5 or num==6 or num==7:
                    tmp = await self._reader.read(num2)
                    continue
                else:
                    if num != 16:
                        tmp = await self._reader.read(num2)
                    else:
                        continue

    def parseDanMu(self, messages):
        try:
            dic = json.loads(messages)
        except: # 有些情况会 jsondecode 失败，未细究，可能平台导致
            return
        cmd = dic['cmd']
        if cmd == 'LIVE':
            #print ('直播开始。。。')
            return
        if cmd == 'PREPARING':
            #print ('房主准备中。。。')
            return
        if cmd == 'DANMU_MSG':
            commentText = dic['info'][1]
            commentUser = dic['info'][2][1]
            isAdmin = dic['info'][2][2] == '1'
            isVIP = dic['info'][2][3] == '1'

            item = [self._roomId, commentUser, commentText, int(time.time())]
            #print (item)
            if self.lock.acquire():
                self.commentq.append(item)
                self.lock.release()
            return
        if cmd == 'SEND_GIFT':
            # GiftName = dic['data']['giftName']
            # GiftUser = dic['data']['uname']
            # Giftrcost = dic['data']['rcost']
            # GiftNum = dic['data']['num']

            return
        if cmd == 'WELCOME':
            # commentUser = dic['data']['uname']
            return
        return

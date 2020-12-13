import gzip
import json
import requests
import os

from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *

from bs4 import BeautifulSoup
import urllib.request,pathlib


url = 'https://invoice.etax.nat.gov.tw/index.html'
html=requests.get(url)
html.encoding="utf-8"
bs=BeautifulSoup(html.text,'html.parser')

num = []
numN = []
numP = []
data = ''
gNoteList = []

items = bs.find_all('span','t18Red')
for item in items:
    for item2 in item.text.split('、'):
        num.append(item2)

for i in range(0, 7):
    numN.append(num[i])
time = bs.find_all("h2")
timeN = time[1].text

for i in range(7, 14):
    numP.append(num[i])
time = bs.find_all("h2")
timeP = time[3].text

money_str = ['', '', '', '獎金2百元',
             '獎金1千元', '獎金4千元', '獎金1萬元',
             '獎金4萬元', '獎金20萬元', '200萬元', '1,000萬元']
# print(len(money_str))

def whole():
    showdata = ''
    showdata = showdata + "發票兌獎(%s)(可輸入3至8個數字做比對) 條件: /invoice01:+號碼\n\n" %(timeN)
    showdata = showdata + "發票兌獎(%s)(可輸入3至8個數字做比對) 條件: /invoice02:+號碼\n\n" %(timeP)
    showdata = showdata + "公車到站時間 條件: /bus:+公車號碼+空格+公車站牌\n\n"
    showdata = showdata + "記事本-新增 條件: /add:+新增事項\n\n" 
    showdata = showdata + "記事本-刪除 條件: /dele:+刪除事項\n\n" 
    showdata = showdata + "記事本-列表 條件: /total:\n\n"
    showdata = showdata + "購物(PChome) 條件: /buy:+購買品項"
    return showdata

#發票compare
def compareNum(str1, str2, num):
    if len(str1) >= num and len(str2) >= num:
        _str1 = str1[len(str1)-num:]
        _str2 = str2[len(str2)-num:]
        #print("_str1=%s, _str2=%s, num=%d" % (_str1, _str2, num))
        if _str1 == _str2:
            return True
        else:
            False
    return False


# 取得路線 站名 時間
ROUTE_URL = 'https://tcgbusfs.blob.core.windows.net/blobbus/GetRoute.gz'
STOP_URL = 'https://tcgbusfs.blob.core.windows.net/blobbus/GetStop.gz'
EST_URL = 'https://tcgbusfs.blob.core.windows.net/blobbus/GetEstimateTime.gz'

gRouteInfos = []
gStopInfos = []


#下載 
def downloadZipFile(url):
    filename = url.split('/')[-1]
    with open(filename, 'wb') as f:
        r = requests.get(url)
        f.write(r.content)
    return filename

#路線
class cRouteInfo:
    RouteID = 0
    BusName = ''
    departureName = ''
    destinationName = ''

    def __init__(self, _RouteID, _BusName, _departure, _destination):
        self.RouteID = _RouteID
        self.BusName = _BusName
        self.departureName = _departure
        self.destinationName = _destination

    def str(self):
        _str = '%s: %s <-> %s' % (self.BusName, self.departureName, self.destinationName)
        return _str


def getBusName(dict1):
    r_list = []
    BusInfos = dict1.get('BusInfo')
    for info in BusInfos:
        RouteID = int(info.get('Id'))
        BusName = info.get('nameZh')
        departureName = info.get('departureZh')
        destinationName = info.get('destinationZh')
    
        isExist = False
        
        for r in r_list:
            if r.RouteID == RouteID:
                isExist = True
                break
        if isExist == False:
            r_list.append(cRouteInfo(RouteID, BusName, departureName, destinationName))
    return r_list


def initRouteInfoTable():
    dict1 = {}

    # 下載 路線URL
    filename = downloadZipFile(ROUTE_URL)

    # 讀取
    with gzip.open(filename, 'rb') as f:
        dict1 = json.loads(f.read().decode('utf-8'))
    items = getBusName(dict1)

    # 移除 
    os.remove(filename)
    return items

def getRouteInfo(RouteInfos, BusName):
    for info in RouteInfos:
        if info.BusName == BusName:
            return info
    return None

def getRouteInfo2(RouteInfos, RouteID):
    for info in RouteInfos:
        if info.RouteID == RouteID:
            return info
    return None


#站名
class cStopInfo:
    StopID = 0
    StopName = ''
    RouteID = 0
    goBack = ''
    
    def __init__(self, _StopID, _StopName, _RouteID, _goBack):
        self.StopID = _StopID
        self.StopName = _StopName
        self.RouteID = _RouteID
        self.goBack = _goBack

    def str(self):
        _str = '%s' %(self.StopName)
        return _str


def getStop(dict1):
    r_list = []
    BusInfos = dict1.get('BusInfo')
    for info in BusInfos:
        StopID = int(info.get('Id'))
        RouteID = int(info.get('routeId'))
        StopName = info.get('nameZh')
        goBack = info.get('goBack')
        r_list.append(cStopInfo(StopID, StopName, RouteID, goBack))
    return r_list


def initStopInfoTable():
    dict1 = {}
    
    # 下載 站名URL
    filename = downloadZipFile(STOP_URL)

    # 讀取
    with gzip.open(filename, 'rb') as f:
        dict1 = json.loads(f.read().decode('utf-8'))

    items = getStop(dict1)

    # 移除
    os.remove(filename)
    return items


def getStopInfo(StopInfos, RouteID, StopName):
    r_list = []
    for info in StopInfos:
        if info.RouteID != RouteID or info.StopName != StopName:
            continue
        r_list.append(info)
    return r_list

def getStopInfo2(StopInfos, StopID):
    for info in StopInfos:
        if info.StopID == StopID:
            return info
    return None            


#到站時間
class cESTime:
    EstimateTime = 0
    GoBack = 0
    GoDesc = ''
    listESTime = ['', '尚未發車', '交管不停靠', '末班車已過', '今日未營運']

    def __init__(self, _EstimateTime, _GoBack, _GoDesc):
        self.EstimateTime = int(_EstimateTime)
        self.GoBack = int(_GoBack)
        self.GoDesc = _GoDesc

    def str(self):
        _str = '(%s) %s' % (self.getGoBack(), self.getESTime())
        return _str 

    def getESTime(self):
        _str = ''
        if self.EstimateTime > 0:
            _str = '約%d分' % (self.EstimateTime / 60)
        else:
            _str = self.listESTime[abs(self.EstimateTime)]
        return _str

    def getGoBack(self):
        return self.GoDesc


def downloadESTInfos():
    dict1 = {}
    
    # 下載 到站URL
    filename = downloadZipFile(EST_URL)

    # 讀取
    with gzip.open(filename, 'rb') as f:
        dict1 = json.loads(f.read().decode('utf-8'))

    BusInfos = dict1.get('BusInfo')

    # 移除 
    os.remove(filename)
    return BusInfos


def getESTime(ESTInfos, RouteID, StopID):
    global gRouteInfos, gStopInfos

    obj = None
    for info in ESTInfos:
        if info.get('RouteID') != RouteID or info.get('StopID') != StopID:
            continue

        rinfo = getRouteInfo2(gRouteInfos, RouteID)
        sinfo = getStopInfo2(gStopInfos, StopID)
        if rinfo == None or sinfo == None:
            continue

        GoDesc = ''
        if sinfo.goBack == '0':  # 去程
            GoDesc = '往 %s' % (rinfo.destinationName)
        elif sinfo.goBack == '1':  # 返程
            GoDesc = '往 %s' % (rinfo.departureName)
        obj = cESTime(info.get('EstimateTime'), info.get('GoBack'), GoDesc)
        break
    return obj



def initBusInfos():
    global gRouteInfos, gStopInfos

    gRouteInfos = initRouteInfoTable()
    gStopInfos = initStopInfoTable()
    
#     print('%d' %len(gRouteInfos)) #公車數量
#     print('%d' %len(gStopInfos)) #站牌數量

def Total(text):
    showdata = ''
    global gNoteList
    
    
    if text[:6:] == "/help:":
        showdata = whole()
    
    #這月發票
    elif text[:11:] == '/invoice01:' and len(text[11:]) > 2 and len(text[11:]) < 9:
        text = text[11:]
        isMatch = False
        showdata = '可惜沒中獎'
        if len(text) <= 8:
            for n in numN:
                for i in range(8, 2, -1):
                    if compareNum(n, text, i) == False:
                        continue
                    if compareNum(n, text, i) == True:
                        isMatch = True
                    
                    #頭獎
                    if len(text) == i and len(text) != len(n) and n != numN[0] and n != numN[1]: 
#                         print("n=%s, text=%s, i=%d" % (n, text, i))
                        showdata = '最高會中頭獎%s(%s)輸入完整8位數號碼：' %(money_str[8],n)
                        break
                    
                    if n == numN[0]: #特別獎
                        if len(text) == i and len(text) != 8:
                            showdata = '最高會中特別獎%s(%s)輸入完整8位數號碼：' %(money_str[10],n)
                            break
                        if len(n) != i:
                            print("n=%s, text=%s, i=%d" % (n, text, i))
                            showdata = '可惜沒中獎'
                            break
                        showdata = '中獎拉！！！號碼(%s) %s' % (n, money_str[10])
                        break
                    
                    if n == numN[1]: #特獎
                        if len(text) == i and len(text) != 8:
                            showdata = '最高會中特獎%s(%s)輸入完整8位數號碼：' %(money_str[9],n)
                            break
                        if len(n) != i:
                            print("n=%s, text=%s, i=%d" % (n, text, i))
                            showdata = '可惜沒中獎'
                            break
                        showdata = '中獎拉！！！號碼(%s) %s' % (n, money_str[9])
                        break
                        
#                     print("n=%s, text=%s, i=%d" % (n, text, i))
                    showdata = '中獎拉！！！號碼(%s) %s' % (n, money_str[i])
                    break
                
                if isMatch == True:
                    break
    
    #上月發票 同上
    elif text[:11:] == '/invoice02:' and len(text[11:]) > 2 and len(text[11:]) < 9:
        text = text[11:]
        isMatch = False
        showdata = '可惜沒中獎'
        if len(text) <= 8:
            for n in numP:
                for i in range(8, 2, -1):
                    if compareNum(n, text, i) == False:
                        continue
                    if compareNum(n, text, i) == True:
                        isMatch = True
                        
                    if len(text) == i and len(text) != len(n) and n != numP[0] and n != numP[1]:
#                         print("n=%s, text=%s, i=%d" % (n, text, i))
                        showdata = '最高會中頭獎%s(%s)輸入完整8位數號碼：' %(money_str[8],n)
                        break
                    
                    if n == numP[0]:
                        if len(text) == i and len(text) != 8:
                            showdata = '最高會中特別獎%s(%s)輸入完整8位數號碼：' %(money_str[10],n)
                            break
                        if len(n) != i:
                            print("n=%s, text=%s, i=%d" % (n, text, i))
                            showdata = '可惜沒中獎'
                            break
                        showdata = '中獎拉！！！號碼(%s) %s' % (n, money_str[10])
                        break
                    
                    if n == numP[1]:
                        if len(text) == i and len(text) != 8:
                            showdata = '最高會中特獎%s(%s)輸入完整8位數號碼：' %(money_str[9],n)
                            break
                        if len(n) != i:
                            print("n=%s, text=%s, i=%d" % (n, text, i))
                            showdata = '可惜沒中獎'
                            break
                        showdata = '中獎拉！！！號碼(%s) %s' % (n, money_str[9])
                        break
                        
                    print("n=%s, text=%s, i=%d" % (n, text, i))
                    showdata = '中獎拉！！！號碼(%s) %s' % (n, money_str[i])
                    break
                
                if isMatch == True:
                    break
                
    #公車           
    elif text[:5:] == "/bus:":
        global gRouteInfos, gStopInfos
        if gRouteInfos == None or gStopInfos == None or text == '':
            return ''

        ESTInfos = downloadESTInfos()
        
        bus_num_stop = text[5:].split(' ')
        showdata = ''

        test_busname = bus_num_stop[0]
        test_stopname = bus_num_stop[1]
    
        # get the route-info from bus-name 
        rinfo = getRouteInfo(gRouteInfos, test_busname)
        if rinfo != None:
            showdata = rinfo.str()
            # get the stop-info
            sinfos = getStopInfo(gStopInfos, rinfo.RouteID, test_stopname)
            for sinfo in sinfos:
                estime = getESTime(ESTInfos, rinfo.RouteID, sinfo.StopID)
                if estime != None:
                    str1 = sinfo.str() + ':' + estime.str()
                    showdata = showdata + '\n'+ str1
        else:
            showdata = "無此公車"
                    
#記事本        
    elif text[:5:] == "/add:":
        #新增
        text = text[5:]
        gNoteList.append(text)
        showdata = '已新增\n\n'
        snote = ""
        for index in range(len(gNoteList)):
            snote = snote + "%d. %s\n" % (index+1, gNoteList[index])
        showdata = showdata + "total: \n\n%s" % (snote)

    elif text[:6:] == "/dele:":
        #刪除
        index = int(text[6:])-1
        if index < len(gNoteList):
            del gNoteList[index]
            showdata = "已刪除\n\n"
            snote = ""
            for index in range(len(gNoteList)):
                snote = snote + "%d. %s\n" % (index+1, gNoteList[index])
            showdata = showdata + "total: \n\n%s" % (snote)
        else:
            showdata = "找不到該ID的記事"
        
    elif text[:7:] == "/total:": 
        #列表
        snote = ""
        #print(len(gNoteList))
        for index in range(len(gNoteList)):
            snote = snote + "%d. %s\n" % (index+1, gNoteList[index])
        showdata = "total: \n\n%s" % (snote)

    #購物
    elif text[:5:] == "/buy:":
        text = text[5:]
        showdata = 'https://ecshweb.pchome.com.tw/search/v3.3/?q=' + text

    else:
        showdata = '輸入錯誤'
        
    return showdata

#initBusInfos()


app = Flask(__name__)

# Channel Access Token
line_bot_api = LineBotApi('Channel Access Token')
# Channel Secret
handler = WebhookHandler('Channel Secret')
line_bot_api.push_message('push_token', TextSendMessage(text='輸入"/help:"顯示所有功能'))

# 監聽所有來自 /callback 的 Post Request
@app.route('/callback', methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info('Request body: ' + body)
    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 處理訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text
    message = TextSendMessage(text=Total(text))
    line_bot_api.reply_message(event.reply_token, message)


import os
if __name__ == '__main__':
    initBusInfos()
#     print("%s" % Total("/bus:262 台北捷運"))
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

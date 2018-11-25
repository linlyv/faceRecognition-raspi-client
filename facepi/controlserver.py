# -*- coding:UTF-8 -*-
from __future__ import unicode_literals
from time import sleep
import time
import os,signal,sys,struct,socket
import numpy as np
import json
import cv2
import re
from websocket_server import WebsocketServer

servip=None
imagepath = "/home/pi/facepi/image.jpg"
count=0
takephoto=False
pid=None
run=False
filesocket=False
noface=False

def rotate(image, angle, center=None, scale=1.0):
    # 获取图像尺寸
    (h, w) = image.shape[:2]
    # 若未指定旋转中心，则将图像中心设为旋转中心
    if center is None:
        center = (w / 2, h / 2)
    # 执行旋转
    M = cv2.getRotationMatrix2D(center, angle, scale)
    rotated = cv2.warpAffine(image, M, (w, h))
    # 返回旋转后的图像
    return rotated

def cvcaptrue(s):
    global imagepath
    global noface
    print(imagepath)
    result=None
    cap = cv2.VideoCapture(0)
    timetostart=time.time()
    cap.set(3, 320)  # set Width
    cap.set(4, 240)  # set Height
    cascade_path = "/home/pi/facepi/haarcascade_frontalface_alt.xml"
    while (not noface):
        if noface:
            print("noface")
            break
        timetobreak=time.time()
        if timetobreak-timetostart>20:     #设置超时退出
            break
        ret, frame = cap.read()
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)#先转为灰度图
        cascade = cv2.CascadeClassifier(cascade_path)

        faceRects = cascade.detectMultiScale(frame, scaleFactor=1.2, minNeighbors=3, minSize=(72, 72))#检测人脸
        if len(faceRects) > 0:
            for faceRect in faceRects:
                print("检测到人脸")
                x, y, w, h = faceRect     #获得人脸在整张图片中的位置数据
                image = gray[y : y + h +8, x : x + w ]
                src_RGB = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)#从绘度图转为3通道的黑白图片
                kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], np.float32)  # 拉普拉斯算子进行锐化
                dst = cv2.filter2D(src_RGB, -1, kernel=kernel)
                yn = cv2.imwrite(imagepath, dst)
                try:
                    result=tcpsendfile(s, imagepath)#发送人脸图片，并把结果通过websocket呈现给前端web界面
                except:
                    result="sendimage error"
                    pass
                break
            break
        k = cv2.waitKey(10) & 0xff
        if k == 27:  # press 'ESC' to quit
            break
    cap.release()
    cv2.destroyAllWindows()
    return result


def tcpsendfile(s,path):
    filepath = path
    print('imagepath=',filepath)
    time1 = time.time()
    print(os.path.isfile(filepath))
    if os.path.isfile(filepath):
        file_name = os.path.basename(filepath)
        # 获取文件大小
        file_size = os.stat(filepath).st_size
        # 发送文件名 和 文件大小
        datasen = file_name + '|' + str(file_size)
        sendata = datasen.encode('utf-8')
        s.send(sendata)
        # 为了防止粘包，将文件名和大小发送过去之后，等待服务端收到，直到从服务端接受一个信号（说明服务端已经收到）
        s.recv(1024)
        # s.send(fhead)
        print('client filepath: {0}'.format(filepath))

        fp = open(filepath, 'rb')
        send_size = 0
        Flag = True
        while Flag:
            if send_size + 1024 > file_size:
                data = fp.read(file_size - send_size)
                Flag = False
            else:
                data = fp.read(1024)
                send_size += 1024
            s.send(data)
        fp.close()

    result=s.recv(1024).decode()
    print("返回结果：", result)
    time2 = time.time()
    print("耗时：%.2f s" % (time2 - time1))
    s.close()
    return result+",%.2f" % (time2 - time1)#姓名，误差，耗时
#l连接人脸识别服务，连接超时返回0
def photohandle(server):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((servip, 6666))
        print("成功连接人脸识别服务器")
    except socket.error as msg:
        print(msg)
        return 0
        # sys.exit(1)
    sleep(0.5)
    results = cvcaptrue(s)
    print(results)
    try:
        name = str(results.split(",")[0])
        bias = float(results.split(",")[1])
        elapsedtime = float(results.split(",")[2])
    except:
        name = 'null'
        bias = 99
        elapsedtime = 0
    jdata = [{"name": name, "bias": bias, "time": elapsedtime}]
    jsondata = json.dumps(jdata, ensure_ascii=False)
    try:
        server.send_message_to_all(jsondata)
    except:
        print("send text error")
    print(jsondata)
    s.close()
    return 1

def new_client(client, server):
    print("新接入 id %d" % client['id'])
    #print(client)
    global count
    global noface
    noface=True
    count=count+1

# Called for every client disconnecting
def client_left(client, server):
    print("Client(%d) disconnected" % client['id'])
    global count
    global run
    count = count -1
    if count==0:
        result=os.popen("kill -9 $(ps -aux|grep /home/pi/facepi/jsmpegserver.py|awk '{print $2}')")  # 停止
        print("kill jsmpegserver.py?->",result.read())
        run = False


# Called when a client sends a message
def message_received(client, server, message):#传入server对象，然后才可以通过server.send_message_to_all("给前端的消息字符串")发送消息
    global takephoto
    global run
    global noface
    if len(message) < 200:
        message = message[:200]
        print("Client(%d) said: %s" % (client['id'], message))     
        if "end" in str(message):   #接收到end指令
            run=False    #标记jsmpegserver.py结束运行
            result = os.popen("kill -9 $(ps -aux|grep /home/pi/facepi/jsmpegserver.py|awk '{print $2}')")  # 停止视频采集程序
            print("收到end指令，关闭摄像头：", result.read())
        elif "start" in str(message):
            megs=''
            try:
                if not run:
                    run=True 
                    print("打开摄像头，向%s推送视频流。。。。" % client["address"][0])
                    f = os.popen("python3 /home/pi/facepi/jsmpegserver.py")#通过命令行来启动视频流传输
                    megs = f.read()
                    with open('/var/www/html/log.txt', 'w') as f:
                        f.write(megs)
                else:
                    print("向%s推送视频流。。。。"%client["address"][0])
            except:

                with open('/var/www/html/logexcept.txt', 'w') as f:
                    f.write(megs)
                try:
                    server.send_message_to_all("打开摄像头错误，错误信息保存在/var/www/html/logexcept.txt")
                except:
                    print("管道断开，发送消息失败")
            print("remote_server return")

        elif "takephoto" in str(message):
            noface = False
            print("take..")
            ret=photohandle(server)
            if ret==0:
                print("连接服务器超时")
            takephoto=True
        elif str(message)=="cancelphoto":
            takephoto=False
            noface = True
        elif "setremoteip" in str(message):
            try:
                ipaddr=str(message).split(":")[1]
            except:
                ipaddr=" "
                pass
            ipdic = {"remoteip":ipaddr}
            with open('/var/www/html/static/remoteserv.json', 'w') as f:
                json.dump(ipdic,f)
                print("远程ip设置成功")
                try:
                    server.send_message_to_all("远程ip设置成功,请重启树莓派以生效")
                except:
                    pass
        elif "shutdown" in str(message):
            try:
                t=os.popen("sudo shutdown")
                st=t.read()
                server.send_message_to_all("一分钟后关机")
            except:
                pass
        elif "reboot" in str(message):
            try:
                os.popen("sudo reboot")
            except:
                pass
        elif "killchrome" in str(message):
            try:
                pattern = re.compile(r'\d{4}')
                pidstr = os.popen("ps -u pi | grep chromium-browse")
                pidst=pidstr.read()
                result1 = pattern.findall(str(pidst))
                print(result1)
                for i in result1:
                    try:
                        os.popen("kill "+i)
                    except:
                        pass

            except:
                pass
        elif "getip" in str(message):
            try:
                with open('/var/www/html/static/piip.json', 'r') as fi:
                    data = json.load(fi)
                    print(data)
                    piip = data['piip']
                    print('piip:', piip)
                    try:
                        server.send_message_to_all(piip)
                    except:
                        print("send text error")
            except:
                pass
        elif "wakeup" in str(message):
            try:
                print("唤醒无效")
                wk=os.popen("xdotool mousemove 780 460 click 1")
                print(wk.read())
                #os.popen("xdotool click 3")
            except:
                pass
        elif "getserverip" in str(message):
            try:
                with open('/var/www/html/static/remoteserv.json', 'r') as fi:
                    data = json.load(fi)
                    print(data)
                    serverip = data['remoteip']
                    print('返回服务器ip:', serverip)
                    try:
                        server.send_message_to_all(serverip)
                    except:
                        print("send serverip error")
            except:
                pass
        elif "nodetectface" in str(message):
            print("noface=",noface)
            noface=True

with open('/var/www/html/static/remoteserv.json', 'r') as f:
    data = json.load(f)
    print(data)
    servip=data['remoteip']
    print('servip:',servip)


def endProcess(signum=None, frame=None):
    global run
    if signum is not None:
        SIGNAL_NAMES_DICT = dict((getattr(signal, n), n) for n in dir(signal) if n.startswith('SIG') and '_' not in n)
        print("signal {} received by process with PID {}".format(SIGNAL_NAMES_DICT[signum], os.getpid()))
    print("\n-- Terminating program --")
    print(frame)
    print("Cleaning up...")
    run = False
    print("Done.")
    exit(0)


signal.signal(signal.SIGTERM, endProcess)
signal.signal(signal.SIGINT, endProcess)
signal.signal(signal.SIGHUP, endProcess)
signal.signal(signal.SIGQUIT, endProcess)

PORT = 9000
socketserver = WebsocketServer(PORT, host='0.0.0.0')
socketserver.set_fn_new_client(new_client)      #有新连接就执行new_client方法
socketserver.set_fn_client_left(client_left)      #有连接断开就执行client_left方法
socketserver.set_fn_message_received(message_received)    #设置message_received方法来统一处理前端javascript发来的消息指令
socketserver.run_forever()
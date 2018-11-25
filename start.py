# -*- coding:UTF-8 -*-
import os,sys
from time import sleep
import json
import socket


def get_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip
	
def openchrome():

    checks=os.popen("ps -u pi | grep chromium-browse")
    checked=checks.read()
    ch=str(checked).split('\n')
    print(ch)
    ipaddr=''
    while ipaddr=='':     #等待获取ip
        ipaddr=get_host_ip()
    ipdict = {"piip":ipaddr} 
    json_str = json.dumps(ipdict)   #构造json对象
    print(ipdict)
	
	 #json对象写入文件(给前端页面使用)
    with open('/var/www/html/static/piip.json', 'w') as f:
        json.dump(ipdict, f)
    print(type(ipaddr))
    
    
    if len(ch)>1:#判断是否已有浏览器在运行，有就退出程序
        return 0
    sleep(3)   #以全屏模式打开浏览器并访问127.0.0.1
    os.popen("chromium-browser --disable-popup-blocking --no-first-run --disable-desktop-notifications --kiosk http://127.0.0.1/")
    
    
    print("done!")

openchrome()
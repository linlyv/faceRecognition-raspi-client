# faceRecognition-raspi-client

客户端程序

start.py应设置为开机启动程序，目的是打开浏览器以打开web页面

由于树莓派性能有限，运行TensorFlow识别人脸耗时长，所以树莓派使用opencv获取人脸图片，传到服务器再进行识别


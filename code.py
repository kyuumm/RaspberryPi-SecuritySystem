#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 干簧管总控+光电人脸安防系统 匹配最新接线引脚
import RPi.GPIO as GPIO
import time
import smbus
import cv2
import numpy as np

# ========== BCM引脚定义（严格匹配接线图纸） ==========
REED_PIN = 17       # 干簧管D0 BCM17
LED_R = 18          # 双色LED红灯R BCM18
LED_G = 27          # 双色LED绿灯G BCM27
OPT_PIN = 22        # U型光隔离输入BCM22
LASER_PIN = 23      # 激光控制输出BCM23
LCD_ADDR = 0x27
BLEN = 1
BUS = smbus.SMBus(1)

# ===================== LCD1602 I2C驱动 =====================
def write_word(addr, data):
    global BLEN
    temp = data
    if BLEN == 1:
        temp |= 0x08
    else:
        temp &= 0xF7
    BUS.write_byte(addr, temp)

def send_command(comm):
    buf = comm & 0xF0
    buf |= 0x04
    write_word(LCD_ADDR, buf)
    time.sleep(0.002)
    buf &= 0xFB
    write_word(LCD_ADDR, buf)

    buf = (comm & 0x0F) << 4
    buf |= 0x04
    write_word(LCD_ADDR, buf)
    time.sleep(0.002)
    buf &= 0xFB
    write_word(LCD_ADDR, buf)

def send_data(data):
    buf = data & 0xF0
    buf |= 0x05
    write_word(LCD_ADDR, buf)
    time.sleep(0.002)
    buf &= 0xFB
    write_word(LCD_ADDR, buf)

    buf = (data & 0x0F) << 4
    buf |= 0x05
    write_word(LCD_ADDR, buf)
    time.sleep(0.002)
    buf &= 0xFB
    write_word(LCD_ADDR, buf)

def lcd_init():
    try:
        send_command(0x33)
        time.sleep(0.005)
        send_command(0x32)
        time.sleep(0.005)
        send_command(0x28)
        time.sleep(0.005)
        send_command(0x0C)
        time.sleep(0.005)
        send_command(0x01)
        BUS.write_byte(LCD_ADDR, 0x08)
        return True
    except:
        print("LCD初始化失败，检查I2C接线")
        return False

def lcd_clear():
    send_command(0x01)

def lcd_write(x, y, text):
    if x < 0: x = 0
    if x > 15: x = 15
    if y < 0: y = 0
    if y > 1: y = 1
    addr = 0x80 + 0x40 * y + x
    send_command(addr)
    for ch in text:
        send_data(ord(ch))

# ===================== 摄像头人脸检测 =====================
face_cascade = cv2.CascadeClassifier("/home/pi/CLBDEMO/haarcascade_frontalface_default.xml")
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

def face_detect():
    if face_cascade.empty():
        print("人脸xml文件缺失")
        return False
    if not cap.isOpened():
        print("摄像头未打开")
        return False
    ret, img = cap.read()
    if not ret:
        return False
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 3, minSize=(35,35))
    face_num = len(faces)
    # 绘制人脸绿色方框
    for (x,y,w,h) in faces:
        cv2.rectangle(img,(x,y),(x+w,y+h),(0,255,0),2)
    cv2.imshow("Camera View", img)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        raise KeyboardInterrupt
    return face_num > 0

# ===================== GPIO初始化 =====================
def gpio_setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    # 输入引脚
    GPIO.setup(REED_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(OPT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    # 输出引脚默认低电平关闭
    GPIO.setup(LED_R, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(LED_G, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(LASER_PIN, GPIO.OUT, initial=GPIO.LOW)

# ===================== 三种工作状态 =====================
# 无磁铁：系统休眠
def sleep_state():
    GPIO.output(LED_R, GPIO.LOW)
    GPIO.output(LED_G, GPIO.LOW)
    GPIO.output(LASER_PIN, GPIO.LOW)
    lcd_clear()
    lcd_write(0,0,"System Locked")
    lcd_write(0,1,"No Magnet")

# 有磁铁待机：绿灯常亮
def normal_state():
    GPIO.output(LED_R, GPIO.LOW)
    GPIO.output(LED_G, GPIO.HIGH)
    GPIO.output(LASER_PIN, GPIO.LOW)
    lcd_clear()
    lcd_write(0,0,"Standby Mode")
    lcd_write(0,1,"Wait Detect")

# 报警状态：遮挡光隔离+人脸识别
def alarm_state():
    GPIO.output(LED_R, GPIO.HIGH)
    GPIO.output(LED_G, GPIO.LOW)
    GPIO.output(LASER_PIN, GPIO.HIGH)
    lcd_clear()
    lcd_write(0,0,"WARNING!")
    lcd_write(0,1,"Intruder Found")

# ===================== 资源释放 =====================
def destroy():
    cap.release()
    cv2.destroyAllWindows()
    GPIO.output(LED_R, GPIO.LOW)
    GPIO.output(LED_G, GPIO.LOW)
    GPIO.output(LASER_PIN, GPIO.LOW)
    lcd_clear()
    GPIO.cleanup()

# ===================== 主循环 =====================
def main():
    gpio_setup()
    if not lcd_init():
        return
    print("系统就绪，放置磁铁开启检测")
    try:
        while True:
            reed_val = GPIO.input(REED_PIN)
            # reed_val=0 有磁铁；reed_val=1 无磁铁休眠
            if reed_val == 1:
                sleep_state()
                time.sleep(0.4)
                continue
            # 有磁铁，执行检测逻辑
            opt_val = GPIO.input(OPT_PIN)
            has_face = face_detect()
            print(f"干簧管：有磁 | 光隔离遮挡：{opt_val} | 人脸：{has_face}")
            if opt_val == 1 and has_face:
                alarm_state()
            else:
                normal_state()
            time.sleep(0.4)
    except KeyboardInterrupt:
        print("\n程序退出")
    finally:
        destroy()

if __name__ == "__main__":
    main()

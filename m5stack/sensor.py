from m5stack import *
from m5ui import *
from m5mqtt import M5mqtt
import units

clear_bg(0x000000)

title = M5TextBox(70, 85, 'IoT Home ', lcd.FONT_DejaVu40, 0xFFFFFF)
status_circle = M5Circle(110, 160, 15, 0xaaaaaa, 0xaaaaaa)
status_text = M5TextBox(135, 150, 'starting',  lcd.FONT_DejaVu24, 0xFFFFFF)

env_sensor = units.ENV(units.PORTA)

sensor_id = 'inside'
broker_ip = '192.168.1.39'
send_frequency = 0.1
m5mqtt = M5mqtt(sensor_id, broker_ip, 1883, '', '', 300)

while True:
  status_circle.setBgColor(0x2acf22)
  status_circle.setBorderColor(0x2acf22)
  status_text.setText('sending')
  title.setText('IoT Home')

  m5mqtt.publish('home/' + sensor_id + '/temperature', str(env_sensor.temperature()))
  m5mqtt.publish('home/' + sensor_id + '/pressure', str(env_sensor.pressure()))
  m5mqtt.publish('home/' + sensor_id + '/humidity', str(env_sensor.humidity()))

  wait(1)

  status_circle.setBgColor(0xaaaaaa)
  status_circle.setBorderColor(0xaaaaaa)
  status_text.setText('idling')

  wait(1/send_frequency - 1)
from m5stack import *
from m5ui import *
from m5mqtt import M5mqtt
import json
import time, machine
from ntptime import settime
from lib import wifiCfg
import utime

class CoreApp:
  interrupt_counter = 1 # set to 1 if sensor values should be read on startup, 0 else
  sensors = {
    'humidity': {
      'is_active': True,
      'measurement_unit': 'AH',
      'label': 'Humidity',
      'unit': unit.ENV,
      'port': unit.PORTA,
    },
    'temperature': {
      'is_active': True,
      'measurement_unit': 'C',
      'label': 'Temperature',
      'unit': unit.ENV,
      'port': unit.PORTA,
    },
    'pressure': {
      'is_active': True,
      'measurement_unit': 'Pa',
      'label': 'Pressure',
      'unit': unit.ENV,
      'port': unit.PORTA,
    },
  }
  config = {
    'core_id': 'inside',
    'broker_ip': '192.168.1.6',
    'send_frequency': 0.1,
    'ui': {
      'default_color': 0xEEEEEE,
    },
  }

  def __init__(self):
    self.isInitialzed = False

  def init(self):
    if self.isInitialzed:
      return

    self.init_wifi()
    self.init_time()
    self.init_mqtt()
    self.init_screen()
    self.init_sensors()

    self.isInitialzed = True

  def init_screen(self):
    lcd.clear(lcd.BLACK)

    self.status_circle = M5Circle(20, 215, 10, 0xaaaaaa, 0xaaaaaa)
    self.status_text = M5TextBox(40, 207, 'starting',  lcd.FONT_DejaVu18, self.config['ui']['default_color'])

  def init_sensors(self):
    self.active_sensors = {}

    start_x = 10
    start_y = 10
    sensor_count = 0

    for sensor_name, sensor_config in self.sensors.items():
      self.active_sensors[sensor_name] = {
        'name': sensor_name,
        'config': sensor_config,
        'sensor': unit.get(sensor_config['unit'], sensor_config['port']),
        'label_text': M5TextBox(start_x, start_y + 30, sensor_config['label'] + ' [' + sensor_config['measurement_unit'] + ']',  lcd.FONT_Default, self.config['ui']['default_color']),
        'label_value': M5TextBox(start_x, start_y, '-',  lcd.FONT_DejaVu24, self.config['ui']['default_color']),
      }

      sensor_count = sensor_count + 1
      start_y = start_y + 65

      if sensor_count % 3 == 0:
        start_x = 170
        start_y = 10

  def init_mqtt(self):
    self.m5mqtt = M5mqtt(self.config['core_id'], self.config['broker_ip'], 1883, '', '', 300)

  def init_wifi(self):
    wifiCfg.screenShow()
    wifiCfg.autoConnect(lcdShow=True)

  def init_time(self):
    settime()

  def interrupt_handler(timer):
    CoreApp.interrupt_counter = 1 + CoreApp.interrupt_counter

  def current_time(self):
    return (utime.time() + 946684800) * 1000 # Convert utime to timestamp in milliseconds

  def run_decrement_interrupt_counter(self):
    state = machine.disable_irq()
    CoreApp.interrupt_counter = CoreApp.interrupt_counter - 1
    machine.enable_irq(state)

  def run_set_status(self, status):
    if status == 'waiting':
      self.status_circle.setBgColor(0xaaaaaa)
      self.status_circle.setBorderColor(0xaaaaaa)
      self.status_text.setText(status)
    elif status == 'updating':
      self.status_circle.setBgColor(0x2acf22)
      self.status_circle.setBorderColor(0x2acf22)
      self.status_text.setText(status)
    elif status == 'error':
      self.status_circle.setBgColor(0xd40707)
      self.status_circle.setBorderColor(0xd40707)
      self.status_text.setText(status)
    else:
      self.status_circle.setBgColor(0xaaaaaa)
      self.status_circle.setBorderColor(0xaaaaaa)
      self.status_text.setText('undefined status')

  def run_update(self):
    self.run_set_status('updating')
    self.run_decrement_interrupt_counter()

    current_timestamp = self.current_time()

    for sensor_name, sensor in self.active_sensors.items():
      sensor_value = getattr(sensor['sensor'], sensor_name)
      sensor_json = {'timestamp': current_timestamp, 'value': sensor_value}

      sensor['label_value'].setText(str(sensor_value))
      self.m5mqtt.publish('home/' + self.config['core_id'] + '/' + sensor_name, json.dumps(sensor_json))

    wait_ms(500)
    self.run_set_status('waiting')

  def run(self):
    self.init()
    self.run_set_status('waiting')

    timer = machine.Timer(-1)
    timer.init(period=10000, mode=machine.Timer.PERIODIC, callback=CoreApp.interrupt_handler)

    while True:
      if CoreApp.interrupt_counter > 0:
        try:
          # TODO handle mqtt disconnect
          self.run_update()
        except:
          self.run_set_status('error')

      wait_ms(500)

core_app = CoreApp()
core_app.run()

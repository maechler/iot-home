from m5stack import *
from m5ui import *
from m5mqtt import M5mqtt
from uiflow import *
import json
import time, machine
from ntptime import settime
from lib import wifiCfg
import utime
import unit

class CoreApp:
  interrupt_counter = 1 # set to 1 if sensor values should be read on startup, 0 else
  sensors = {
    'humidity': {
      'is_active': True,
      'measurement_unit': 'AH',
      'label': 'Humidity',
      'value_key': 'humidity',
      'unit': unit.ENV,
      'port': unit.PORTA,
    },
    'temperature': {
      'is_active': True,
      'measurement_unit': 'C',
      'label': 'Temperature',
      'value_key': 'temperature',
      'unit': unit.ENV,
      'port': unit.PORTA,
    },
    'pressure': {
      'is_active': True,
      'measurement_unit': 'Pa',
      'label': 'Pressure',
      'value_key': 'pressure',
      'unit': unit.ENV,
      'port': unit.PORTA,
    },
    'earth': {
      'is_active': True,
      'measurement_unit': 'mg/L',
      'label': 'Earth',
      'value_key': 'analogValue',
      'pbhub_address': 0x0,
      'unit': unit.PBHUB,
      'port': unit.PORTA,
    },
    'light': {
      'is_active': True,
      'measurement_unit': 'lux',
      'label': 'Light',
      'value_key': 'analogValue',
      'pbhub_address': 1,
      'unit': unit.PBHUB,
      'port': unit.PORTA,
    },
  }
  config = {
    'core_id': 'inside',
    'broker_ip': '192.168.1.12',
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
      if not sensor_config['is_active']:
        continue

      current_sensor = unit.get(sensor_config['unit'], sensor_config['port'])
      self.active_sensors[sensor_name] = {
        'name': sensor_name,
        'config': sensor_config,
        'get_value': lambda s=current_sensor, c=sensor_config: s.analogRead(c['pbhub_address']) if 'pbhub_address' in c else getattr(s, c['value_key']),
        'sensor': current_sensor,
        'label_text': M5TextBox(start_x, start_y + 30, sensor_config['label'] + ' [' + sensor_config['measurement_unit'] + ']',  lcd.FONT_Default, CoreApp.config['ui']['default_color']),
        'label_value': M5TextBox(start_x, start_y, '-',  lcd.FONT_DejaVu24, CoreApp.config['ui']['default_color']),
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

  def run_set_status(self, status, status_text=''):
    if status.startswith('waiting'):
      self.status_circle.setBgColor(0xaaaaaa)
      self.status_circle.setBorderColor(0xaaaaaa)
      self.status_text.setText(status)
    elif status.startswith('sending'):
      self.status_circle.setBgColor(0x2acf22)
      self.status_circle.setBorderColor(0x2acf22)
      self.status_text.setText(status)
    elif status.startswith('error'):
      self.status_circle.setBgColor(0xd40707)
      self.status_circle.setBorderColor(0xd40707)
      self.status_text.setText(status + (': ' + status_text if status_text else ''))
    else:
      self.status_circle.setBgColor(0xaaaaaa)
      self.status_circle.setBorderColor(0xaaaaaa)
      self.status_text.setText('undefined status')

  def run_buttons(self):
    if btnB.wasPressed():
      lcd.clear(lcd.BLACK)

      start_x = 10
      start_y = 10

      core_id_label = M5TextBox(start_x, start_y + 30, 'Core ID',  lcd.FONT_Default, CoreApp.config['ui']['default_color'])
      core_id_value = M5TextBox(start_x, start_y, CoreApp.config['core_id'],  lcd.FONT_DejaVu24, CoreApp.config['ui']['default_color'])
      start_y = start_y + 65
      mqtt_host_label = M5TextBox(start_x, start_y + 30, 'MQTT Host',  lcd.FONT_Default, CoreApp.config['ui']['default_color'])
      mqtt_host_value = M5TextBox(start_x, start_y, CoreApp.config['broker_ip'],  lcd.FONT_DejaVu24, CoreApp.config['ui']['default_color'])
      start_y = start_y + 65
      send_frequency_label = M5TextBox(start_x, start_y + 30, 'Send Frequency [Hz]',  lcd.FONT_Default, CoreApp.config['ui']['default_color'])
      send_frequency_value = M5TextBox(start_x, start_y, str(CoreApp.config['send_frequency']),  lcd.FONT_DejaVu24, CoreApp.config['ui']['default_color'])

      while not btnB.isReleased():
        pass

      lcd.clear(lcd.BLACK)

      return True

    return False

  def run(self):
    self.init()
    self.run_set_status('waiting')

    timer = machine.Timer(-1)
    timer.init(period=10000, mode=machine.Timer.PERIODIC, callback=CoreApp.interrupt_handler)
    fake_space = True # use fake space to trick M5TextBox to render text even if unchanged

    while True:
      buttons_pressed = self.run_buttons()

      if buttons_pressed:
        self.run_set_status('waiting' + (' ' if fake_space else ''))
        for sensor_name, sensor in self.active_sensors.items():
          sensor['label_text'].setText(sensor['config']['label'] + ' [' + sensor['config']['measurement_unit'] + ']' + (' ' if fake_space else ''))
          sensor['label_value'].setText('{:.2f}'.format(sensor['get_value']())+ (' ' if fake_space else ''))

        fake_space = not fake_space

      if CoreApp.interrupt_counter > 0:
        self.run_set_status('sending')
        self.run_decrement_interrupt_counter()

        for sensor_name, sensor in self.active_sensors.items():
          sensor_json = {'timestamp': self.current_time(), 'value': sensor['get_value']()}

          sensor['label_text'].setText(sensor['config']['label'] + ' [' + sensor['config']['measurement_unit'] + ']' + (' ' if fake_space else ''))
          sensor['label_value'].setText('{:.2f}'.format(sensor['get_value']())+ (' ' if fake_space else ''))

          self.m5mqtt.publish('home/' + self.config['core_id'] + '/' + sensor_name, json.dumps(sensor_json))

        wait_ms(500)
        self.run_set_status('waiting' + (' ' if fake_space else ''))
        fake_space = not fake_space

      wait_ms(500)

try:
  core_app = CoreApp()
  core_app.run()
except Exception as e:
  lcd.clear(lcd.BLACK)
  lcd.print('Oops, an error occurred! ' + str(e), 0, 0, 0xd40707)

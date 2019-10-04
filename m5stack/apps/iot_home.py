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

TFT_LED_PIN = const(32)


class MyTextBox(M5TextBox):
    add_fake_space = True

    def setText(self, text):
        # use fake space to trick M5TextBox into rendering text even if unchanged
        super().setText(text + (' ' if self.add_fake_space else ''))
        self.add_fake_space = not self.add_fake_space


class CoreApp:
    interrupt_counter = 1  # set to 1 if sensor values should be read on startup, 0 else
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
            'pbhub_address': 0x00,
            'unit': unit.PBHUB,
            'port': unit.PORTA,
        },
        'light': {
            'is_active': True,
            'measurement_unit': 'lux',
            'label': 'Light',
            'value_key': 'analogValue',
            'pbhub_address': 0x01,
            'unit': unit.PBHUB,
            'port': unit.PORTA,
        },
    }
    config = {
        'core_id': 'inside',
        'broker_ip': '192.168.1.12',
        'send_frequency': 0.1,
        'screen_timeout': 1000 * 60,
        'ui': {
            'default_color': 0xEEEEEE,
        },
    }

    def __init__(self):
        self.isInitialzed = False
        self.screen_power = machine.Pin(TFT_LED_PIN, machine.Pin.OUT)

    def init(self):
        if self.isInitialzed:
            return

        self.init_wifi()
        self.init_time()
        self.init_mqtt()
        self.init_screen()
        self.init_sensors()

        self.isInitialzed = True

    def pbhubAnalogRead(self, pbhub, pbhub_address):
        #  See http://forum.m5stack.com/topic/1330/connect-units-to-pbhub
        data = 0
        max_val = 30
        min_val = 750
        for i in range(0, 10):
            newdata = 750 - pbhub.analogRead(pbhub_address)
            data += newdata
            if newdata > max_val:
                max_val = newdata
            if newdata < min_val:
                min_val = newdata
        data -= (max_val + min_val)
        data >>= 3
        return round(max(1024 * data / 750, 0), 2)

    def init_screen(self):
        self.last_user_interaction = self.current_time()  # Startup
        self.set_screen_on(True)

        lcd.clear(lcd.BLACK)

        self.status_circle = M5Circle(20, 215, 10, 0xaaaaaa, 0xaaaaaa)
        self.status_text = MyTextBox(40, 207, 'starting', lcd.FONT_DejaVu18, self.config['ui']['default_color'])

    def init_sensors(self):
        self.active_sensors = {}

        start_x = 10
        start_y = 10
        sensor_count = 0
        align_right = False

        for sensor_name, sensor_config in self.sensors.items():
            if not sensor_config['is_active']:
                continue

            if align_right:
                start_x = 170
            else:
                start_x = 10

            current_sensor = unit.get(sensor_config['unit'], sensor_config['port'])
            self.active_sensors[sensor_name] = {
                'name': sensor_name,
                'config': sensor_config,
                'get_value': lambda s=current_sensor, c=sensor_config: self.pbhubAnalogRead(s, c['pbhub_address']) if 'pbhub_address' in c else getattr(s, c['value_key']),
                'sensor': current_sensor,
                'label_text': MyTextBox(start_x, start_y + 30, sensor_config['label'] + ' [' + sensor_config['measurement_unit'] + ']', lcd.FONT_Default, CoreApp.config['ui']['default_color']),
                'label_value': MyTextBox(start_x, start_y, '-', lcd.FONT_DejaVu24, CoreApp.config['ui']['default_color']),
            }

            sensor_count = sensor_count + 1

            if sensor_count % 2 == 0:
                start_y = start_y + 65

            align_right = not align_right

    def init_mqtt(self):
        self.m5mqtt = M5mqtt(self.config['core_id'], self.config['broker_ip'], 1883, '', '', 300)

    def init_wifi(self):
        wifiCfg.screenShow()
        wifiCfg.autoConnect(lcdShow=True)

    def init_time(self):
        settime()

    def set_screen_on(self, is_on):
        self.screen_power.value(int(is_on))

    @staticmethod
    def interrupt_handler(timer):
        CoreApp.interrupt_counter = 1 + CoreApp.interrupt_counter

    def current_time(self):
        return (utime.time() + 946684800) * 1000  # Convert utime to timestamp in milliseconds

    def run_check_wifi(self):
        if not wifiCfg.isconnected():
            wifiCfg.reconnect()

    def run_check_screen_timeout(self):
        delta = self.current_time() - self.last_user_interaction

        if delta > self.config['screen_timeout']:
            self.set_screen_on(False)

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

    def run_show_config(self):
        lcd.clear(lcd.BLACK)

        start_x = 10
        start_y = 10

        core_id_label = MyTextBox(start_x, start_y + 30, 'Core ID', lcd.FONT_Default, CoreApp.config['ui']['default_color'])
        core_id_value = MyTextBox(start_x, start_y, CoreApp.config['core_id'], lcd.FONT_DejaVu24, CoreApp.config['ui']['default_color'])
        start_y = start_y + 65
        mqtt_host_label = MyTextBox(start_x, start_y + 30, 'MQTT Host', lcd.FONT_Default, CoreApp.config['ui']['default_color'])
        mqtt_host_value = MyTextBox(start_x, start_y, CoreApp.config['broker_ip'], lcd.FONT_DejaVu24, CoreApp.config['ui']['default_color'])
        start_y = start_y + 65
        send_frequency_label = MyTextBox(start_x, start_y + 30, 'Send Frequency [Hz]', lcd.FONT_Default, CoreApp.config['ui']['default_color'])
        send_frequency_value = MyTextBox(start_x, start_y, str(CoreApp.config['send_frequency']), lcd.FONT_DejaVu24, CoreApp.config['ui']['default_color'])

    def run_buttons(self):
        button_pressed = False

        if btnA.wasPressed():
            button_pressed = True

        if btnB.wasPressed():
            button_pressed = True

            self.run_show_config()

            while not btnB.isReleased():
                pass

            lcd.clear(lcd.BLACK)

        if btnC.wasPressed():
            button_pressed = True

        return button_pressed

    def run(self):
        self.init()
        self.run_set_status('waiting')

        timer = machine.Timer(-1)
        timer.init(period=int(1000 / CoreApp.config['send_frequency']), mode=machine.Timer.PERIODIC, callback=CoreApp.interrupt_handler)

        while True:
            buttons_pressed = self.run_buttons()

            self.run_check_screen_timeout()

            if buttons_pressed:
                self.last_user_interaction = self.current_time()
                self.set_screen_on(True)

                self.run_set_status('waiting')
                for sensor_name, sensor in self.active_sensors.items():
                    sensor['label_text'].setText(sensor['config']['label'] + ' [' + sensor['config']['measurement_unit'] + ']')
                    sensor['label_value'].setText('{:.2f}'.format(sensor['get_value']()))

            if CoreApp.interrupt_counter > 0:
                self.run_check_wifi()
                self.run_set_status('sending')
                self.run_decrement_interrupt_counter()

                for sensor_name, sensor in self.active_sensors.items():
                    sensor_json = {'timestamp': self.current_time(), 'value': sensor['get_value']()}

                    sensor['label_text'].setText(sensor['config']['label'] + ' [' + sensor['config']['measurement_unit'] + ']')
                    sensor['label_value'].setText('{:.2f}'.format(sensor['get_value']()))

                    self.m5mqtt.publish('home/' + self.config['core_id'] + '/' + sensor_name, json.dumps(sensor_json))

                wait_ms(500)
                self.run_set_status('waiting')

            wait_ms(500)


try:
    core_app = CoreApp()
    core_app.run()
except Exception as e:
    lcd.clear(lcd.BLACK)
    lcd.print('Oops, an error occurred! ' + str(e), 0, 0, 0xd40707)

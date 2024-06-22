import os
import subprocess

TRANSIENT_DATABASE = os.getenv('TRANSIENT_DATABASE') == 'TRUE'

if TRANSIENT_DATABASE:
    subprocess.run(['service', 'mariadb', 'start'])
    os.environ['DATABASE_HOST'] = 'localhost'
    os.environ['DATABASE_NAME'] = 'anonymous_messenger_db'
    os.environ['DATABASE_USER'] = 'anonymous_messenger'
    os.environ['DATABASE_PASS'] = 'anonymous_messenger_pass'

print('*' * 80)
APP_PATH = os.getenv('APP_PATH', './')
LICENSE_PATH = os.path.join(APP_PATH, 'LICENSE')
with open(LICENSE_PATH, 'r') as license_file:
    print(license_file.read())
print('*' * 80)

print("Starting server")
os.chdir(APP_PATH)
from main import run
run()

print("Exiting")

if TRANSIENT_DATABASE:
    subprocess.run(['service', 'mariadb', 'stop'])

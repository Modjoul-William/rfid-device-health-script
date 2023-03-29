import boto3
import pandas as pd
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import json
import os
from io import StringIO
from datetime import datetime
import requests


class DeviceHealthMonitor:

    def __init__(self):
        load_dotenv()

        # API environment variables
        self.username_smtp = os.environ.get("USERNAME_SMTP")
        self.password = os.environ.get("PASSWORD")
        self.url_obtain_login_token = os.environ.get("URL_OBTAIN_LOGIN_TOKEN")
        self.url_device_status = os.environ.get('URL_DEVICE_STATUS')

        # Email environment variables
        self.sender_email = os.environ.get("SENDER_EMAIL")
        self.rec_email = os.environ.get('REC_EMAIL')
        self.rec_email_2 = os.environ.get('REC_EMAIL_2')
        self.coles_rec_email = os.environ.get('COLES_REC_EMAIL')
        self.email_password = os.environ.get('EMAIL_PASSWORD')

        # AWS environment variables
        self.bucket_name = os.getenv('BUCKET_NAME')

        self.timestamp = str(datetime.now().replace(microsecond=0))
        self.devices_list = []
        self.offline_devices = []
        self.coles_offline_devices = []

    def get_clearstream_login_token(self):
        payload = {
            "username": self.username_smtp,
            "password": self.password
        }
        headers = {
            'Content-Type': 'text/plain'
        }
        response = requests.request("POST", self.url_obtain_login_token, headers=headers, json=payload)
        token_response = response.json()
        bearer_token = token_response['token']

        if bearer_token:
            print('Login Successful!')

        self.get_clearstream_json_data(bearer_token)

    def get_clearstream_json_data(self, bearer_token):
        headers = {
            'Content-Type': 'text/plain',
            'Authorization': f'Bearer {bearer_token}'
        }
        response = requests.request("GET", self.url_device_status, headers=headers)

        # Filter down response result
        top = response.json()
        devices = top['devices']

        # Adds a key value pair to tell when the csv sheet was made for quicksight
        for device in devices:
            device['timeaccessed'] = str(self.timestamp)

        self.devices_list.append(devices)

        # Check to see if device is offline and if the name ends with DVA3,
        # then add the name of the device to the offline_devices list
        for device in devices:
            if device['online'] == "" and device['name'].endswith('DVA3'):
                self.offline_devices.append(device['name'])

        # Check to see if devices ending in ESDC are offline
        for device in devices:
            if device['online'] == "" and device['name'].endswith('ESDC'):
                self.coles_offline_devices.append(device['name'])
    
    def send_offline_devices_email(self):
        pretty_offline_devices = json.dumps(self.offline_devices, indent=4)
        pretty_coles_offline_devices = json.dumps(self.coles_offline_devices, indent=4)

        recipients = [self.rec_email, self.rec_email_2, self.sender_email]
        coles_recipients = [self.coles_rec_email, self.sender_email]
        if self.offline_devices:
            print('There are devices Down')
            try:
                message = MIMEMultipart('alternative')
                message['Subject'] = 'Current Offline Devices'
                message['From'] = 'Modjoul Device Script'
                message['To'] = ','.join(recipients)

                message.attach(MIMEText(f"The following devices are offline: \r\n {pretty_offline_devices}"))

                server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                server.login(self.sender_email, self.email_password)
                server.sendmail(
                    self.sender_email,
                    recipients, message.as_string()
                )
                server.quit()
                print('Email Sent!')
            except:
                print('There was an error sending the email')
        if self.coles_offline_devices:
            print('There are devices Down')
            try:
                message = MIMEMultipart('alternative')
                message['Subject'] = 'Current Offline Devices'
                message['From'] = 'Modjoul Device Script'
                message['To'] = ','.join(coles_recipients)

                message.attach(MIMEText(f"The following devices are offline: \r\n {pretty_coles_offline_devices}"))

                server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                server.login(self.sender_email, self.email_password)
                server.sendmail(
                    self.sender_email,
                    coles_recipients, message.as_string()
                )
                server.quit()
                print('Email Sent!')
            except Exception as e:
                import traceback
                print('There was an error sending the email:')
                print(traceback.format_exc())

        else:
            print('There are no Devices Down')
            
if __name__ == "__main__":
    health = DeviceHealthMonitor()
    health.get_clearstream_login_token()
    health.send_offline_devices_email()
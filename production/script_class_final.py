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

def lambda_handler(event,context):
    load_dotenv()

    # API environment variables
    USERNAME_SMTP = os.environ.get("USERNAME_SMTP")
    PASSWORD = os.environ.get("PASSWORD")
    URL_OBTAIN_LOGIN_TOKEN = os.environ.get("URL_OBTAIN_LOGIN_TOKEN")
    URL_DEVICE_STATUS = os.environ.get('URL_DEVICE_STATUS')

    # Email environment variables
    SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
    REC_EMAIL = os.environ.get('REC_EMAIL')
    REC_EMAIL_2 = os.environ.get('REC_EMAIL_2')
    COLES_REC_EMAIL = os.environ.get('COLES_REC_EMAIL')
    EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')

    # AWS environment variables
    BUCKET_NAME = os.getenv('BUCKET_NAME')

    class DeviceHealthMonitor:
        def __init__(self):
            self.timestamp = str(datetime.now().replace(microsecond=0))
            self.devices_list = []
            self.offline_devices = []
            self.coles_offline_devices = []

        def get_clearstream_login_token(self):
            """
            This method retrieves an authentication token from the Clearstream API using the provided
            USERNAME_SMTP and PASSWORD. If the login is successful, it calls the get_clearstream_json_data method
            with the obtained bearer token as its argument.
            """
            payload = {
                "username": USERNAME_SMTP,
                "password": PASSWORD
            }
            headers = {
                'Content-Type': 'text/plain'
            }
            try:
                response = requests.request("POST", URL_OBTAIN_LOGIN_TOKEN, headers=headers, json=payload)
                response.raise_for_status() # Raise an exception if the response contains an HTTP error status code
            except requests.exceptions.RequestException as e:
                print(f"Error while obtaining login token: {e}")
                return  # Exit the function early in case of an error
            
            token_response = response.json()
            bearer_token = token_response['token']

            if bearer_token:
                print('Login Successful!')

            self.get_clearstream_json_data(bearer_token)

        def get_clearstream_json_data(self, bearer_token):
            """
            This method retrieves a list of devices and their statuses from the Clearstream API using the provided
            bearer_token. It then processes the JSON data to extract what devices are offline and updates the appropriate
            devices_list, offline_devices, and coles_offline_devices attributes.

            Args:
                bearer_token (str): The authentication token obtained from the Clearstream API.
            """
            headers = {
                'Content-Type': 'text/plain',
                'Authorization': f'Bearer {bearer_token}'
            }
            try:
                response = requests.request("GET", URL_DEVICE_STATUS, headers=headers)
                response.raise_for_status()  # Raise an exception if the response contains an HTTP error status code
            except requests.exceptions.RequestException as e:
                print(f"Error while obtaining device status: {e}")
                return  # Exit the function early in case of an error

            top = response.json()
            devices = top['devices']

            for device in devices:
                device['timeaccessed'] = str(self.timestamp)

            self.devices_list.append(devices)

            # DVA3 check
            for device in devices:
                if device['online'] == "" and device['name'].endswith('DVA3'):
                    self.offline_devices.append(device['name'])

            # COLES check
            for device in devices:
                if device['online'] == "" and device['name'].endswith('ESDC'):
                    self.coles_offline_devices.append(device['name'])

        def send_offline_devices_email(self):
            """
            This method formats and sends an email notification to the appropriate recipients when there are offline devices
            in the offline_devices or coles_offline_devices attributes.
            """

            pretty_offline_devices = json.dumps(self.offline_devices, indent=4)
            pretty_coles_offline_devices = json.dumps(self.coles_offline_devices, indent=4)

            recipients = [REC_EMAIL, REC_EMAIL_2, SENDER_EMAIL]
            coles_recipients = [REC_EMAIL_2, COLES_REC_EMAIL, SENDER_EMAIL]
            if self.offline_devices:
                print('There are devices Down')
                try:
                    message = MIMEMultipart('alternative')
                    message['Subject'] = 'Current Offline Devices'
                    message['From'] = 'Modjoul Device Script'
                    message['To'] = ','.join(recipients)
                    message.attach(MIMEText(f"The following devices are offline: \r\n {pretty_offline_devices}"))

                    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                    server.login(SENDER_EMAIL, EMAIL_PASSWORD)
                    server.sendmail(
                    SENDER_EMAIL, 
                    recipients, message.as_string() 
                    )
                    server.quit()
                    print('Email Sent!')
                except smtplib.SMTPException as e:
                    print(f'There was an error sending the email: {e}')

            if self.coles_offline_devices:
                print('There are devices Down')
                try:
                    message = MIMEMultipart('alternative')
                    message['Subject'] = 'Current Offline Devices'
                    message['From'] = 'Modjoul Device Script'
                    message['To'] = ','.join(coles_recipients)

                    message.attach(MIMEText(f"The following devices are offline: \r\n {pretty_coles_offline_devices}"))

                    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                    server.login(SENDER_EMAIL, EMAIL_PASSWORD)
                    server.sendmail(
                    SENDER_EMAIL, 
                    coles_recipients, message.as_string() 
                    )
                    server.quit()
                    print('Email Sent!')
                except smtplib.SMTPException as e:
                    print(f'There was an error sending the email: {e}')
            else:
                print('There are no Devices Down')
            
        def create_s3_csv_files(self):
            """
            The method creates two file paths: one for the current device health sheet which is overwritten and another for the historical
            device health sheet with a timestamp.
            """
            df = pd.DataFrame(self.devices_list[0])

            resource = boto3.resource(
                's3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_VAR'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_CODE'),
                region_name=os.getenv('AWS_REGION_VAR')
            )

            current = 'current/device_health_sheet.csv'
            history = f'history/device_health_sheet_{self.timestamp}.csv'

            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False)
            try:
                resource.Object(BUCKET_NAME, current).put(Body=csv_buffer.getvalue())
                resource.Object(BUCKET_NAME, history).put(Body=csv_buffer.getvalue())
                print('CSV files were added to S3')
            except boto3.exceptions.Boto3Error as e:
                print(f'There was a problem with adding the csv files to S3: {e}')
                
    device_health = DeviceHealthMonitor()
    device_health.get_clearstream_login_token()
    device_health.send_offline_devices_email()
    device_health.create_s3_csv_files()
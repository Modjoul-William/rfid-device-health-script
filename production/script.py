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

    # Initialize environment variables
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

    timestamp = str(datetime.now().replace(microsecond=0))

    def get_ClearStream_login_token():
        # Logs into API to obtain bearer token required for status update
        # and passes it into the next function to run
        
        payload = {
            "username":USERNAME_SMTP,
            "password": PASSWORD
        }
        headers = {
            'Content-Type': 'text/plain'       
        }
        response = requests.request("POST", URL_OBTAIN_LOGIN_TOKEN, headers=headers, json=payload)
        token_response = response.json()
        BEARER_TOKEN = token_response['token']

        if BEARER_TOKEN:
            print('Login Successful!')
            
        get_ClearStream_JSON_data(BEARER_TOKEN)


    devices_list = []
    offline_devices = []
    coles_offline_devices = []

    def get_ClearStream_JSON_data(BEARER_TOKEN):
        # Uses the token obtained from login to access the status of the devices and see 
        # if DVA3 devices are currently offline and then sends email with devices listed

        headers = {
            'Content-Type': 'text/plain',
            'Authorization': f'Bearer {BEARER_TOKEN}'
        }
        response = requests.request("GET", URL_DEVICE_STATUS, headers=headers )

        # Filter down response result
        top = response.json()
        devices = top['devices']

        # Adds a key value pair to tell when the csv sheet was made for quicksight
        for device in devices:
            device['timeaccessed'] = str(timestamp)

        devices_list.append(devices)

        # Check to see if device is offline and if the name ends with DVA3, 
        # then add the name of the device to the offline_devices list
        for device in devices:
            if device['online'] == "" and device['name'].endswith('DVA3'):
                offline_devices.append(device['name'])

            # Check to see if devices ending in ESDC are offline
        for device in devices:
            if device['online'] == "" and device['name'].endswith('ESDC'):
                coles_offline_devices.append(device['name'])
        

    def send_offline_devices_email():
        # If devices are down, send email listing which ones are
        pretty_offline_devices = json.dumps(offline_devices, indent=4)
        pretty_coles_offline_devices = json.dumps(coles_offline_devices, indent=4)

        recipients = [REC_EMAIL, REC_EMAIL_2, SENDER_EMAIL ]
        coles_recipients = [REC_EMAIL_2, COLES_REC_EMAIL, SENDER_EMAIL]
        if offline_devices:
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
            except:
                print('There was an error sending the email')
        if coles_offline_devices:
            print('There are devices Down')
            try:
                message = MIMEMultipart('alternative')
                message['Subject'] = 'Current Offline Devices'
                message['From'] = 'Modjoul Device Script'
                message['To'] = ','.join(recipients)

                message.attach(MIMEText(f"The following devices are offline: \r\n {pretty_coles_offline_devices}"))

                server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                server.login(SENDER_EMAIL, EMAIL_PASSWORD)
                server.sendmail(
                SENDER_EMAIL, 
                coles_recipients, message.as_string() 
                )
                server.quit()
                print('Email Sent!')
            except:
                print('There was an error sending the email')
        else:
            print('There are no Devices Down')

    def create_S3_csv_files():
        # Formats the data into a pandas dataframe and creates CSV files to put into
        # S3 buckets

        df=pd.DataFrame(devices_list[0])

        # Initialize AWS boto3
        resource = boto3.resource(
            's3',
            aws_access_key_id = os.getenv('AWS_ACCESS_KEY_VAR'),
            aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_CODE'),
            region_name = os.getenv('AWS_REGION_VAR')
        )

        # Name files and determine location
        current = 'current/device_health_sheet.csv'
        history = f'history/device_health_sheet_{timestamp}.csv'

        # Add CSV files to both current and historical folders
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        try:
            resource.Object(BUCKET_NAME, current).put( Body=csv_buffer.getvalue())
            resource.Object(BUCKET_NAME, history).put( Body=csv_buffer.getvalue())
            print('CSV files were added to S3')
        except:
            print('There was a problem with adding the csv files to S3')


    get_ClearStream_login_token()
    send_offline_devices_email()
    create_S3_csv_files()







        













import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import requests
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from django.conf import settings


def get_session():
    session = requests.Session()
    session.verify = False
    retry = Retry(total=2, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


def _send_sms_async(phone_number, message):
    try:
        url = "https://api.sandbox.africastalking.com/version1/messaging"
        headers = {
            "apiKey": settings.AT_API_KEY,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {
            "username": settings.AT_USERNAME,
            "to": phone_number,
            "message": message,
        }
        session = get_session()
        response = session.post(
            url,
            headers=headers,
            data=data,
            timeout=60
        )
        print(f"[AT Raw Response] {response.status_code} {response.text}")
    except Exception as e:
        print(f"[AT Exception] {str(e)}")


def send_sms(phone_number, message):
    try:
        thread = threading.Thread(
            target=_send_sms_async,
            args=(phone_number, message)
        )
        thread.daemon = True
        thread.start()
        return {'success': True, 'data': 'SMS queued for sending'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def send_otp_sms(phone_number, otp_code):
    message = f"Your CleanLinka verification code is: {otp_code}. Valid for 10 minutes. Do not share this code."
    return send_sms(phone_number, message)


def send_job_assigned_sms(phone_number, collector_name):
    message = f"Hello {collector_name}, you have a new pickup job assigned on CleanLinka. Open your app to accept."
    return send_sms(phone_number, message)


def send_request_confirmed_sms(phone_number, household_name):
    message = f"Hello {household_name}, your waste pickup request has been received on CleanLinka. A collector will be assigned shortly."
    return send_sms(phone_number, message)


def send_collector_accepted_sms(phone_number, household_name):
    message = f"Hello {household_name}, a collector has accepted your pickup request and is on the way."
    return send_sms(phone_number, message)


def send_job_completed_sms(phone_number, household_name):
    message = f"Hello {household_name}, your waste pickup has been completed. Thank you for using CleanLinka!"
    return send_sms(phone_number, message)
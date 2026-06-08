#!/usr/bin/env python3
"""
AdShare Dynamic Login & Session Manager
Establishes and maintains a logged-in session for AdShare automation scripts.
"""
import os
import pickle
import time
import requests
from bs4 import BeautifulSoup

COOKIE_FILE = "session_cookies.pkl"
BASE_URL = "https://adsha.re"

def load_cookies():
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Could not load cookies: {e}")
    return None

def save_cookies(jar):
    try:
        with open(COOKIE_FILE, 'wb') as f:
            pickle.dump(jar, f)
        print("Session cookies saved.")
    except Exception as e:
        print(f"Error saving cookies: {e}")

def get_session(username, password):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    })
    
    cookies = load_cookies()
    if cookies:
        session.cookies.update(cookies)
        print("Loaded cookies. Verifying session...")
        try:
            response = session.get(f"{BASE_URL}/adverts", timeout=15)
            response.raise_for_status()
            if 'logout' in response.text.lower() or 'account' in response.text.lower():
                print("Session is valid.")
                return session
        except requests.exceptions.RequestException as e:
            print(f"Session validation failed: {e}. Proceeding to re-login.")
    
    print("Performing dynamic login...")
    for attempt in range(3):
        try:
            response = session.get(f"{BASE_URL}/login", timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            login_form = soup.find('form')
            if not login_form: raise ValueError("Could not find login form.")

            action = login_form.get('action')
            login_action_url = f"{BASE_URL}{action}" if action.startswith('/') else action

            email_input = login_form.find('input', {'value': 'Email Address'})
            password_input = login_form.find('input', {'value': 'Password'})

            if not email_input or not password_input:
                raise ValueError("Could not find email or password fields.")
            
            payload = {
                email_input.get('name'): username,
                password_input.get('name'): password,
            }

            print(f"Attempting login with payload: {payload}")
            login_response = session.post(login_action_url, data=payload, timeout=15, allow_redirects=True)
            login_response.raise_for_status()

            print(f"Login response URL: {login_response.url}")
            print(f"Login response status: {login_response.status_code}")
            
            # Check for successful login by looking for redirect to /offer page
            if 'offer' in login_response.url and login_response.url != f"{BASE_URL}/login":
                print("Login successful - redirected to offer page!")
                save_cookies(session.cookies)
                return session
            else:
                print("Checking response content for clues...")
                soup = BeautifulSoup(login_response.text, 'html.parser')
                error_messages = soup.find_all(class_=['error', 'alert', 'warning'])
                if error_messages:
                    for error in error_messages:
                        print(f"Error message found: {error.get_text()}")
                
            print(f"Login attempt {attempt+1} may have failed. Retrying...")
            time.sleep(2)

        except requests.exceptions.RequestException as e:
            print(f"Login attempt {attempt + 1} failed with a network error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred during login: {e}")
            time.sleep(5)
            
    print("All login attempts failed.")
    return None

# For compatibility with the run() function format
def run(input_dict):
    # Test the login
    username = "jiocloud90@gmail.com"
    password = "@Sd2007123"

    print(f"Testing login with username: {username}")
    session = get_session(username, password)

    result = {"success": False, "session": None}
    
    if session:
        print("Login successful! Testing access to account page...")
        try:
            response = session.get(f"{BASE_URL}/account", timeout=15)
            print(f"Account page status: {response.status_code}")
            if response.status_code == 200:
                print("Access to account page confirmed!")
                result["success"] = True
                result["session"] = "active"
            else:
                print("Failed to access account page")
        except Exception as e:
            print(f"Error accessing account page: {e}")
    else:
        print("Login failed completely")
    
    return result

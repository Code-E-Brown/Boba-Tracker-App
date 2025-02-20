from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import json
from dotenv import load_dotenv, find_dotenv

# Load environment variables
env_path = find_dotenv()
load_dotenv(env_path, override=True)

def get_last_status():
    """Read the last known boba status from file"""
    try:
        with open('boba_status.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"was_unavailable": False}

def save_status(was_unavailable):
    """Save the current boba status to file"""
    with open('boba_status.json', 'w') as f:
        json.dump({"was_unavailable": was_unavailable}, f)

def send_email(subject, body):
    """Send email using Gmail SMTP"""
    sender_email = os.environ.get('EMAIL_SENDER')
    sender_password = os.environ.get('EMAIL_PASSWORD')
    receiver_email = os.environ.get('EMAIL_RECEIVER')
    
    if not all([sender_email, sender_password, receiver_email]):
        print("Email credentials not set in environment variables")
        return False
    
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    
    message.attach(MIMEText(body, "plain"))
    
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(str(sender_email).strip(), str(sender_password).strip())
        server.send_message(message)
        print(f"Email notification sent successfully to {receiver_email}")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False

def handle_modal(driver):
    """Attempt to close modal if it appears"""
    try:
        close_button = driver.find_element(By.XPATH, "//*[@id='modal-content']/div[1]/button")
        if close_button.is_displayed():
            close_button.click()
    except:
        pass

def check_boba_availability():
    email_was_sent = False  # Track if an email was sent
    
    # Setup Chrome options for headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Setup Chrome driver with options
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    try:
        # Navigate directly to the pistachio milk tea page
        driver.get("https://order.toasttab.com/online/teasnyou/item-pistachio-milk-tea_0090e00d-4be2-41a9-972f-dc591121459c")
        
        # Wait for the page to load completely
        wait = WebDriverWait(driver, 10)
        wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        
        # Check if page exists by looking for error indicators
        try:
            error_element = WebDriverWait(driver, 3).until(EC.presence_of_element_located(
                (By.XPATH, "//div[contains(@class, 'error-page') or contains(@class, '404')]")))
            print("Error: The pistachio milk tea page no longer exists or the URL has changed.")
            return
        except TimeoutException:
            # No error found, continue with normal flow
            pass
        
        # Wait for and find the 1/2 Boba option
        try:
            # Wait for the boba element while handling any modal that appears
            boba_element = None
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 second timeout
                handle_modal(driver)
                try:
                    boba_element = driver.find_element(
                        By.XPATH, "//div[contains(@class, 'name') and contains(text(), '1/2 Boba~')]")
                    break
                except:
                    continue
            
            if not boba_element:
                raise TimeoutException("Could not find boba element")
            
            # Get the parent input element to check if it's disabled
            input_element = driver.find_element(
                By.XPATH, 
                "//div[contains(@class, 'name') and contains(text(), '1/2 Boba~')]" +
                "/ancestor::label/preceding-sibling::input"
            )
            
            # Check if boba is available (not disabled)
            boba_available = not (input_element.get_attribute("aria-disabled") == "true")
            
            if boba_available:
                print("1/2 Boba is available for Pistachio Milk Tea!")
                # Check if we previously sent an unavailability email
                last_status = get_last_status()
                if last_status["was_unavailable"]:
                    email_sent = send_email(
                        "Boba Available Again!",
                        "Good news! The 1/2 boba option is now available for Pistachio Milk Tea at Teas n' You."
                    )
                    email_was_sent = email_sent
                    print(f"Availability notification {'sent' if email_sent else 'failed to send'}")
                save_status(False)
            else:
                print("Sorry, 1/2 boba is currently unavailable.")
                email_sent = send_email(
                    "Boba Unavailable Alert",
                    "The 1/2 boba option is currently unavailable for Pistachio Milk Tea at Teas n' You."
                )
                email_was_sent = email_sent
                print(f"Unavailability notification {'sent' if email_sent else 'failed to send'}")
                save_status(True)
                
        except TimeoutException:
            print("Could not find the 1/2 Boba option on the page. The page might not have loaded properly.")
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    
    finally:
        driver.quit()
        print(f"Email notification: {'Sent' if email_was_sent else 'Not sent'}")

if __name__ == "__main__":
    check_boba_availability() 
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
import undetected_chromedriver as uc

# Load environment variables
env_path = find_dotenv()
load_dotenv(env_path, override=True)

def get_last_status():
    """Read the last known boba status from file or environment"""
    # Check if running in GitHub Actions
    if 'GITHUB_TOKEN' in os.environ:
        return {"was_unavailable": os.environ.get('WAS_UNAVAILABLE', 'false').lower() == 'true'}
    
    # Local environment - use JSON file
    try:
        with open('boba_status.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"was_unavailable": False}

def save_status(was_unavailable):
    """Save the current boba status to file or print for GitHub Actions"""
    # Check if running in GitHub Actions
    if 'GITHUB_TOKEN' in os.environ:
        print(f"Would update WAS_UNAVAILABLE to: {was_unavailable}")
        return
    
    # Local environment - save to JSON file
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
    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Setup Chrome driver with options
    if 'GITHUB_TOKEN' in os.environ:
        print("Running in GitHub Actions environment")
        chromedriver_path = os.environ.get('CHROMEDRIVER_PATH', '/usr/bin/chromedriver')
        driver = uc.Chrome(
            options=chrome_options,
            driver_executable_path=chromedriver_path,
            version_main=133
        )
    else:
        print("Running in local environment")
        driver = uc.Chrome(
            options=chrome_options,
            version_main=111
        )
    
    try:
        print("Navigating to page...")
        driver.get("https://order.toasttab.com/online/teasnyou/item-pistachio-milk-tea_0090e00d-4be2-41a9-972f-dc591121459c")
        
        # Initial wait for page load
        wait = WebDriverWait(driver, 30)
        print("Waiting for page to load...")
        wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        print("Page load complete")
        
        # Print page info
        print(f"Current URL: {driver.current_url}")
        print(f"Page title: {driver.title}")
        
        # Handle Cloudflare
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            print(f"Attempt {retry_count + 1} to bypass Cloudflare...")
            
            # Wait longer for page to load
            time.sleep(10)
            
            # Check if we're still on Cloudflare page
            if "Just a moment" in driver.title:
                print("Still on Cloudflare page, retrying...")
                retry_count += 1
                if retry_count < max_retries:
                    # Refresh the page
                    driver.refresh()
                    time.sleep(5)
                continue
            else:
                print("Successfully bypassed Cloudflare!")
                break
        
        if retry_count >= max_retries:
            print("Failed to bypass Cloudflare after maximum retries")
            return
        
        try:
            # Wait for a known element that should be on the actual page
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "modifierGroups")))
            print("Main content loaded successfully")
        except TimeoutException:
            print("Failed to load main content after Cloudflare challenge")
            driver.save_screenshot("debug_screenshot.png")  # Save screenshot for debugging
            raise
        
        try:
            # Try to find any element on the page to verify content loaded
            body = driver.find_element(By.TAG_NAME, "body")
            print(f"Page content length: {len(body.text)}")
        except:
            print("Could not find page body")
        
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
            boba_available = not (
                input_element.get_attribute("disabled") is not None or 
                input_element.get_attribute("aria-disabled") == "true"
            )
            
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
                # Check if we haven't already sent an unavailability email
                last_status = get_last_status()
                if not last_status["was_unavailable"]:
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
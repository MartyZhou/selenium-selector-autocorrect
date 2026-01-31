"""Example: Basic usage of selenium-selector-autocorrect."""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_selector_autocorrect import install_auto_correct_hook

# Install the hook at test startup
install_auto_correct_hook()

# Use Selenium normally - auto-correction happens on timeouts
driver = webdriver.Chrome()

try:
    driver.get("https://example.com")
    
    # If this selector times out, AI will suggest an alternative
    element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "some-element"))
    )
    
    print("Element found!")
    
finally:
    driver.quit()

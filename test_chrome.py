from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from pyvirtualdisplay import Display
import time

print("Starting display...")
display = Display(visible=False, size=(1920, 1080))
display.start()

print("Setting up Chrome...")
options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")

print("Starting Chrome...")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

print("Loading page...")
driver.get("https://vkusvill.ru/cart/")
time.sleep(5)
print("Title:", driver.title)
print("Page length:", len(driver.page_source))

driver.quit()
display.stop()
print("SUCCESS")

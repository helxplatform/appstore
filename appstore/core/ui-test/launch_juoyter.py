from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager

driver = webdriver.Chrome(ChromeDriverManager().install())
driver.maximize_window()

driver.get('http://0.0.0.0:8000/admin')
driver.implicitly_wait(10)

username = driver.find_element_by_id('id_username')
username.clear()
username.send_keys("admin")

password = driver.find_element_by_id('id_password')
password.clear()
password.send_keys("admin")
driver.implicitly_wait(10)

driver.find_element_by_xpath("//input[@value='Log in']").click()

driver.implicitly_wait(20)

driver.get("http://0.0.0.0:8000/apps")

driver.find_element_by_id('create-new-pod-modal').click()

driver.implicitly_wait(30)
driver.find_element_by_xpath("//a[containsapp_id='jupyter-ds']").click()

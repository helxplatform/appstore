import time

from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager


class LaunchAppTest(StaticLiveServerTestCase):

    def setUp(self):
        self.selenium = webdriver.Chrome(ChromeDriverManager().install())
        self.selenium.implicitly_wait(10)
        self.selenium.maximize_window()
        self.user = User.objects.create_superuser(username='test_admin', email="admin@admin.com", password='admin')
        self.app_id = ['jupyter-ds', 'hail', 'blackbalsam', 'rstudio-server']
        self.login()

    def tearDown(self):
        self.selenium.quit()

    def login(self):
        self.selenium.get('%s%s' % (self.live_server_url, '/admin/'))
        username_input = self.selenium.find_element_by_name("username")
        username_input.send_keys('test_admin')
        password_input = self.selenium.find_element_by_name("password")
        password_input.send_keys('admin')
        self.selenium.find_element_by_xpath('//input[@value="Log in"]').click()

    def launch_app(self, app_id):
        self.selenium.find_element_by_id('create-new-pod-modal').click()
        time.sleep(2)
        self.selenium.find_element_by_xpath(f"//a[@app_id='{app_id}']").click()
        self.selenium.find_element_by_xpath("//button[@onclick='launchApp()']").click()
        self.selenium.switch_to.window(self.selenium.window_handles[0])

    def check_app(self):
        self.selenium.get('%s%s' % (self.live_server_url, '/apps/'))
        rData = []
        for row_number in range(1, len(self.app_id) + 1):
            row = self.selenium.find_element_by_xpath(
                "//table[@class='manage-pods-table table table-striped']").find_elements_by_xpath(
                f"//tr[" + str(row_number) + "]/td")
            for index, web_data in enumerate(row):
                if index % 6 == 0:
                    rData.append(web_data.text)
        return rData

    def delete_app(self):
        self.selenium.get('%s%s' % (self.live_server_url, '/apps/'))
        for row_number in range(1, len(self.app_id) + 1):
            row = self.selenium.find_element_by_xpath(
                "//table[@class='manage-pods-table table table-striped']").find_elements_by_xpath(
                f"//tr[" + str(row_number) + "]/td")
            for index, web_data in enumerate(row):
                if index % 5 == 0 and index != 0:
                    web_data.click()

    def test_launch_app(self):
        self.selenium.get('%s%s' % (self.live_server_url, '/apps/'))
        for app_id in self.app_id:
            self.launch_app(app_id)
        self.selenium.refresh()
        self.assertEqual(sorted(self.app_id), self.check_app())
        self.delete_app()
        time.sleep(5)



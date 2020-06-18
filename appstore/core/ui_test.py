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
        self.user = User.objects.create_superuser(username='admin', email="admin@admin.com", password='admin')
        self.app_id = ['blackbalsam', 'hail', 'rstudio-server', 'jupyter-ds']

    def tearDown(self):
        self.selenium.quit()

    def login(self):
        self.selenium.get('%s%s' % (self.live_server_url, '/admin/'))
        username_input = self.selenium.find_element_by_name("username")
        username_input.send_keys('admin')
        password_input = self.selenium.find_element_by_name("password")
        password_input.send_keys('admin')
        self.selenium.find_element_by_xpath('//input[@value="Log in"]').click()

    def launch_app(self,app_id):
        self.selenium.get('%s%s' % (self.live_server_url, '/apps/'))
        self.selenium.find_element_by_id('create-new-pod-modal').click()
        self.selenium.find_element_by_xpath(f"//a[@app_id='{app_id}']").click()
        self.selenium.find_element_by_xpath("//button[@onclick='launchApp()']").click()

    def test_launch_app(self):
        self.login()
        for app_id in self.app_id:
            self.launch_app(app_id)
        # self.launch_app('jupyter-ds')

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
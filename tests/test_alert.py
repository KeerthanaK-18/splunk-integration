import declare
import unittest
from mock import patch, MagicMock

mocked_modules = {}
def setUpModule():
    global mocked_modules

    module_to_be_mocked = [
        'splunk',
        'splunk.rest',
        'splunk.clilib',
        'solnlib.server_info',
        'splunk_aoblib',
        'splunk_aoblib.rest_migration',
        'solnlib.splunkenv'
    ]

    mocked_modules = {module: MagicMock() for module in module_to_be_mocked}

    for module, magicmock in mocked_modules.items():
        patch.dict('sys.modules', **{module: magicmock}).start()

def tearDownModule():
    patch.stopall()

class TestDatabricksAlert(unittest.TestCase):
    """Test databricksAlert."""

    @classmethod
    def setUp(cls):
        import modalert_launch_notebook_helper
        cls.alert = modalert_launch_notebook_helper

    def test_system_exit(self):
        helper = MagicMock()
        helper.get_param.side_effect = [" ", "ts", "param", "cluster"]
        helper.log_error = MagicMock()
        with self.assertRaises(SystemExit) as cm:
            self.alert.process_event(helper)
        helper.log_error.assert_called_once_with("Notebook path is a required parameter which is not provided.")
        self.assertEqual(cm.exception.code, 1)
    
    @patch("modalert_launch_notebook_helper.time", auto_spec=True)
    @patch("modalert_launch_notebook_helper.client", auto_spec=True)
    @patch("modalert_launch_notebook_helper.get_splunkd_access_info", auto_spec=True)
    def test_alert_adhoc(self, mock_info, mock_client, mock_time):
        helper = MagicMock()
        helper.get_param.side_effect = ["/path", "ts", "param", "cluster"]
        helper.alert_mode = "adhoc"
        helper.orig_sid = "sid"
        helper.orig_rid = "rid"
        mock_info.return_value = ("https", "localhost", "port")
        service = mock_client.connect.return_value = MagicMock()
        mock_time.time.side_effect = [1,2]
        helper.log_info = MagicMock()
        self.alert.process_event(helper)
        helper.log_info.assert_called_once_with("Exiting alert action. Time taken: 1 seconds.")
    
    @patch("modalert_launch_notebook_helper.time", auto_spec=True)
    @patch("modalert_launch_notebook_helper.client", auto_spec=True)
    @patch("modalert_launch_notebook_helper.get_splunkd_access_info", auto_spec=True)
    def test_alert_non_adhoc(self, mock_info, mock_client, mock_time):
        helper = MagicMock()
        helper.get_param.side_effect = ["/path", "ts", "param", "cluster"]
        helper.alert_mode = "scheduled"
        helper.sid = "sid"
        helper.settings = {"rid": "rid"}
        mock_info.return_value = ("https", "localhost", "port")
        service = mock_client.connect.return_value = MagicMock()
        mock_time.time.side_effect = [1,2]
        helper.log_info = MagicMock()
        self.alert.process_event(helper)
        helper.log_info.assert_called_once_with("Exiting alert action. Time taken: 1 seconds.")
    
    @patch("modalert_launch_notebook_helper.client", auto_spec=True)
    @patch("modalert_launch_notebook_helper.get_splunkd_access_info", auto_spec=True)
    def test_alert_exception(self, mock_info, mock_client):
        helper = MagicMock()
        helper.get_param.side_effect = ["/path", "ts", "param", "cluster"]
        helper.alert_mode = "scheduled"
        helper.sid = "sid"
        helper.settings = {"rid": "rid"}
        mock_info.return_value = ("https", "localhost", "port")
        service = mock_client.connect.side_effect = Exception("error in connect")
        helper.log_error = MagicMock()
        with self.assertRaises(SystemExit) as cm:
            self.alert.process_event(helper)
        self.assertEqual(helper.log_error.call_count, 2)
        self.assertEqual(cm.exception.code, 1)
    
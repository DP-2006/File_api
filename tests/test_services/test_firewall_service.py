# tests/test_services/test_firewall_service.py
import pytest
from unittest.mock import patch, MagicMock

from core.services.firewall_service import FirewallService


@pytest.mark.django_db
class TestFirewallService:
    
    def test_firewall_service_init(self):
        service = FirewallService()
        assert service is not None
    
    @patch('core.services.firewall_service.requests.get')
    def test_scan_file_safe(self, mock_get, test_file):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'is_threat': False,
            'severity': 'low'
        }
        mock_get.return_value = mock_response
        service = FirewallService()
        result = service.scan_file(test_file)
        assert result['is_threat'] is False
    
    @patch('core.services.firewall_service.requests.get')
    def test_scan_file_threat(self, mock_get, test_file):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'is_threat': True,
            'threat_type': 'malware',
            'severity': 'high'
        }
        mock_get.return_value = mock_response
        service = FirewallService()
        result = service.scan_file(test_file)
        assert result['is_threat'] is True
        assert result['threat_type'] == 'malware'

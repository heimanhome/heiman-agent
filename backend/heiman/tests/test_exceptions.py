import pytest
from fastapi import status

from heiman.middleware.exceptions import (
    BaseAPIException,
    BusinessException,
    ResourceNotFoundException,
    ConflictException,
    AuthenticationException,
    AuthorizationException,
    ValidationException,
    BadRequestException,
    DeviceNotFoundException,
    RuleNotFoundException,
    TaskNotFoundException,
    PersonNotFoundException,
    HomeNotFoundException,
    RuleValidationException,
    SensorDataException,
    ConfigurationException,
    RateLimitException,
    ServiceUnavailableException,
    DatabaseException,
    OfflineModeException,
)


class TestBaseAPIException:
    def test_default_values(self):
        exc = BaseAPIException()
        assert exc.code == 1000
        assert exc.http_status == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc.message == "Internal server error"

    def test_custom_message(self):
        exc = BaseAPIException(message="Custom error")
        assert exc.message == "Custom error"

    def test_custom_code(self):
        exc = BaseAPIException(code=9999)
        assert exc.code == 9999

    def test_custom_message_and_code(self):
        exc = BaseAPIException(message="Custom error", code=9999)
        assert exc.code == 9999
        assert exc.message == "Custom error"


class TestBusinessExceptions:
    def test_business_exception(self):
        exc = BusinessException()
        assert exc.code == 2000
        assert exc.http_status == status.HTTP_400_BAD_REQUEST

    def test_validation_exception(self):
        exc = ValidationException()
        assert exc.code == 1002
        assert exc.http_status == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert exc.message == "Validation failed"

    def test_bad_request_exception(self):
        exc = BadRequestException()
        assert exc.code == 1001
        assert exc.http_status == status.HTTP_400_BAD_REQUEST
        assert exc.message == "Bad request"


class TestResourceNotFoundExceptions:
    def test_resource_not_found(self):
        exc = ResourceNotFoundException()
        assert exc.code == 2001
        assert exc.http_status == status.HTTP_404_NOT_FOUND

    def test_device_not_found(self):
        exc = DeviceNotFoundException()
        assert exc.code == 2010
        assert exc.http_status == status.HTTP_404_NOT_FOUND
        assert "Device not found" in exc.message

    def test_rule_not_found(self):
        exc = RuleNotFoundException()
        assert exc.code == 2011
        assert exc.http_status == status.HTTP_404_NOT_FOUND

    def test_task_not_found(self):
        exc = TaskNotFoundException()
        assert exc.code == 2012
        assert exc.http_status == status.HTTP_404_NOT_FOUND

    def test_person_not_found(self):
        exc = PersonNotFoundException()
        assert exc.code == 2013
        assert exc.http_status == status.HTTP_404_NOT_FOUND

    def test_home_not_found(self):
        exc = HomeNotFoundException()
        assert exc.code == 2014
        assert exc.http_status == status.HTTP_404_NOT_FOUND


class TestAuthExceptions:
    def test_authentication_exception(self):
        exc = AuthenticationException()
        assert exc.code == 3001
        assert exc.http_status == status.HTTP_401_UNAUTHORIZED

    def test_authorization_exception(self):
        exc = AuthorizationException()
        assert exc.code == 3002
        assert exc.http_status == status.HTTP_403_FORBIDDEN


class TestConflictException:
    def test_conflict_exception(self):
        exc = ConflictException()
        assert exc.code == 2002
        assert exc.http_status == status.HTTP_409_CONFLICT


class TestSpecificBusinessExceptions:
    def test_rule_validation_exception(self):
        exc = RuleValidationException()
        assert exc.code == 1010
        assert exc.http_status == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_sensor_data_exception(self):
        exc = SensorDataException()
        assert exc.code == 2020
        assert exc.http_status == status.HTTP_400_BAD_REQUEST

    def test_configuration_exception(self):
        exc = ConfigurationException()
        assert exc.code == 2030
        assert exc.http_status == status.HTTP_400_BAD_REQUEST


class TestServiceExceptions:
    def test_rate_limit_exception(self):
        exc = RateLimitException()
        assert exc.code == 4001
        assert exc.http_status == status.HTTP_429_TOO_MANY_REQUESTS

    def test_service_unavailable_exception(self):
        exc = ServiceUnavailableException()
        assert exc.code == 5001
        assert exc.http_status == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_database_exception(self):
        exc = DatabaseException()
        assert exc.code == 5002
        assert exc.http_status == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_offline_mode_exception(self):
        exc = OfflineModeException()
        assert exc.code == 5010
        assert exc.http_status == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "offline" in exc.message.lower()

from fastapi import status


class BaseAPIException(Exception):
    code: int = 1000
    http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "Internal server error"

    def __init__(self, message: str | None = None, code: int | None = None):
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        super().__init__(self.message)


class BusinessException(BaseAPIException):
    code = 2000
    http_status = status.HTTP_400_BAD_REQUEST


class ResourceNotFoundException(BaseAPIException):
    code = 2001
    http_status = status.HTTP_404_NOT_FOUND
    message = "Resource not found"


class ConflictException(BaseAPIException):
    code = 2002
    http_status = status.HTTP_409_CONFLICT
    message = "Conflict"


class AuthenticationException(BaseAPIException):
    code = 3001
    http_status = status.HTTP_401_UNAUTHORIZED
    message = "Unauthorized"


class AuthorizationException(BaseAPIException):
    code = 3002
    http_status = status.HTTP_403_FORBIDDEN
    message = "Forbidden"


class ValidationException(BaseAPIException):
    code = 1002
    http_status = status.HTTP_422_UNPROCESSABLE_CONTENT
    message = "Validation failed"


class BadRequestException(BaseAPIException):
    code = 1001
    http_status = status.HTTP_400_BAD_REQUEST
    message = "Bad request"


class DeviceNotFoundException(ResourceNotFoundException):
    code = 2010
    message = "Device not found"


class RuleNotFoundException(ResourceNotFoundException):
    code = 2011
    message = "Rule not found"


class TaskNotFoundException(ResourceNotFoundException):
    code = 2012
    message = "Task not found"


class PersonNotFoundException(ResourceNotFoundException):
    code = 2013
    message = "Person not found"


class HomeNotFoundException(ResourceNotFoundException):
    code = 2014
    message = "Home not found"


class RuleValidationException(ValidationException):
    code = 1010
    message = "Rule validation failed"


class SensorDataException(BusinessException):
    code = 2020
    message = "Sensor data error"


class ConfigurationException(BusinessException):
    code = 2030
    message = "Configuration error"


class RateLimitException(BaseAPIException):
    code = 4001
    http_status = status.HTTP_429_TOO_MANY_REQUESTS
    message = "Rate limit exceeded"


class ServiceUnavailableException(BaseAPIException):
    code = 5001
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    message = "Service unavailable"


class DatabaseException(BaseAPIException):
    code = 5002
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    message = "Database error"


class OfflineModeException(ServiceUnavailableException):
    code = 5010
    message = "Service is running in offline mode"
class TychoException(Exception):
    def __init__(self, message, details=""):
        super().__init__(message)
        self.details = details


class StartException(Exception):
    def __init__(self, message, details=""):
        super().__init__(message, details)


class DeleteException(Exception):
    def __init__(self, message, details=""):
        super().__init__(message, details)


class ContextException(TychoException):
    def __init__(self, message, details=""):
        super().__init__(message, details)


class ModifyException(Exception):
    def __init__(self, message, details=""):
        super().__init__(message, details)
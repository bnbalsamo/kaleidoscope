class Error(Exception):
    err_name = "Error"
    status_code = 500
    message = ""

    def __init__(self, message=None):
        if message is not None:
            self.message = message

    def to_dict(self):
        return {"message": self.message,
                "error_name": self.err_name}


class ParameterError(Error):
    err_name = "ParamterError"
    status_code = 400


class IdentifierResolutionError(Error):
    err_name = "IdentifierResolutionError"
    status_code = 404

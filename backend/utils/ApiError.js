export class ApiError extends Error {
  constructor(statusCode, message, errors = [], stack = "") {
    super(message);
    this.statusCode = statusCode;
    this.message = message;
    this.errors = errors;
    if (stack) {
      this.stack = stack;
    } else {
      Error.captureStackTrace(this, this.constructor);
    }
  }

  static internal(message, error = null) {
    return new ApiError(
      message || error?.message || "Internal Server Error",
      500
    );
  }

  static badRequest(message) {
    return new ApiError(message || "Bad Request", 400);
  }

  static unauthorized(message) {
    return new ApiError(message || "Unauthorized", 401);
  }

  static notFound(message) {
    return new ApiError(message || "Not Found", 404);
  }

  static forbidden(message) {
    return new ApiError(message || "Forbidden", 403);
  }
}

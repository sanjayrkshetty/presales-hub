export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body:   string,
    public readonly path:   string,
  ) {
    super(`API ${status} ${path}: ${body}`);
    this.name = "ApiError";
  }

  get isClientError() { return this.status >= 400 && this.status < 500; }
  get isServerError() { return this.status >= 500; }
  get isUnauthorized(){ return this.status === 401; }
  get isForbidden()   { return this.status === 403; }
  get isNotFound()    { return this.status === 404; }
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}

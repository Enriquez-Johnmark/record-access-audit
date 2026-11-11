/** What the API says when it refuses (FastAPI's `detail`). */
interface ErrorBody {
  error: string
  code?: string
}

/** An answer from the API other than success, in the API's own words. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string | undefined

  constructor(status: number, body: ErrorBody) {
    super(body.error)
    this.name = "ApiError"
    this.status = status
    this.code = body.code
  }

  /** The session has ended; they must log in again. */
  get isNotLoggedIn() {
    return this.status === 401
  }
}

type Method = "GET" | "POST" | "PUT" | "DELETE"

/**
 * Calls the API. Every request in the app goes through here: it sends
 * the session cookie and JSON, and turns any failure
 * into an ApiError.
 */
export async function api<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) throw new ApiError(response.status, await errorBody(response))
  // 201, 202 and 204 answers may have no body at all.
  const text = await response.text()
  return (text === "" ? undefined : JSON.parse(text)) as T
}

async function errorBody(response: Response): Promise<ErrorBody> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === "string") return { error: body.detail }
  } catch {
    // Not JSON: a proxy or the network answered, not the API.
  }
  return { error: "The app couldn't be reached. Check your connection and try again." }
}

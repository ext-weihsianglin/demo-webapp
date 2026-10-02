/** Decode JSON API responses, including plain-text errors from the dev proxy. */
export async function readApiResponse(response: Response) {
  let data: ReturnType<typeof JSON.parse>;
  try {
    data = await response.json();
  } catch {
    throw new Error(response.ok
      ? `API returned an invalid response (HTTP ${response.status}). Try again.`
      : `API temporarily unavailable (HTTP ${response.status}). Try again when the backend is running.`);
  }
  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === 'string' ? detail
      : detail?.summary ? `${detail.status || 'API error'}: ${detail.summary}`
      : Array.isArray(detail) && detail[0]?.msg ? detail[0].msg
      : `API request failed (HTTP ${response.status}).`;
    throw new Error(message);
  }
  return data;
}

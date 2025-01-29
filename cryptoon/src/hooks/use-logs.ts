// hooks/use-logs.ts
import useSWR from "swr"

export function useLogs(userId?: string) {
  const { data, error } = useSWR(
    userId ? `/api/logs?userId=${userId}` : null,
    fetcher
  )

  return {
    logs: data,
    isLoading: !error && !data,
    isError: error
  }
}
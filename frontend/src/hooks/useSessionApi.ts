import { useQuery } from "@tanstack/react-query";
import { SessionApi } from "../api/session";

export function useSessionApi() {
    return useQuery({
        queryKey: ["sessions"],
        queryFn: SessionApi.getAll,
        select: (response) => response.sessions,
    });
}
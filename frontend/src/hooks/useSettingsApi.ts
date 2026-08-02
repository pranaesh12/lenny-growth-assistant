import { useQuery } from "@tanstack/react-query";

import { SettingsApi } from "../api/settings";

export function useSettingsApi() {
    return useQuery({
        queryKey: ["settings"],
        queryFn: async () => {
            const response = await SettingsApi.get();
            return response.data;
        },
    });
}
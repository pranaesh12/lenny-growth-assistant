import { useQuery } from "@tanstack/react-query";

import { ArtifactApi } from "../api/artifact";

export function useArtifactApi() {
    return useQuery({
        queryKey: ["artifacts"],
        queryFn: async () => {
            const response = await ArtifactApi.list();
            return response.data;
        },
    });
}
import api from "./client";

export const ArtifactApi = {
    list() {
        return api.get("/api/v1/artifacts");
    },

    get(id: string) {
        return api.get(`/api/v1/artifacts/${id}`);
    },

    delete(id: string) {
        return api.delete(`/api/v1/artifacts/${id}`);
    },
};
import api from "./client";

export const SettingsApi = {
    get() {
        return api.get("/api/v1/settings");
    },

    update(settings: unknown) {
        return api.put("/api/v1/settings", settings);
    },
};
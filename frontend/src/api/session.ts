import api from "./client";
import type { Session } from "../types/session";

interface SessionListResponse {
    sessions: Session[];
    count: number;
}

export const SessionApi = {
    async getAll(): Promise<SessionListResponse> {
        const response = await api.get<SessionListResponse>(
            "/api/v1/sessions",
        );

        return response.data;
    },

    async create(data: { title: string }): Promise<Session> {
        const response = await api.post<Session>(
            "/api/v1/sessions",
            data,
        );

        return response.data;
    },

    async rename(id: string, title: string): Promise<Session> {
        const response = await api.patch<Session>(
            `/api/v1/sessions/${id}`,
            { title },
        );

        return response.data;
    },

    async delete(id: string): Promise<void> {
        await api.delete(`/api/v1/sessions/${id}`);
    },
};
import { BrowserRouter, Routes, Route } from "react-router-dom";

import MainLayout from "../layouts/MainLayout";

import ChatPage from "../pages/ChatPage";
import SettingsPage from "../pages/SettingsPage";
import ArtifactPage from "../pages/ArtifactPage";

export default function AppRouter() {
    return (
        <BrowserRouter>
            <Routes>
                <Route element={<MainLayout />}>
                    <Route
                        path="/"
                        element={<ChatPage />}
                    />

                    <Route
                        path="/settings"
                        element={<SettingsPage />}
                    />

                    <Route
                        path="/artifacts"
                        element={<ArtifactPage />}
                    />
                </Route>
            </Routes>
        </BrowserRouter>
    );
}
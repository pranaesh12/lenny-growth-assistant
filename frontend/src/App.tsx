import { Toaster } from "sonner";

import AppRouter from "./routes/AppRouter";

export default function App() {
  return (
    <>
      <AppRouter />
      <Toaster richColors position="top-right" />
    </>
  );
}
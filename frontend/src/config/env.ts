const env = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
};

if (!env.apiBaseUrl) {
  throw new Error("VITE_API_BASE_URL is not configured.");
}

export default env;

import axios from "axios";

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL,
    headers: {
        "Content-Type": "application/json",
    },
});

// Automatically attach JWT to requests
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem("access_token");

        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }

        return config;
    },
    (error) => Promise.reject(error)
);

// Handle expired or invalid JWT
api.interceptors.response.use(
    (response) => response,
    (error) => {
        const status = error.response?.status;
        const requestUrl = error.config?.url || "";

        // Do not log out when login fails due to incorrect credentials
        if (status === 401 && !requestUrl.includes("/auth/login")) {
            localStorage.removeItem("access_token");

            window.dispatchEvent(
                new Event("auth:session-expired")
            );
        }

        return Promise.reject(error);
    }
);

export default api;

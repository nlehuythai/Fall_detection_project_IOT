import api from "./api";

export const authService = {
    // Register account
    register: async (userData) => {
        const response = await api.post("/auth/register", userData);
        return response.data;
    },

    // Login account
    login: async (email, password) => {
        const formData = new URLSearchParams();

        formData.append("username", email);
        formData.append("password", password);

        const response = await api.post("/auth/login", formData, {
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
            },
        });

        return response.data;
    },

    // Get current user
    getMe: async () => {
        const response = await api.get("/auth/me");
        return response.data;
    },
    // Update profile
    updateProfile: async (userData) => {
        const response = await api.patch("/auth/me", userData);
        return response.data;
    },

    // Change password
    changePassword: async (passwordData) => {
        const response = await api.patch(
            "/auth/me/password",
            passwordData
        );
        return response.data;
    },
};
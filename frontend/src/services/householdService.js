import api from "./api";

export const householdService = {
    // Get all households of current user
    getAll: async () => {
        const response = await api.get("/households/");
        return response.data;
    },

    // Create household
    create: async (data) => {
        const response = await api.post("/households/", data);
        return response.data;
    },

    // Get household details
    getById: async (householdId) => {
        const response = await api.get(`/households/${householdId}`);
        return response.data;
    },

    // Get household members
    getMembers: async (householdId) => {
        const response = await api.get(
            `/households/${householdId}/members`
        );
        return response.data;
    },

    // Update household
    update: async (householdId, data) => {
        const response = await api.patch(
            `/households/${householdId}`,
            data
        );
        return response.data;
    },
    // Create household invitation
    createInvite: async (householdId, data) => {
        const response = await api.post(
            `/households/${householdId}/invites`,
            data
        );
        return response.data;
    },

    // Accept household invitation
    acceptInvite: async (invitationToken) => {
        const response = await api.post(
            "/households/invites/accept",
            null,
            {
                params: {
                    invitation_token: invitationToken,
                },
            }
        );
        return response.data;
    },
    removeMember: async (householdId, userId) => {
        const response = await api.delete(
            `/households/${householdId}/members/${userId}`
        );
        return response.data;
    },
    // Get Telegram Bot configuration of household
    getTelegramBot: async (householdId) => {
        const response = await api.get(
            `/households/${householdId}/telegram-bot`
        );
        return response.data;
    },

    // Generate Telegram linking code
    createTelegramLinkCode: async (householdId) => {
        const response = await api.post(
            `/households/${householdId}/telegram-link-code`
        );
        return response.data;
    },
};

export default householdService;
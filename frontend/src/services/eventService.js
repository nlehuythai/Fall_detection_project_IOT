import api from "./api";

export const eventService = {
    // Get all fall events
    getAll: async (householdId) => {
        const response = await api.get(
            `/households/${householdId}/events`
        );
        return response.data;
    },

    // Get event details
    getById: async (householdId, eventId) => {
        const response = await api.get(
            `/households/${householdId}/events/${eventId}`
        );
        return response.data;
    },

    // Acknowledge fall event
    acknowledge: async (householdId, eventId) => {
        const response = await api.patch(
            `/households/${householdId}/events/${eventId}/acknowledge`
        );
        return response.data;
    },
};

export default eventService;
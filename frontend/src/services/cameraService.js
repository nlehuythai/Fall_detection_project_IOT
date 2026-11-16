import api from "./api";

export const cameraService = {
    // Register a new camera
    create: async (householdId, data) => {
        const response = await api.post(
            `/households/${householdId}/cameras`,
            data
        );
        return response.data;
    },

    // Get all cameras
    getAll: async (householdId) => {
        const response = await api.get(
            `/households/${householdId}/cameras`
        );
        return response.data;
    },

    // Get camera details
    getById: async (householdId, cameraId) => {
        const response = await api.get(
            `/households/${householdId}/cameras/${cameraId}`
        );
        return response.data;
    },

    // Update camera
    update: async (householdId, cameraId, data) => {
        const response = await api.patch(
            `/households/${householdId}/cameras/${cameraId}`,
            data
        );
        return response.data;
    },

    // Delete camera
    delete: async (householdId, cameraId) => {
        const response = await api.delete(
            `/households/${householdId}/cameras/${cameraId}`
        );
        return response.data;
    },

    // Regenerate camera API key
    regenerateKey: async (householdId, cameraId) => {
        const response = await api.post(
            `/households/${householdId}/cameras/${cameraId}/regenerate-key`
        );
        return response.data;
    },
};

export default cameraService;
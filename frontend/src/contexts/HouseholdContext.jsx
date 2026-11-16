import {
    createContext,
    useContext,
    useCallback,
    useEffect,
    useState,
} from "react";

import { useAuth } from "./AuthContext";
import { householdService } from "../services/householdService";

const HouseholdContext = createContext(null);

export function HouseholdProvider({ children }) {
    const { isAuthenticated } = useAuth();

    const [households, setHouseholds] = useState([]);
    const [household, setHousehold] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const refreshHouseholds = useCallback(async () => {
        if (!isAuthenticated) {
            setHouseholds([]);
            setHousehold(null);
            return;
        }

        try {
            setLoading(true);
            setError(null);

            const data = await householdService.getAll();

            setHouseholds(data);

            setHousehold((current) => {
                if (!data.length) return null;

                // Giữ hộ gia đình đang chọn nếu vẫn còn trong danh sách
                const existing = data.find(
                    (item) => item.id === current?.id
                );

                return existing || data[0];
            });
        } catch (err) {
            console.error("Failed to load households:", err);
            setError(
                err.response?.data?.detail ||
                "Không thể tải danh sách hộ gia đình."
            );
        } finally {
            setLoading(false);
        }
    }, [isAuthenticated]);

    useEffect(() => {
        refreshHouseholds();
    }, [refreshHouseholds]);

    const selectHousehold = (householdData) => {
        setHousehold(householdData);
    };

    const clearHousehold = () => {
        setHousehold(null);
    };

    return (
        <HouseholdContext.Provider
            value={{
                households,
                household,
                householdId: household?.id || null,
                loading,
                error,
                selectHousehold,
                clearHousehold,
                refreshHouseholds,
            }}
        >
            {children}
        </HouseholdContext.Provider>
    );
}

export function useHousehold() {
    return useContext(HouseholdContext);
}